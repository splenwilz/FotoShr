from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime, timedelta
import argparse
from werkzeug.security import check_password_hash, generate_password_hash
import logging
import boto3
from botocore.exceptions import ClientError
import uuid
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import DictCursor

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, static_folder='app/static', template_folder='app/templates')
app.logger.setLevel(logging.DEBUG)

# Configuration from environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fotoshr_secret_key')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', 'fotoshr.db')
app.config['USE_S3'] = os.environ.get('USE_S3', 'False').lower() == 'true'
app.config['AWS_S3_BUCKET'] = os.environ.get('AWS_S3_BUCKET', '')
app.config['AWS_REGION'] = os.environ.get('AWS_REGION', 'us-east-1')
app.config['AWS_ACCESS_KEY_ID'] = os.environ.get('AWS_ACCESS_KEY_ID', '')
app.config['AWS_SECRET_ACCESS_KEY'] = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
app.config['USE_POSTGRES'] = os.environ.get('USE_POSTGRES', 'False').lower() == 'true'
app.config['POSTGRES_HOST'] = os.environ.get('POSTGRES_HOST', 'db')
app.config['POSTGRES_PORT'] = os.environ.get('POSTGRES_PORT', '5432')
app.config['POSTGRES_USER'] = os.environ.get('POSTGRES_USER', 'postgres')
app.config['POSTGRES_PASSWORD'] = os.environ.get('POSTGRES_PASSWORD', 'postgres')
app.config['POSTGRES_DB'] = os.environ.get('POSTGRES_DB', 'fotoshr')

# Log app configuration
app.logger.debug(f"Static folder: {app.static_folder}")
app.logger.debug(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
app.logger.debug(f"Using S3: {app.config['USE_S3']}")
app.logger.debug(f"Using PostgreSQL: {app.config['USE_POSTGRES']}")

# Create upload folder if it doesn't exist and we're not using S3
if not app.config['USE_S3']:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize S3 client if enabled
s3_client = None
if app.config['USE_S3']:
    try:
        # Use environment variables for AWS credentials instead of profile
        s3_client = boto3.client(
            's3',
            region_name=app.config['AWS_REGION'],
            aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY']
        )
        app.logger.debug(f"S3 client initialized for region {app.config['AWS_REGION']} using environment variables")
    except Exception as e:
        app.logger.error(f"Failed to initialize S3 client: {str(e)}")

# Database setup
def get_db_connection():
    if app.config['USE_POSTGRES']:
        conn = psycopg2.connect(
            host=app.config['POSTGRES_HOST'],
            port=app.config['POSTGRES_PORT'],
            user=app.config['POSTGRES_USER'],
            password=app.config['POSTGRES_PASSWORD'],
            dbname=app.config['POSTGRES_DB'],
            cursor_factory=DictCursor
        )
        conn.autocommit = True
        return conn
    else:
        conn = sqlite3.connect(app.config['DATABASE_PATH'])
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if app.config['USE_POSTGRES']:
        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create images table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            title VARCHAR(100) NOT NULL,
            description TEXT,
            filename VARCHAR(255) NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags VARCHAR(255),
            views INTEGER DEFAULT 0,
            s3_url TEXT
        )
        ''')
        
        # Create likes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            image_id INTEGER NOT NULL REFERENCES images(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, image_id)
        )
        ''')
    else:
        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create images table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags TEXT,
            views INTEGER DEFAULT 0,
            s3_url TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        # Create likes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            image_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (image_id) REFERENCES images (id),
            UNIQUE(user_id, image_id)
        )
        ''')
    
    conn.commit()
    conn.close()

# Get last inserted ID
def get_last_id(conn, cursor):
    if app.config['USE_POSTGRES']:
        return cursor.fetchone()[0]
    else:
        return conn.execute('SELECT last_insert_rowid()').fetchone()[0]

# Initialize database on startup
init_db()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Helper function to upload file to S3
def upload_file_to_s3(file_data, file_name):
    if not s3_client:
        app.logger.error("S3 client not initialized")
        return None
    
    try:
        # Generate a unique object name
        object_name = f"{uuid.uuid4().hex}_{file_name}"
        s3_client.upload_fileobj(file_data, app.config['AWS_S3_BUCKET'], object_name)
        
        # Generate a pre-signed URL that expires in 1 hour
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': app.config['AWS_S3_BUCKET'], 'Key': object_name},
            ExpiresIn=3600
        )
        return {"url": url, "object_name": object_name}
    except ClientError as e:
        app.logger.error(f"Error uploading to S3: {str(e)}")
        return None

# Helper function to get a pre-signed URL for an S3 object
def get_s3_presigned_url(object_name):
    if not s3_client:
        app.logger.error("S3 client not initialized")
        return None
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': app.config['AWS_S3_BUCKET'], 'Key': object_name},
            ExpiresIn=3600
        )
        return url
    except ClientError as e:
        app.logger.error(f"Error generating pre-signed URL: {str(e)}")
        return None

# Routes
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if app.config['USE_POSTGRES']:
            cursor.execute('SELECT * FROM images ORDER BY upload_date DESC')
            images = cursor.fetchall()
        else:
            images = conn.execute('SELECT * FROM images ORDER BY upload_date DESC').fetchall()
        
        # Process images to get S3 URLs if needed
        processed_images = []
        for img in images:
            img_dict = dict(img)
            if app.config['USE_S3'] and img_dict.get('filename'):
                # If using S3 and we have a filename (which should be the S3 object name)
                img_dict['s3_url'] = get_s3_presigned_url(img_dict['filename'])
            processed_images.append(img_dict)
        
        app.logger.debug(f"Index page loaded with {len(processed_images)} images")
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        processed_images = []
    finally:
        conn.close()
    
    return render_template('index.html', images=processed_images)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if app.config['USE_POSTGRES']:
            cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s',
                         (username, password))
            user = cursor.fetchone()
        else:
            user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                              (username, password)).fetchone()
        
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if app.config['USE_POSTGRES']:
                cursor.execute('INSERT INTO users (username, password, email) VALUES (%s, %s, %s)',
                             (username, password, email))
            else:
                conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                           (username, password, email))
            
            conn.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except (sqlite3.IntegrityError, psycopg2.IntegrityError):
            flash('Username or email already exists')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('You need to be logged in to log out!')
        return redirect(url_for('login'))
    
    # Clear the session
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('index'))

@app.route('/profile')
@app.route('/profile/<int:user_id>')
def profile(user_id=None):
    # Use current user if no user_id is provided
    if user_id is None and 'user_id' in session:
        user_id = session['user_id']
    elif user_id is None:
        flash('You need to be logged in to view your profile!')
        return redirect(url_for('login'))
    
    # Get user information
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if app.config['USE_POSTGRES']:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
    else:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        flash('User not found!')
        conn.close()
        return redirect(url_for('index'))
    
    # Convert user dict to mutable dictionary and parse created_at as datetime
    user_dict = dict(user)
    if user_dict['created_at'] and isinstance(user_dict['created_at'], str):
        try:
            user_dict['created_at'] = datetime.strptime(user_dict['created_at'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # If parsing fails, leave it as is
            pass
    
    # Get user's images
    if app.config['USE_POSTGRES']:
        cursor.execute(
            'SELECT * FROM images WHERE user_id = %s ORDER BY upload_date DESC', 
            (user_id,)
        )
        images = cursor.fetchall()
    else:
        images = conn.execute(
            'SELECT * FROM images WHERE user_id = ? ORDER BY upload_date DESC', 
            (user_id,)
        ).fetchall()
    
    # Check if likes table exists
    total_likes = 0
    if app.config['USE_POSTGRES']:
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'likes')")
        likes_table_exists = cursor.fetchone()[0]
        
        if likes_table_exists:
            cursor.execute('''
                SELECT COUNT(*) as total_likes 
                FROM likes 
                WHERE image_id IN (SELECT id FROM images WHERE user_id = %s)
            ''', (user_id,))
            total_likes_result = cursor.fetchone()
            if total_likes_result:
                total_likes = total_likes_result[0]
    else:
        cursor = conn.cursor()
        likes_table_exists = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='likes'").fetchone()
        
        if likes_table_exists:
            total_likes_result = conn.execute('''
                SELECT COUNT(*) as total_likes 
                FROM likes 
                WHERE image_id IN (SELECT id FROM images WHERE user_id = ?)
            ''', (user_id,)).fetchone()
            if total_likes_result:
                total_likes = total_likes_result[0]
    
    # Process images to convert date strings to datetime objects and add S3 URLs
    processed_images = []
    for image in images:
        image_dict = dict(image)
        # Handle upload_date field (convert to created_at for template compatibility)
        if image_dict.get('upload_date') and isinstance(image_dict['upload_date'], str):
            try:
                # Set both the original field and created_at for template compatibility
                image_dict['upload_date'] = datetime.strptime(image_dict['upload_date'], '%Y-%m-%d %H:%M:%S')
                image_dict['created_at'] = image_dict['upload_date']
            except ValueError:
                # If parsing fails, leave as is
                image_dict['created_at'] = None
        
        # Get S3 URL if using S3
        if app.config['USE_S3'] and image_dict.get('filename'):
            image_dict['s3_url'] = get_s3_presigned_url(image_dict['filename'])
        
        processed_images.append(image_dict)
    
    # Calculate statistics
    stats = {
        'total_images': len(processed_images),
        'total_views': sum(image['views'] or 0 for image in processed_images if 'views' in image),
        'total_likes': total_likes
    }
    
    conn.close()
    
    return render_template('profile.html', user=user_dict, images=processed_images, stats=stats)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('You need to be logged in to upload images!')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Get form data
            title = request.form.get('title', 'Untitled')
            description = request.form.get('description', '')
            tags = request.form.get('tags', '')
            
            # Secure the filename
            filename = secure_filename(file.filename)
            
            # Handle file storage (S3 or local)
            s3_url = None
            if app.config['USE_S3']:
                # Upload to S3
                s3_result = upload_file_to_s3(file, filename)
                if s3_result:
                    filename = s3_result['object_name']  # Store S3 object name in database
                    s3_url = s3_result['url']
                else:
                    flash('Error uploading to cloud storage')
                    return redirect(request.url)
            else:
                # Save locally
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
            
            # Save to database
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                if app.config['USE_POSTGRES']:
                    cursor.execute(
                        'INSERT INTO images (user_id, title, description, filename, tags, s3_url) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                        (session['user_id'], title, description, filename, tags, s3_url)
                    )
                    image_id = cursor.fetchone()[0]
                    conn.commit()
                else:
                    conn.execute(
                        'INSERT INTO images (user_id, title, description, filename, tags, s3_url) VALUES (?, ?, ?, ?, ?, ?)',
                        (session['user_id'], title, description, filename, tags, s3_url)
                    )
                    conn.commit()
                    image_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                
                app.logger.info(f"Image uploaded successfully: id={image_id}, filename={filename}, s3_url={s3_url}")
                flash('Image uploaded successfully!')
                return redirect(url_for('image', image_id=image_id))
            except Exception as e:
                app.logger.error(f"Error saving image to database: {str(e)}")
                flash('Error saving image information to database')
                return redirect(request.url)
            finally:
                conn.close()
    
    return render_template('upload.html')

@app.route('/search')
def search():
    query = request.args.get('query', '')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if query:
            # Get filter parameters
            categories = request.args.get('categories', '').split(',') if request.args.get('categories') else []
            time_filter = request.args.get('time', '')
            search_in = request.args.get('search_in', 'title,description,tags').split(',')
            
            # Build the search conditions
            conditions = []
            params = []
            
            # Search in specified fields
            field_conditions = []
            if 'title' in search_in:
                field_conditions.append('i.title LIKE ?')
                params.append(f'%{query}%')
            if 'description' in search_in:
                field_conditions.append('i.description LIKE ?')
                params.append(f'%{query}%')
            if 'tags' in search_in:
                field_conditions.append('i.tags LIKE ?')
                params.append(f'%{query}%')
            
            if field_conditions:
                conditions.append('(' + ' OR '.join(field_conditions) + ')')
            
            # Apply category filter (if categories are provided)
            if categories and categories[0]:  # Check if categories is not empty
                category_conditions = []
                for category in categories:
                    category_conditions.append('i.tags LIKE ?')
                    params.append(f'%{category}%')
                conditions.append('(' + ' OR '.join(category_conditions) + ')')
            
            # Apply time filter
            if time_filter:
                current_time = datetime.now()
                if time_filter == '24h':
                    conditions.append('i.upload_date >= ?')
                    params.append((current_time - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'))
                elif time_filter == '7d':
                    conditions.append('i.upload_date >= ?')
                    params.append((current_time - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'))
                elif time_filter == '30d':
                    conditions.append('i.upload_date >= ?')
                    params.append((current_time - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S'))
                elif time_filter == 'year':
                    conditions.append('i.upload_date >= ?')
                    params.append((current_time - timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S'))
            
            # Construct the final query
            sql_query = '''
                SELECT i.*, u.username 
                FROM images i
                JOIN users u ON i.user_id = u.id
            '''
            
            if conditions:
                sql_query += ' WHERE ' + ' AND '.join(conditions)
            
            # Apply sorting
            sort = request.args.get('sort', 'newest')
            if sort == 'oldest':
                sql_query += ' ORDER BY i.upload_date ASC'
            elif sort == 'most_viewed':
                sql_query += ' ORDER BY i.views DESC'
            elif sort == 'most_liked':
                # Would need a join with likes table for better sorting
                sql_query += ' ORDER BY i.upload_date DESC'
            else:  # default to newest
                sql_query += ' ORDER BY i.upload_date DESC'
            
            app.logger.info(f"Search query: {sql_query}, params: {params}")
            
            # Execute the query
            if app.config['USE_POSTGRES']:
                # Replace ? with %s for PostgreSQL
                sql_query = sql_query.replace('?', '%s')
                cursor.execute(sql_query, params)
                results = cursor.fetchall()
            else:
                results = conn.execute(sql_query, params).fetchall()
            
            # Process images to include user data
            images = []
            for img in results:
                img_dict = dict(img)
                img_dict['user'] = {'username': img['username']}
                
                # Generate S3 URL if needed
                if app.config['USE_S3'] and img_dict.get('filename'):
                    img_dict['s3_url'] = get_s3_presigned_url(img_dict['filename'])
                
                images.append(img_dict)
                
            app.logger.info(f"Found {len(images)} search results for '{query}'")
        else:
            # If no query, get some recent images to display
            if app.config['USE_POSTGRES']:
                cursor.execute('''
                    SELECT i.*, u.username 
                    FROM images i
                    JOIN users u ON i.user_id = u.id
                    ORDER BY i.upload_date DESC LIMIT 6
                ''')
                results = cursor.fetchall()
            else:
                results = conn.execute('''
                    SELECT i.*, u.username 
                    FROM images i
                    JOIN users u ON i.user_id = u.id
                    ORDER BY i.upload_date DESC LIMIT 6
                ''').fetchall()
            
            # Process images to include user data
            images = []
            for img in results:
                img_dict = dict(img)
                img_dict['user'] = {'username': img['username']}
                
                # Generate S3 URL if needed
                if app.config['USE_S3'] and img_dict.get('filename'):
                    img_dict['s3_url'] = get_s3_presigned_url(img_dict['filename'])
                
                images.append(img_dict)
    
    except Exception as e:
        app.logger.error(f"Error in search route: {str(e)}")
        images = []
    finally:
        conn.close()
    
    return render_template('search.html', images=images, query=query)

@app.route('/gallery')
def gallery():
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'newest')
    query = request.args.get('query', '')
    category = request.args.get('category', '')
    date_filter = request.args.get('date', '')
    user_filter = request.args.get('user', '')
    tags_filter = request.args.get('tags', '')
    per_page = 12
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Sort based on parameter
    if sort == 'oldest':
        order_by = 'i.upload_date ASC'
    elif sort == 'most_viewed':
        order_by = 'i.views DESC'
    elif sort == 'most_liked':
        # We could count likes with a subquery if needed
        order_by = 'i.upload_date DESC'
    else:  # default newest
        order_by = 'i.upload_date DESC'
    
    # Build the search conditions if a query is provided
    conditions = []
    params = []
    
    if query:
        # Search in title, description, and tags
        search_conditions = [
            'i.title LIKE ?',
            'i.description LIKE ?',
            'i.tags LIKE ?'
        ]
        for _ in search_conditions:
            params.append(f'%{query}%')
        conditions.append('(' + ' OR '.join(search_conditions) + ')')
    
    # Apply category filter if provided
    if category:
        conditions.append('i.tags LIKE ?')
        params.append(f'%{category}%')
    
    # Apply date filter if provided
    if date_filter:
        current_time = datetime.now()
        if date_filter == 'today':
            conditions.append('i.upload_date >= ?')
            params.append((current_time - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'))
        elif date_filter == 'week':
            conditions.append('i.upload_date >= ?')
            params.append((current_time - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'))
        elif date_filter == 'month':
            conditions.append('i.upload_date >= ?')
            params.append((current_time - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S'))
        elif date_filter == 'year':
            conditions.append('i.upload_date >= ?')
            params.append((current_time - timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S'))
    
    # Apply user filter if provided
    if user_filter:
        conditions.append('u.username LIKE ?')
        params.append(f'%{user_filter}%')
    
    # Apply tags filter if provided
    if tags_filter:
        tags = [tag.strip() for tag in tags_filter.split(',')]
        tag_conditions = []
        for tag in tags:
            if tag:
                tag_conditions.append('i.tags LIKE ?')
                params.append(f'%{tag}%')
        if tag_conditions:
            conditions.append('(' + ' OR '.join(tag_conditions) + ')')
    
    # Construct SQL query based on conditions
    sql_count = 'SELECT COUNT(*) FROM images i JOIN users u ON i.user_id = u.id'
    sql_query = '''
        SELECT i.*, u.username 
        FROM images i
        JOIN users u ON i.user_id = u.id
    '''
    
    if conditions:
        where_clause = ' WHERE ' + ' AND '.join(conditions)
        sql_count += where_clause
        sql_query += where_clause
    
    # Get total count for pagination
    try:
        if app.config['USE_POSTGRES']:
            # Replace ? with %s for PostgreSQL
            pg_sql_count = sql_count.replace('?', '%s')
            cursor.execute(pg_sql_count, params)
            total = cursor.fetchone()[0]
        else:
            total = conn.execute(sql_count, params).fetchone()[0]
    except Exception as e:
        app.logger.error(f"Error getting count: {str(e)}")
        total = 0
    
    total_pages = max(1, (total // per_page) + (1 if total % per_page > 0 else 0))
    
    # Calculate pagination
    offset = (page - 1) * per_page
    sql_query += f' ORDER BY {order_by}'
    
    if app.config['USE_POSTGRES']:
        sql_query += f' LIMIT {per_page} OFFSET {offset}'
        params_copy = params.copy()  # Create a copy of params since we won't add to it for Postgres
    else:
        sql_query += ' LIMIT ? OFFSET ?'
        params.append(per_page)
        params.append(offset)
    
    try:
        app.logger.debug(f"Gallery query: {sql_query}, params: {params}")
        
        if app.config['USE_POSTGRES']:
            # Replace ? with %s for PostgreSQL
            pg_sql_query = sql_query.replace('?', '%s')
            cursor.execute(pg_sql_query, params_copy)
            images_raw = cursor.fetchall()
            
            # Check if likes table exists
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'likes')")
            likes_table_exists = cursor.fetchone()[0]
        else:
            images_raw = conn.execute(sql_query, params).fetchall()
            
            # Check if likes table exists
            cursor = conn.cursor()
            likes_table_exists = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='likes'").fetchone()
        
        # Process images to include user data
        images = []
        for img in images_raw:
            img_dict = dict(img)
            img_dict['user'] = {'username': img['username']}
            
            # Count likes for this image if the likes table exists
            if likes_table_exists:
                if app.config['USE_POSTGRES']:
                    cursor.execute('SELECT COUNT(*) FROM likes WHERE image_id = %s', (img['id'],))
                    likes_count = cursor.fetchone()[0]
                else:
                    likes_count = conn.execute('SELECT COUNT(*) FROM likes WHERE image_id = ?', 
                                            (img['id'],)).fetchone()[0]
                img_dict['likes'] = likes_count
            else:
                img_dict['likes'] = 0
            
            # Generate S3 URL if needed
            if app.config['USE_S3'] and img_dict.get('filename'):
                img_dict['s3_url'] = get_s3_presigned_url(img_dict['filename'])
            
            # Log image data for debugging
            app.logger.debug(f"Image data: id={img_dict['id']}, title={img_dict['title']}, filename={img_dict['filename']}")
            app.logger.debug(f"Static URL: {url_for('static', filename='uploads/' + img_dict['filename'])}")
            
            images.append(img_dict)
        
        # Get liked images for the current user
        liked_images = []
        if 'user_id' in session and likes_table_exists:
            if app.config['USE_POSTGRES']:
                cursor.execute('SELECT image_id FROM likes WHERE user_id = %s', (session['user_id'],))
                liked = cursor.fetchall()
                liked_images = [row['image_id'] for row in liked]
            else:
                liked = conn.execute('SELECT image_id FROM likes WHERE user_id = ?', 
                                (session['user_id'],)).fetchall()
                liked_images = [row['image_id'] for row in liked]
        
        # Pagination URLs
        next_url = url_for('gallery', page=page+1, sort=sort, query=query, category=category, 
                          date=date_filter, user=user_filter, tags=tags_filter) if page < total_pages else None
        prev_url = url_for('gallery', page=page-1, sort=sort, query=query, category=category, 
                         date=date_filter, user=user_filter, tags=tags_filter) if page > 1 else None
        
        app.logger.info(f"Gallery loaded with {len(images)} images")
        
    except Exception as e:
        app.logger.error(f"Error in gallery route: {str(e)}")
        images = []
        liked_images = []
        next_url = None
        prev_url = None
        total_pages = 1
    finally:
        conn.close()
    
    return render_template('gallery.html', 
                          images=images, 
                          page=page,
                          total_pages=total_pages,
                          sort=sort,
                          query=query,
                          category=category,
                          date_filter=date_filter,
                          user_filter=user_filter,
                          tags_filter=tags_filter,
                          liked_images=liked_images,
                          next_url=next_url,
                          prev_url=prev_url)

@app.route('/image/<int:image_id>')
def image(image_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if app.config['USE_POSTGRES']:
        cursor.execute('SELECT * FROM images WHERE id = %s', (image_id,))
        image = cursor.fetchone()
    else:
        image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
    
    if not image:
        flash('Image not found!')
        conn.close()
        return redirect(url_for('index'))
    
    # Convert to dictionary
    image_dict = dict(image)
    
    # Increment view count
    if app.config['USE_POSTGRES']:
        cursor.execute('UPDATE images SET views = views + 1 WHERE id = %s', (image_id,))
    else:
        conn.execute('UPDATE images SET views = views + 1 WHERE id = ?', (image_id,))
    
    conn.commit()
    
    # Get user info
    if app.config['USE_POSTGRES']:
        cursor.execute('SELECT username FROM users WHERE id = %s', (image_dict['user_id'],))
        user = cursor.fetchone()
    else:
        user = conn.execute('SELECT username FROM users WHERE id = ?', (image_dict['user_id'],)).fetchone()
    
    image_dict['username'] = user['username'] if user else 'Unknown'
    
    # Get like info
    if app.config['USE_POSTGRES']:
        cursor.execute('SELECT COUNT(*) FROM likes WHERE image_id = %s', (image_id,))
        like_count = cursor.fetchone()[0]
    else:
        like_count = conn.execute('SELECT COUNT(*) FROM likes WHERE image_id = ?', (image_id,)).fetchone()[0]
    
    image_dict['likes'] = like_count
    
    # Check if current user has liked this image
    user_liked = False
    if 'user_id' in session:
        if app.config['USE_POSTGRES']:
            cursor.execute('SELECT id FROM likes WHERE user_id = %s AND image_id = %s', 
                         (session['user_id'], image_id))
            result = cursor.fetchone()
        else:
            result = conn.execute('SELECT id FROM likes WHERE user_id = ? AND image_id = ?', 
                                 (session['user_id'], image_id)).fetchone()
        
        user_liked = True if result else False
    
    image_dict['user_liked'] = user_liked
    
    # Get S3 URL if using S3
    if app.config['USE_S3'] and image_dict.get('filename'):
        image_dict['s3_url'] = get_s3_presigned_url(image_dict['filename'])
    
    conn.close()
    return render_template('image_detail.html', image=image_dict)

@app.route('/like_image/<int:image_id>', methods=['POST'])
def like_image(image_id):
    if 'user_id' not in session:
        flash('You need to be logged in to like images!')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if app.config['USE_POSTGRES']:
            cursor.execute('INSERT INTO likes (user_id, image_id) VALUES (%s, %s)',
                         (session['user_id'], image_id))
        else:
            conn.execute('INSERT INTO likes (user_id, image_id) VALUES (?, ?)',
                       (session['user_id'], image_id))
        
        conn.commit()
    except (sqlite3.IntegrityError, psycopg2.IntegrityError):
        # User has already liked this image
        pass
    
    conn.close()
    return redirect(url_for('image', image_id=image_id))

@app.route('/unlike_image/<int:image_id>', methods=['POST'])
def unlike_image(image_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if app.config['USE_POSTGRES']:
        cursor.execute('DELETE FROM likes WHERE user_id = %s AND image_id = %s',
                     (session['user_id'], image_id))
    else:
        conn.execute('DELETE FROM likes WHERE user_id = ? AND image_id = ?',
                   (session['user_id'], image_id))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('image', image_id=image_id))

@app.route('/delete_image/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    # Check if user is logged in
    if 'user_id' not in session:
        flash('You need to be logged in to delete images!')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the image details
    if app.config['USE_POSTGRES']:
        cursor.execute('SELECT * FROM images WHERE id = %s AND user_id = %s', 
                     (image_id, session['user_id']))
        image = cursor.fetchone()
    else:
        image = conn.execute('SELECT * FROM images WHERE id = ? AND user_id = ?', 
                           (image_id, session['user_id'])).fetchone()
    
    if not image:
        flash('Image not found or you do not have permission to delete it!')
        conn.close()
        return redirect(url_for('index'))
    
    # Delete associated likes
    if app.config['USE_POSTGRES']:
        cursor.execute('DELETE FROM likes WHERE image_id = %s', (image_id,))
    else:
        conn.execute('DELETE FROM likes WHERE image_id = ?', (image_id,))
    
    # Delete the image from the database
    if app.config['USE_POSTGRES']:
        cursor.execute('DELETE FROM images WHERE id = %s', (image_id,))
    else:
        conn.execute('DELETE FROM images WHERE id = ?', (image_id,))
    
    conn.commit()
    conn.close()
    
    # Delete the file based on storage method
    if app.config['USE_S3']:
        try:
            # Delete from S3 bucket
            if s3_client and image['filename']:
                s3_client.delete_object(
                    Bucket=app.config['AWS_S3_BUCKET'],
                    Key=image['filename']
                )
                app.logger.info(f"Deleted image from S3: {image['filename']}")
        except Exception as e:
            app.logger.error(f"Error deleting image from S3: {str(e)}")
    else:
        # Delete from local storage
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], image['filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
                app.logger.info(f"Deleted local image file: {file_path}")
        except Exception as e:
            app.logger.error(f"Error deleting local image file: {str(e)}")
    
    flash('Image deleted successfully!')
    return redirect(url_for('index'))

@app.route('/edit_image/<int:image_id>', methods=['GET', 'POST'])
def edit_image(image_id):
    # Check if user is logged in
    if 'user_id' not in session:
        flash('You need to be logged in to edit images!')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the image details
    if app.config['USE_POSTGRES']:
        cursor.execute('SELECT * FROM images WHERE id = %s AND user_id = %s', 
                     (image_id, session['user_id']))
        image = cursor.fetchone()
    else:
        image = conn.execute('SELECT * FROM images WHERE id = ? AND user_id = ?', 
                           (image_id, session['user_id'])).fetchone()
    
    if not image:
        flash('Image not found or you do not have permission to edit it!')
        conn.close()
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Update image details
        title = request.form.get('title', 'Untitled')
        description = request.form.get('description', '')
        tags = request.form.get('tags', '')
        
        if app.config['USE_POSTGRES']:
            cursor.execute('UPDATE images SET title = %s, description = %s, tags = %s WHERE id = %s',
                         (title, description, tags, image_id))
        else:
            conn.execute('UPDATE images SET title = ?, description = ?, tags = ? WHERE id = ?',
                       (title, description, tags, image_id))
        
        conn.commit()
        conn.close()
        
        flash('Image updated successfully!')
        return redirect(url_for('image', image_id=image_id))
    
    conn.close()
    return render_template('edit_image.html', image=image)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # In a real application, you would process the form data here
        # For example, sending an email or storing the message in a database
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Example: Log the message or send an email
        print(f"Contact form submission from {name} ({email}): {subject}")
        
        flash('Thank you for your message! We will get back to you soon.')
        return redirect(url_for('contact'))
        
    return render_template('contact.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to change your settings')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    
    # Get user information
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        flash('User not found')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Process form data
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate current password if trying to change password
        if new_password:
            if not current_password:
                flash('Current password is required to set a new password')
                conn.close()
                return render_template('settings.html', user=user)
                
            if new_password != confirm_password:
                flash('New passwords do not match')
                conn.close()
                return render_template('settings.html', user=user)
                
            # Verify current password
            if not check_password_hash(user['password'], current_password):
                flash('Current password is incorrect')
                conn.close()
                return render_template('settings.html', user=user)
                
            # Update password
            hashed_password = generate_password_hash(new_password)
            conn.execute('UPDATE users SET password = ? WHERE id = ?', 
                       (hashed_password, user_id))
            flash('Password updated successfully')
        
        # Update email if provided
        if email and email != user['email']:
            conn.execute('UPDATE users SET email = ? WHERE id = ?', 
                       (email, user_id))
            flash('Email updated successfully')
        
        conn.commit()
        conn.close()
        return redirect(url_for('settings'))
    
    conn.close()
    return render_template('settings.html', user=user)

@app.route('/help')
def help_center():
    return render_template('help_center.html')

@app.route('/privacy')
def privacy_policy():
    return render_template('privacy.html')

@app.route('/terms')
def terms_of_service():
    return render_template('terms.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the FotoShr application')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the app on')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the app on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    app.run(host=args.host, port=args.port, debug=args.debug) 