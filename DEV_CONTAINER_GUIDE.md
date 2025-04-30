# FotoShr Dev Container Guide

This guide will help you set up and use the development container for FotoShr.

## Prerequisites

1. Install [Visual Studio Code](https://code.visualstudio.com/)
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
3. Install the [Remote - Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension for VS Code

## Getting Started

### Open the Project in a Dev Container

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd FotoShr
   ```

2. Open the project in VS Code:
   ```bash
   code .
   ```

3. When prompted "Folder contains a Dev Container configuration file. Reopen folder to develop in a container", click "Reopen in Container".

   Or:
   
   - Press F1 to open the command palette
   - Type "Remote-Containers: Reopen in Container" and select it

4. VS Code will build the dev container (this may take a few minutes the first time).

5. Once the container is built, you'll be working inside the containerized environment.

## Using the Dev Container

### Running the Application

You can run the application in several ways:

1. **Using VS Code Tasks**:
   - Press `Ctrl+Shift+B` (or `Cmd+Shift+B` on macOS) to run the default build task
   - Or open the Command Palette (`F1`) and select "Tasks: Run Task", then choose "Run Flask Application"

2. **Using the Terminal**:
   - Open a terminal in VS Code (`` Ctrl+` `` or Terminal > New Terminal)
   - Run `python app.py --host 0.0.0.0 --port 5000 --debug`

3. **Using the Debug Configuration**:
   - Go to the Run and Debug view (`Ctrl+Shift+D` or `Cmd+Shift+D` on macOS)
   - Select "Python: Debug App" from the dropdown
   - Press the green Play button or F5

### PostgreSQL Database

The development environment includes a PostgreSQL database:

- **Host**: `db`
- **Port**: `5432`
- **Username**: `postgres`
- **Password**: `postgres`
- **Database**: `fotoshr`

You can connect to it using the SQLTools extension that's included in the dev container.

### AWS S3 Integration

To test the S3 integration locally:

1. Create a `.env` file from the template:
   ```bash
   cp .env.template .env
   ```

2. Edit the `.env` file to add your AWS credentials and bucket information:
   ```
   USE_S3=True
   AWS_S3_BUCKET=your-bucket-name
   AWS_REGION=your-region
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   ```

### Available VS Code Tasks

Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS) and type "Tasks: Run Task" to see the available tasks:

- **Run Flask Application**: Starts the Flask app
- **Run Tests**: Runs the test suite
- **Format Code (Black)**: Formats the code using Black
- **Lint Code (Pylint)**: Lints the code using Pylint
- **Generate Secret Key**: Generates a new secret key for Flask

## Debugging

When running with the "Python: Debug App" configuration, you can:

- Set breakpoints by clicking in the gutter (left margin of the code)
- Inspect variables in the "VARIABLES" panel
- Step through code execution using the debug toolbar

## Notes and Tips

1. **Container Persistence**: The database data is persisted through a Docker volume, so your data will remain even if you stop and restart the container.

2. **Container Performance**: The container is configured to optimize performance, especially on macOS and Windows by using the `:cached` volume mount option.

3. **Adding Dependencies**: If you add new Python dependencies, you'll need to rebuild the container:
   - Press F1 and type "Remote-Containers: Rebuild Container"

4. **Accessing the Application**: You can access the app in your browser at http://localhost:5000

5. **Editing Files**: Any changes you make to the code will be automatically reflected inside the container due to the volume mapping.

6. **Stopping the Dev Container**: When you're done working, you can stop the container by closing VS Code or using the "Remote-Containers: Close Remote Connection" command. 