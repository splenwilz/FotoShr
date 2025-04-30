# FotoShr - Image Sharing Platform

FotoShr is a web application for sharing and managing images, built with Flask and optimized for cloud deployment.

## Features

- User authentication (login/register)
- Upload and manage images
- Like and comment on images
- Search for images
- User profiles
- AWS S3 integration for image storage
- PostgreSQL database support

## Setup

### Prerequisites

- Docker and Docker Compose
- AWS account (for S3 storage)
- AWS CLI configured with appropriate credentials

### Running with Docker

1. Clone the repository:
   ```
   git clone <repository-url>
   cd FotoShr
   ```

2. Create a `.env` file:
   ```
   cp .env.template .env
   ```

3. Edit the `.env` file to configure your environment:
   - For local development, you can leave the defaults
   - For production, set `SECRET_KEY` to a secure value
   - For AWS integration, set `USE_S3=True` and configure the AWS settings

4. Build and run with Docker Compose:
   ```
   docker-compose up --build
   ```

5. Access the application at http://localhost:5000

### Running without Docker

1. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # OR
   .venv\Scripts\activate     # Windows
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file:
   ```
   cp .env.template .env
   ```

4. Edit the `.env` file as needed

5. Run the application:
   ```
   python app.py
   ```

## AWS Configuration

This application integrates with AWS services for cloud deployment:

### S3 Configuration

To use AWS S3 for image storage:

1. Create an S3 bucket for your images
2. Configure your environment variables:
   ```
   USE_S3=True
   AWS_S3_BUCKET=your-bucket-name
   AWS_REGION=your-region
   ```

3. AWS credentials should be configured using one of these methods:
   - AWS profiles in the shared credentials file (~/.aws/credentials)
   - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
   - IAM Role (if running on EC2)

4. With S3 enabled, images will be:
   - Uploaded directly to S3
   - Accessible via pre-signed URLs
   - Automatically deleted from S3 when removed from the application

### IAM Configuration

The application requires IAM permissions for:

- S3 bucket operations (GET, PUT, DELETE)
- Generate pre-signed URLs

Create an IAM policy with the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    }
  ]
}
```

## PostgreSQL Configuration

To use PostgreSQL instead of SQLite:

1. Set the following environment variables:
   ```
   USE_POSTGRES=True
   POSTGRES_HOST=your-postgres-host
   POSTGRES_PORT=5432
   POSTGRES_USER=your-username
   POSTGRES_PASSWORD=your-password
   POSTGRES_DB=your-database
   ```

2. If using Docker Compose, the PostgreSQL service is already configured in the docker-compose.yml file.

3. For AWS RDS deployment:
   - Create a PostgreSQL RDS instance
   - Update the connection parameters in your environment variables
   - Ensure your security groups allow traffic from your application

## Docker Deployment

The application is containerized for easy deployment:

1. Dockerfile features:
   - Multi-stage build for efficiency
   - Python 3.9 base image
   - Proper handling of dependencies
   - Non-root user for security

2. Docker Compose setup:
   - Application container
   - PostgreSQL database container
   - Volume mapping for persistent storage
   - Environment variable configuration

3. Environmental configuration:
   - Database connections auto-configured based on environment
   - S3 integration enabled/disabled based on environment
   - Proper error handling for deployment scenarios

## License

MIT

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

## Project Structure

```
FotoShr/
├── app/
│   ├── static/
│   │   ├── css/         # Stylesheets
│   │   ├── js/          # JavaScript files
│   │   ├── img/         # Static images (logos, icons)
│   │   └── uploads/     # User uploaded images (when not using S3)
│   └── templates/       # HTML templates
├── tests/
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── conftest.py      # Test configuration
├── app.py               # Main application file
├── Dockerfile           # Container definition
├── docker-compose.yml   # Multi-container setup
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
- PostgreSQL / SQLite (Database)
- AWS S3 (Cloud storage)
- Docker (Containerization)
- Bootstrap (Responsive design)
- HTML/CSS/JavaScript (Frontend)
- pytest (Testing framework) 