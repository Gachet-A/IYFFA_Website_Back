# IYFFA Backend

This repository contains the backend of the IYFFA website, built with Django and MariaDB.

## Prerequisites

Ensure you have the following installed:

- Python (>=3.8)
- pip (Python package manager)
- MariaDB Server
- Git

## Installation Guide

### 1. Clone the Repository
```sh
git clone https://github.com/Gachet-A/IYFFA_Website_Back.git
cd IYFFA_Website_Back
```

### 2. Create a Virtual Environment and Activate It
```sh
# Windows
python -m venv backend_venv
backend_venv\Scripts\activate

# macOS/Linux
python3 -m venv backend_venv
source backend_venv/bin/activate
```

### 3. Install Dependencies
```sh
pip install -r requirements.txt
```

### 4. Create migration folder
- Create directory django_rest/migrations
- Create empty python file django_rest/migrations/__init__.py

### 5. Install and Configure MariaDB

#### Install MariaDB (if not installed)

- **Windows**: Download and install from [MariaDB official website](https://mariadb.org/download/)
- **Linux (Debian/Ubuntu)**:
  ```sh
  sudo apt update
  sudo apt install mariadb-server
  ```
- **macOS** (via Homebrew):
  ```sh
  brew install mariadb
  ```

#### Start MariaDB Service
```sh
# Linux/macOS
sudo systemctl start mariadb

# Windows (run in Command Prompt as Administrator)
net start MariaDB
```

#### Secure MariaDB Installation (Optional but Recommended)
```sh
sudo mysql_secure_installation
```
Follow the prompts to set a root password and remove insecure defaults.

### 6. Create the Database and User

#### Login to MariaDB
```sh
mysql -u root -p
```

#### Run the Following SQL Commands:
```sql
CREATE DATABASE iyffa_db;
CREATE USER 'iyffa_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON iyffa_db.* TO 'iyffa_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 7. Store Database Credentials in `.env` File

Create a `.env` file in the project root and add the following:
```ini
DB_NAME=iyffa_db
DB_USER=iyffa_user
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=3306
```

### 8. Apply Migrations
```sh
python manage.py migrate
```

### 9. Run the Development Server
```sh
python manage.py runserver
```

### 10. Access the API
- Open `http://127.0.0.1:8000/api/` in your browser or use **Postman** to test API endpoints.

## Notes
- Ensure MariaDB is running before starting the Django server.

---
**Maintainer:** Gachet-A
