# CloudLibrary - Book Lending Management System

> **College Cloud Computing Project**  
> A complete, beginner-friendly 3-tier web application built with **Python Flask**, **MySQL**, and **Bootstrap 5**, designed specifically for cloud deployment on **Amazon Web Services (AWS)** using an **Application Load Balancer (ALB)**, **EC2 Auto Scaling**, and **Amazon RDS MySQL**.

---

## 📌 Project Overview

This project was built for a college Cloud Computing course. One teammate focuses on application engineering while the other deploys and manages cloud infrastructure on AWS.

### Key Features

- **👨‍💼 Administrator Portal:**
  - Secure authentication with password hashing (`scrypt`/`pbkdf2`) and session management.
  - Complete Book CRUD: Add new titles, edit details, adjust inventory stock, and delete books with active-loan checks.
  - Issued Books Central Console: Real-time visibility into all active borrowings across students.
  - Process Returns: Mark returned books, automatically calculate overdue fines, and restock available copies.
  - Metrics Dashboard: Real-time stats on total titles, inventory copies, active loans, overdue items, registered students, and collected fines.

- **🎓 Student / Member Portal:**
  - Registration & Login with session state.
  - Interactive Catalog: Search by title, author, or ISBN, plus filter by category.
  - 1-Click Borrowing: 14-day borrowing duration with automatic due date computation.
  - Stock Guards: Prevents borrowing if available copies = 0 or if the student already holds an active copy.
  - Student Dashboard: Real-time countdowns (`X days remaining`), overdue indicators, and personal fine tracking.
  - Return books directly from personal dashboard.
  - Complete Borrowing History with timestamps, return dates, and late-fee breakdowns.

- **⚖️ Business Rules & Policy:**
  - Loan Period: **14 days** from issue date.
  - Overdue Fine: **Rs 5.00 per day** past the due date.
  - Availability Check: `available_copies` decrement on borrow and increment on return.

- **☁️ Cloud & Production Ready:**
  - `/health` endpoint returning HTTP 200 with JSON payload for AWS ALB health checking.
  - 100% environment-driven configuration via `.env` (no hardcoded credentials).
  - Production WSGI setup via **Gunicorn** and **Systemd** daemon auto-restart.
  - Automated EC2 bootstrap script (`user_data.sh`).

---

## 📂 Project Directory Structure

```
c:\Cloud_Project\
├── app.py                      # Core Flask web application (routes, auth, business logic)
├── requirements.txt            # Python dependencies (Flask, PyMySQL, Gunicorn, etc.)
├── schema.sql                  # MySQL database schema, foreign keys, indexes & seed data
├── .env.example                # Template for environment configuration
├── .gitignore                  # Ignore pycache, venv, and secret .env files
├── README.md                   # Project documentation & local testing guide
├── HANDOVER.md                 # One-page quick reference for your AWS deployment teammate
├── aws-deployment-guide.md     # Step-by-step AWS console deployment guide
│
├── deploy/                     # Cloud Deployment Automation
│   ├── library.service         # Systemd service unit for Gunicorn on EC2
│   ├── user_data.sh            # EC2 Bootstrap script for Launch Template / standalone EC2
│   └── nginx.conf              # Optional Nginx reverse proxy configuration
│
├── static/                     # Static UI Assets
│   ├── css/
│   │   └── neumorphic.css      # Premium Soft-UI design tokens, paired shadows & typography
│   └── js/
│       └── main.js             # Client helpers (live clock, alert fade, demo toggle)
│
└── templates/                  # Jinja2 HTML Templates
    ├── base.html               # Main base layout with responsive navigation & footer
    ├── index.html              # Public homepage with searchable book catalog & demo credentials
    ├── login.html              # Unified login page with 1-click demo fillers
    ├── register.html           # Student registration page
    ├── 404.html                # Friendly 404 error page
    ├── student/                # Student Portal Views
    │   ├── dashboard.html      # Active loans, overdue warnings, and return action
    │   ├── books.html          # Searchable catalog with instant borrow buttons
    │   └── history.html        # Complete personal borrowing history
    └── admin/                  # Administrator Views
        ├── dashboard.html      # KPI cards, cloud architecture status, recent activity
        ├── books.html          # Book catalog management (view, edit, delete)
        ├── add_book.html       # Add new book form
        ├── edit_book.html      # Edit existing book and inventory form
        └── issued_books.html   # Issued books table with filters and return actions
```

---

## 🏗️ AWS Cloud Architecture

The cloud deployment strictly follows a **3-Tier Highly Available Multi-AZ Architecture**:

```
                    Internet (Students & Admins)
                                 │
                                 ▼ [Port 80]
                    Internet Gateway (IGW)
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
        Public Subnet 1 (AZ-1a)      Public Subnet 2 (AZ-1b)
        Application Load Balancer    Application Load Balancer
        NAT Gateway (+Elastic IP)
                   │                           │
                   └─────────────┬─────────────┘
                                 ▼ [Port 5000: Health Check on /health]
                   ┌───────────────────────────┐
                   ▼                           ▼
        Private App Subnet 1 (AZ-1a) Private App Subnet 2 (AZ-1b)
        EC2 Instance 1 (Flask)       EC2 Instance 2 (Flask)
        (No Public IP)               (No Public IP)
                   │                           │
                   └─────────────┬─────────────┘
                                 ▼ [MySQL Port 3306]
                   ┌───────────────────────────┐
                   ▼                           ▼
        Private DB Subnet 1 (AZ-1a)  Private DB Subnet 2 (AZ-1b)
        └────────────── Amazon RDS MySQL Instance ─────────────┘
```

- **VPC CIDR:** `10.0.0.0/16`
- **2 Public Subnets:** `10.0.1.0/24` (AZ-a) and `10.0.2.0/24` (AZ-b) for ALB and NAT Gateway.
- **2 Private App Subnets:** `10.0.11.0/24` (AZ-a) and `10.0.12.0/24` (AZ-b) for EC2 Flask instances.
- **2 Private DB Subnets:** `10.0.21.0/24` (AZ-a) and `10.0.22.0/24` (AZ-b) for Amazon RDS MySQL.
- **Security Group Isolation:**
  - `ALB-SG`: Inbound HTTP `80` from `0.0.0.0/0`.
  - `EC2-SG`: Inbound TCP `5000` **only from `ALB-SG`**.
  - `RDS-SG`: Inbound TCP `3306` **only from `EC2-SG`**.

> 📖 **Full deployment guide:** Give [aws-deployment-guide.md](file:///c:/Cloud_Project/aws-deployment-guide.md) to your teammate for the exact AWS Console walkthrough.

---

## 💻 How to Run Locally (Before AWS Deployment)

### 1. Prerequisites
- Python 3.9+ installed
- MySQL 8.0+ running locally (or via Docker / XAMPP)

### 2. Setup Database
Open MySQL terminal or MySQL Workbench and run:
```bash
mysql -u root -p < schema.sql
```
This creates the `library_db` database, tables, and inserts sample books and users.

### 3. Create Python Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / Mac
cp .env.example .env
```
Edit `.env` and set your local MySQL password:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=library_db
SECRET_KEY=college-cloud-library-secret-key-change-in-production-2026
PORT=5000
FLASK_DEBUG=1
```

### 6. Run the Application
```bash
python app.py
```
Open your browser and visit: **`http://localhost:5000`**

---

## 🔑 Default Seed Credentials for Demo & Testing

| Role | Username | Password | Notes |
|---|---|---|---|
| **Administrator** | `admin` | `admin123` | Full inventory control & loan management |
| **Student** | `student1` | `student123` | Sample student with pre-seeded active & overdue loans |

*(You can also register brand new student accounts directly from the Register page).*

---

## 🧪 Testing the ALB Health Probe

Run in your browser or terminal:
```bash
curl http://localhost:5000/health
```
Output:
```json
{
  "database": "connected",
  "service": "Library Management System",
  "status": "healthy",
  "timestamp": "2026-10-19T14:30:00Z"
}
```
This endpoint responds with HTTP 200, which satisfies AWS Application Load Balancer health check requirements.

---

## 🎓 College Presentation Highlights

When demonstrating this project to professors and evaluators, highlight:
1. **Cloud Security:** Application instances are in private subnets with **no public IPs**. Database is strictly private.
2. **High Availability:** Instances and database subnets span **2 separate Availability Zones** (`us-east-1a` and `us-east-1b`).
3. **Decoupling:** Separation of presentation layer (Bootstrap 5), application layer (Gunicorn + Flask), and persistent data tier (RDS MySQL).
4. **Resilience & Auto Scaling:** Auto Scaling Group automatically replaces unhealthy instances and scales up under traffic surges.
5. **Observability:** Centralized logging in `/var/log/library_access.log` and automated health checks on `/health`.
