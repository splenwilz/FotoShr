import os
import tempfile
import pytest
from app import app
import sqlite3
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()
    app.config['DATABASE'] = db_path
    app.config['TESTING'] = True
    app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing

    # Create the database and tables
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Create the users table
    conn.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Create the images table
    conn.execute('''
        CREATE TABLE images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            user_id INTEGER NOT NULL,
            upload_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            views INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create a test user with proper password hash
    hashed_password = generate_password_hash('testpassword')
    conn.execute(
        'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
        ('test_user', 'test@example.com', hashed_password)
    )
    
    # Create some test images
    conn.execute(
        'INSERT INTO images (filename, title, description, tags, user_id, upload_date) VALUES (?, ?, ?, ?, ?, ?)',
        ('test1.jpg', 'Test Image 1', 'Test description 1', 'nature,test', 1, '2023-01-01 00:00:00')
    )
    conn.execute(
        'INSERT INTO images (filename, title, description, tags, user_id, upload_date) VALUES (?, ?, ?, ?, ?, ?)',
        ('test2.jpg', 'Test Image 2', 'Test description 2', 'portrait,test', 1, '2023-01-02 00:00:00')
    )
    conn.execute(
        'INSERT INTO images (filename, title, description, tags, user_id, upload_date, views) VALUES (?, ?, ?, ?, ?, ?, ?)',
        ('test3.jpg', 'Test Image 3', 'Test description 3', 'architecture,test', 1, '2023-01-03 00:00:00', 5)
    )
    
    conn.commit()
    
    # Store the connection for testing functions to use
    app.config['DATABASE_CONNECTION'] = conn

    with app.test_client() as client:
        yield client

    # Close and clean up
    conn.close()
    os.close(db_fd)
    os.unlink(db_path)
    # Clean up the uploads folder
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        os.rmdir(app.config['UPLOAD_FOLDER'])

@pytest.fixture
def auth(client):
    """Authentication helper fixture to log in/out during tests"""
    class AuthActions:
        def login(self, username='test_user', password='testpassword'):
            return client.post(
                '/login',
                data={'username': username, 'password': password}
            )

        def logout(self):
            return client.get('/logout')

    return AuthActions() 