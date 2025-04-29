from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime, timedelta
import argparse
from werkzeug.security import check_password_hash, generate_password_hash
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, static_folder='app/static', template_folder='app/templates')
app.logger.setLevel(logging.DEBUG)

app.config['SECRET_KEY'] = 'fotoshr_secret_key'
app.config['UPLOAD_FOLDER'] = 'app/static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Log app configuration
app.logger.debug(f"Static folder: {app.static_folder}")
app.logger.debug(f"Upload folder: {app.config['UPLOAD_FOLDER']}")

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database setup
def get_db_connection():
    conn = sqlite3.connect('fotoshr.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
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

# Initialize database on startup
init_db()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/')
def index():
    conn = get_db_connection()
    images = conn.execute('SELECT * FROM images ORDER BY upload_date DESC').fetchall()
    conn.close()
    return render_template('index.html', images=images)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
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
        try:
            conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                       (username, password, email))
            conn.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
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
    images = conn.execute(
        'SELECT * FROM images WHERE user_id = ? ORDER BY upload_date DESC', 
        (user_id,)
    ).fetchall()
    
    # Check if likes table exists
    cursor = conn.cursor()
    likes_table_exists = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='likes'").fetchone()
    
    # Get total likes for the user's images
    total_likes = 0
    if likes_table_exists:
        # Count likes from the likes table
        total_likes_result = conn.execute('''
            SELECT COUNT(*) as total_likes 
            FROM likes 
            WHERE image_id IN (SELECT id FROM images WHERE user_id = ?)
        ''', (user_id,)).fetchone()
        if total_likes_result:
            total_likes = total_likes_result[0]
    
    # Process images to convert date strings to datetime objects
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
    if 'user_id' not in session:
        flash('Please log in to upload images')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to filename to make it unique
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            title = request.form['title']
            description = request.form.get('description', '')
            tags = request.form.get('tags', '')
            
            conn = get_db_connection()
            conn.execute('INSERT INTO images (user_id, title, description, filename, tags) VALUES (?, ?, ?, ?, ?)',
                       (session['user_id'], title, description, filename, tags))
            conn.commit()
            conn.close()
            
            flash('Image uploaded successfully')
            return redirect(url_for('index'))
    
    return render_template('upload.html')

@app.route('/search')
def search():
    query = request.args.get('query', '')
    
    try:
        conn = get_db_connection()
        
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
            results = conn.execute(sql_query, params).fetchall()
            
            # Process images to include user data
            images = []
            for img in results:
                img_dict = dict(img)
                img_dict['user'] = {'username': img['username']}
                images.append(img_dict)
                
            app.logger.info(f"Found {len(images)} search results for '{query}'")
        else:
            # If no query, get some recent images to display
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
        total = conn.execute(sql_count, params).fetchone()[0]
    except Exception as e:
        app.logger.error(f"Error getting count: {str(e)}")
        total = 0
    
    total_pages = max(1, (total // per_page) + (1 if total % per_page > 0 else 0))
    
    # Calculate pagination
    offset = (page - 1) * per_page
    sql_query += f' ORDER BY {order_by} LIMIT ? OFFSET ?'
    params.append(per_page)
    params.append(offset)
    
    try:
        app.logger.debug(f"Gallery query: {sql_query}, params: {params}")
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
                likes_count = conn.execute('SELECT COUNT(*) FROM likes WHERE image_id = ?', 
                                        (img['id'],)).fetchone()[0]
                img_dict['likes'] = likes_count
            else:
                img_dict['likes'] = 0
                
            # Log image data for debugging
            app.logger.debug(f"Image data: id={img_dict['id']}, title={img_dict['title']}, filename={img_dict['filename']}")
            app.logger.debug(f"Static URL: {url_for('static', filename='uploads/' + img_dict['filename'])}")
            
            images.append(img_dict)
        
        # Get liked images for the current user
        liked_images = []
        if 'user_id' in session and likes_table_exists:
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
    
    # Check if the image exists
    image = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
    
    if not image:
        flash('Image not found')
        return redirect(url_for('index'))
    
    # Get username
    user = conn.execute('SELECT username FROM users WHERE id = ?', (image['user_id'],)).fetchone()
    if user:
        image = dict(image)
        image['user'] = {'username': user['username']}
        image['views'] = 0  # Default value
    
    # Check if views column exists
    cursor = conn.cursor()
    column_exists = cursor.execute("PRAGMA table_info(images)").fetchall()
    views_exists = any(col[1] == 'views' for col in column_exists)
    
    if not views_exists:
        # Add views column if it doesn't exist
        try:
            conn.execute('ALTER TABLE images ADD COLUMN views INTEGER DEFAULT 0')
            conn.commit()
        except:
            # Column might have been added in another request
            pass
    
    # Update view count
    try:
        conn.execute('UPDATE images SET views = COALESCE(views, 0) + 1 WHERE id = ?', (image_id,))
        conn.commit()
    except sqlite3.OperationalError:
        # Handle potential race condition or database lock
        pass
    
    # Check if likes table exists
    table_exists = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='likes'").fetchone()
    
    # Get likes count and check if user has liked it
    likes_count = 0
    has_liked = False
    
    if table_exists:
        likes_count = conn.execute('SELECT COUNT(*) FROM likes WHERE image_id = ?', (image_id,)).fetchone()[0]
        
        if 'user_id' in session:
            has_liked = conn.execute('SELECT 1 FROM likes WHERE image_id = ? AND user_id = ?', 
                                  (image_id, session['user_id'])).fetchone() is not None
    
    conn.close()
    
    return render_template('image_detail.html', image=image, likes_count=likes_count, has_liked=has_liked)

@app.route('/like_image/<int:image_id>', methods=['POST'])
def like_image(image_id):
    if 'user_id' not in session:
        flash('Please log in to like images')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO likes (user_id, image_id) VALUES (?, ?)', 
                   (session['user_id'], image_id))
        conn.commit()
    except sqlite3.IntegrityError:
        # User already liked this image
        pass
    finally:
        conn.close()
    
    return redirect(url_for('image', image_id=image_id))

@app.route('/unlike_image/<int:image_id>', methods=['POST'])
def unlike_image(image_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM likes WHERE user_id = ? AND image_id = ?', 
               (session['user_id'], image_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('image', image_id=image_id))

@app.route('/delete_image/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to delete images')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Check if image exists and belongs to the current user
    image = conn.execute('SELECT * FROM images WHERE id = ? AND user_id = ?', 
                       (image_id, session['user_id'])).fetchone()
    
    if not image:
        flash('Image not found or you do not have permission to delete it')
        return redirect(url_for('index'))
    
    # Get the filename to delete the file
    filename = image['filename']
    
    # Delete image from database
    conn.execute('DELETE FROM images WHERE id = ?', (image_id,))
    
    # Delete associated likes
    cursor = conn.cursor()
    table_exists = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='likes'").fetchone()
    if table_exists:
        conn.execute('DELETE FROM likes WHERE image_id = ?', (image_id,))
    
    conn.commit()
    conn.close()
    
    # Delete the actual file
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    flash('Image deleted successfully')
    return redirect(url_for('index'))

@app.route('/edit_image/<int:image_id>', methods=['GET', 'POST'])
def edit_image(image_id):
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Please log in to edit images')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Check if image exists and belongs to the current user
    image = conn.execute('SELECT * FROM images WHERE id = ? AND user_id = ?', 
                       (image_id, session['user_id'])).fetchone()
    
    if not image:
        flash('Image not found or you do not have permission to edit it')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        tags = request.form.get('tags', '')
        
        conn.execute('UPDATE images SET title = ?, description = ?, tags = ? WHERE id = ?',
                   (title, description, tags, image_id))
        conn.commit()
        conn.close()
        
        flash('Image updated successfully')
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
    parser = argparse.ArgumentParser(description='Run the Flask app')
    parser.add_argument('--host', default='127.0.0.1', help='Host to run the app on')
    parser.add_argument('--port', type=int, default=5002, help='Port to run the app on')
    args = parser.parse_args()
    
    # Print sample image URLs for testing
    conn = get_db_connection()
    images = conn.execute('SELECT id, filename FROM images LIMIT 3').fetchall()
    conn.close()
    
    if images:
        for img in images:
            app.logger.info(f"Test image URL (browser): http://{args.host}:{args.port}/static/uploads/{img['filename']}")
    else:
        app.logger.warning("No images found in database to test URLs")
    
    app.run(debug=True, host=args.host, port=args.port) 