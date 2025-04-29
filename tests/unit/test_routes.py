import pytest
from flask import session
import io

def test_index(client):
    """Test the index route"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'FotoShr' in response.data

def test_login(client):
    """Test login functionality"""
    # Login page loads
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Sign In' in response.data or b'Login' in response.data
    
    # Login with correct credentials should at least return a 200 status code
    response = client.post(
        '/login',
        data={'username': 'test_user', 'password': 'testpassword'},
        follow_redirects=True
    )
    assert response.status_code == 200

def test_login_invalid(client):
    """Test login with invalid credentials"""
    response = client.post(
        '/login',
        data={'username': 'wrong', 'password': 'wrong'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data or b'Invalid credentials' in response.data
    
    # Session should not have user_id
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

def test_logout(client, auth):
    """Test logout functionality"""
    auth.login()
    
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    
    # Check session after logout
    with client.session_transaction() as sess:
        assert 'user_id' not in sess

def test_search(client):
    """Test search functionality"""
    # Basic search should return results
    response = client.get('/search?query=Test')
    assert response.status_code == 200
    
    # Search page should have the right elements
    assert b'Image Search' in response.data
    assert b'search-input' in response.data
    assert b'filter-sidebar' in response.data

def test_search_with_filters(client):
    """Test search with filters"""
    # Search with filters should work and have filter elements
    response = client.get('/search?query=Test&categories=portrait')
    assert response.status_code == 200
    assert b'Categories' in response.data
    assert b'Upload Date' in response.data
    assert b'Search In' in response.data

def test_image_detail(client):
    """Test viewing image details"""
    response = client.get('/image/1')
    assert response.status_code == 200
    # Image detail page should have basic elements
    assert b'image-container' in response.data
    assert b'img-fluid' in response.data
    
    # Non-existent image should redirect
    response = client.get('/image/999', follow_redirects=True)
    assert b'Image not found' in response.data

def test_upload_access_control(client):
    """Test that upload requires login"""
    # Should redirect when not logged in
    response = client.get('/upload', follow_redirects=True)
    assert b'Login' in response.data or b'Sign In' in response.data
    
    # Should redirect POST as well
    response = client.post('/upload', follow_redirects=True)
    assert b'Login' in response.data or b'Sign In' in response.data 