# CloudLibrary - Teammate AWS Deployment & Handover Guide

> **Project:** CloudLibrary (College Cloud Computing Project)  
> **Tech Stack:** Python 3.9+ Flask, Gunicorn WSGI, MySQL 8 (Amazon RDS), Neumorphic Soft-UI Frontend  
> **Target Cloud:** AWS 3-Tier Architecture (ALB &rarr; EC2 ASG &rarr; RDS MySQL)

---

## 1. Quick Summary of Changes & Architecture
- **Soft-UI / Neumorphic Redesign:** Full modern redesign using `#e6e8ec` light-grey surface, dual light/dark shadows, `Unbounded` (headings) and `Manrope` (body) typography, live clock widget, circular utilization dial, and semantic status chips.
- **CSRF Protection:** Added session-based CSRF protection on all forms.
- **Zero-Config Local Fallback:** Automatically runs on SQLite (`library.db`) if local MySQL is absent, and seamlessly connects to Amazon RDS MySQL when `DB_HOST` is set.
- **ALB Health Probe:** Accessible at `/health` returning HTTP 200 and JSON.

---

## 2. Environment Variables (`.env`)
Create a `.env` file in the project root:
```ini
# Database Configuration (For AWS RDS deployment, paste your RDS Endpoint)
DB_HOST=your-rds-endpoint.c123456789.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=YourSecureRDSPassword123
DB_NAME=library_db

# Flask Security & Server Port
SECRET_KEY=college-cloud-library-secret-key-change-in-production-2026
PORT=5000
FLASK_DEBUG=0
```

---

## 3. How to Import `schema.sql` to Amazon RDS
Because Amazon RDS MySQL is inside private subnets, run this from your EC2 instance (or Bastion):
```bash
mysql -h <YOUR_RDS_ENDPOINT> -P 3306 -u admin -p library_db < schema.sql
```
*Note: `app.py` also contains self-healing automatic seed verification on startup (`admin` / `admin123` and `student1` / `student123`).*

---

## 4. Gunicorn WSGI & Systemd Service Commands

### Manual Run via Gunicorn (Port 5000):
```bash
gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
```

### Systemd Service Setup (Auto-starts on reboot):
1. Copy the service unit to systemd:
   ```bash
   sudo cp deploy/library.service /etc/systemd/system/library.service
   ```
2. Reload and enable daemon:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable library.service
   sudo systemctl restart library.service
   ```
3. Check service status and logs:
   ```bash
   sudo systemctl status library.service
   sudo journalctl -u library.service -n 50 --no-pager
   ```

---

## 5. Load Balancer & Health Check Verification
- **Health Check Path:** `/health`
- **Port:** `5000` (or `80` if using Nginx reverse proxy)
- **Success Code:** `200`
- **Test Command:**
  ```bash
  curl -i http://localhost:5000/health
  ```
  Expected Output:
  ```json
  {"status":"healthy","service":"Library Management System","database":"connected","engine":"mysql"}
  ```

---

## 6. Default Demo Accounts for Evaluation

| Role | Username | Password | Purpose |
|---|---|---|---|
| **Administrator** | `admin` | `admin123` | Full inventory control, edit/delete books, mark returns |
| **Student** | `student1` | `student123` | Borrow books, view active loans, test 14-day loan rules |
