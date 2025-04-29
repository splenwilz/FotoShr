# FotoShr

FotoShr is an image gallery platform that allows users to showcase their images.

## Features

- User registration and authentication
- Image upload with title, description, and tags
- Image gallery with responsive layout
- Search and filtering capabilities
- Individual image view

## Setup Instructions

1. Clone the repository
2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the application:
   ```
   python app.py
   ```
5. Open a web browser and navigate to http://127.0.0.1:5000

## Tests

The application includes both unit tests and integration tests to ensure functionality works as expected.

### Running Tests

1. Make sure you have installed the testing dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run all tests:
   ```
   pytest tests/
   ```

3. Run specific test categories:
   ```
   # Unit tests only
   pytest tests/unit/

   # Integration tests only
   pytest tests/integration/
   ```

4. Run tests with verbose output:
   ```
   pytest tests/ -v
   ```

### Test Coverage

The tests cover:
- Core functionality: Database operations, image uploads, user authentication
- Route testing: Ensuring all endpoints return expected responses
- UI components: Verifying that UI elements are present and functioning
- User flows: Testing complete user journeys like registration, login, and image upload

### Test Categories

#### Unit Tests
- `test_database.py`: Tests database connectivity and schema integrity
- `test_routes.py`: Tests core route functionality and access control

#### Integration Tests
- `test_ui_components.py`: Tests UI components across different parts of the application
- `test_user_flows.py`: Tests user journeys like registration and search

## Project Structure

```
FotoShr/
├── app/
│   ├── static/
│   │   ├── css/         # Stylesheets
│   │   ├── js/          # JavaScript files
│   │   ├── img/         # Static images (logos, icons)
│   │   └── uploads/     # User uploaded images
│   └── templates/       # HTML templates
├── tests/
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── conftest.py      # Test configuration
├── app.py               # Main application file
├── requirements.txt     # Project dependencies
└── README.md            # This file
```

## Usage

1. Register a new account
2. Log in with your credentials
3. Upload images with titles, descriptions, and tags
4. Browse the gallery
5. Search for images by title, description, or tags

## Technologies Used

- Flask (Python web framework)
- SQLite (Database)
- HTML/CSS/JavaScript (Frontend)
- Bootstrap (Responsive design)
- pytest (Testing framework) 