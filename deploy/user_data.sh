#!/bin/bash
# ==============================================================================
# EC2 User Data Bootstrap Script for CloudLibrary Application
# Target OS: Ubuntu 22.04 LTS (x86_64 or ARM64)
# ==============================================================================
set -e
exec > >(tee /var/log/user_data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "=================================================="
echo "Starting CloudLibrary EC2 Bootstrap..."
echo "=================================================="

# 1. Update OS packages
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

# 2. Install Python 3, pip, venv, git, and MySQL client
apt-get install -y python3 python3-pip python3-venv git mysql-client curl

# 3. Define App Directory & User
APP_DIR="/home/ubuntu/library-system"
APP_USER="ubuntu"

# 4. Create App Directory
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# 5. Fetch code: Replace with your actual GitHub repository URL
# If your repo is public:
REPO_URL="https://github.com/your-username/cloud-library-system.git"

if [ ! -d "$APP_DIR/.git" ]; then
    echo "Cloning repository from $REPO_URL..."
    # If using git:
    git clone "$REPO_URL" "$APP_DIR" || {
        echo "Git clone failed or repo placeholder not updated yet."
        echo "Falling back to local setup..."
    }
fi

# 6. Set up Python Virtual Environment
echo "Setting up Python virtual environment..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
if [ -f "$APP_DIR/requirements.txt" ]; then
    "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
else
    # Fallback install if requirements.txt was not yet pulled
    "$APP_DIR/venv/bin/pip" install Flask==3.0.3 PyMySQL==1.1.0 cryptography==42.0.5 python-dotenv==1.0.1 gunicorn==22.0.0 Werkzeug==3.0.3
fi

# 7. Create .env configuration file
# IMPORTANT: Replace these values with your actual RDS Endpoint and database credentials!
cat << 'EOF' > "$APP_DIR/.env"
DB_HOST=YOUR_RDS_ENDPOINT_HERE.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=YourSecureRDSMasterPassword123
DB_NAME=library_db
SECRET_KEY=college-cloud-library-secret-key-change-in-production-2026
PORT=5000
FLASK_DEBUG=0
EOF

# 8. Set up Systemd Service
echo "Configuring systemd service..."
cat << 'EOF' > /etc/systemd/system/library.service
[Unit]
Description=Gunicorn instance to serve CloudLibrary Flask Application
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/library-system
EnvironmentFile=/home/ubuntu/library-system/.env
ExecStart=/home/ubuntu/library-system/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 --access-logfile /var/log/library_access.log --error-logfile /var/log/library_error.log app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 9. Set permissions
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
touch /var/log/library_access.log /var/log/library_error.log
chown "$APP_USER:$APP_USER" /var/log/library_*.log

# 10. Reload systemd and start application
systemctl daemon-reload
systemctl enable library.service
systemctl restart library.service

echo "=================================================="
echo "CloudLibrary Bootstrap Completed Successfully!"
echo "Service status:"
systemctl status library.service --no-pager
echo "Testing local /health endpoint:"
curl -i http://127.0.0.1:5000/health || true
echo "=================================================="
