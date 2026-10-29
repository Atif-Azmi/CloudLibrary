import os
import sqlite3
import secrets
import time
import pymysql
import pymysql.cursors
from datetime import date, datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default-cloud-project-secret-key-2026")

# Database configuration from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "library_db")
DB_TYPE = os.getenv("DB_TYPE", "auto").lower()

# Business rules constants
LATE_FEE_PER_DAY = 5.0  # Rs 5 per day late fee
DEFAULT_BORROW_DAYS = 14  # 14 days borrowing period

# Active database engine tracking ('mysql' or 'sqlite')
ACTIVE_DB_ENGINE = "mysql"
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.db")


# ==========================================================
# CSRF PROTECTION HELPERS
# ==========================================================
def get_csrf_token():
    """Generates or retrieves CSRF token from current session."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


@app.context_processor
def inject_csrf_token():
    """Makes csrf_token() directly callable in all Jinja templates."""
    return dict(csrf_token=get_csrf_token)


def validate_csrf():
    """Validates the CSRF token from the POST request against the session."""
    token = request.form.get('csrf_token')
    expected_token = session.get('csrf_token')
    if not token or not expected_token or not secrets.compare_digest(token, expected_token):
        return False
    return True


# ==========================================================
# DATABASE ABSTRACTION & RESILIENT CONNECTION
# ==========================================================
class SQLiteCursorWrapper:
    """Wrapper around sqlite3 cursor to emulate PyMySQL DictCursor with %s placeholders."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        sqlite_query = query.replace("%s", "?")
        if params is not None:
            converted_params = []
            for p in params:
                if isinstance(p, (date, datetime)):
                    converted_params.append(str(p))
                else:
                    converted_params.append(p)
            return self._cursor.execute(sqlite_query, converted_params)
        return self._cursor.execute(sqlite_query)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return self._convert_row(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [self._convert_row(r) for r in rows]

    def _convert_row(self, row):
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, str) and (k.endswith('_date') or k in ('due_date', 'issue_date', 'return_date')):
                try:
                    d[k] = datetime.strptime(v, '%Y-%m-%d').date()
                except Exception:
                    pass
        return d

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cursor.close()

    def close(self):
        self._cursor.close()


class SQLiteConnectionWrapper:
    """Wrapper around sqlite3 connection to emulate PyMySQL connection interface."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return SQLiteCursorWrapper(self._conn.cursor())

    def close(self):
        self._conn.close()

    def commit(self):
        self._conn.commit()


def init_sqlite_schema(conn):
    """Initializes tables and seeds in SQLite if MySQL is not available."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        isbn TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        total_copies INTEGER NOT NULL DEFAULT 1,
        available_copies INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS borrow_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        issue_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        return_date TEXT,
        fine_amount REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'borrowed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
    )
    """)
    conn.commit()

    # Seed initial accounts if empty
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        admin_hash = generate_password_hash('admin123')
        student_hash = generate_password_hash('student123')
        cur.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, 'admin')",
                    ('admin', 'admin@college.edu', admin_hash, 'System Administrator'))
        cur.execute("INSERT INTO users (username, email, password_hash, full_name, role) VALUES (?, ?, ?, ?, 'student')",
                    ('student1', 'student1@college.edu', student_hash, 'Aarav Sharma'))
        conn.commit()

    # Seed initial books if empty
    cur.execute("SELECT COUNT(*) FROM books")
    if cur.fetchone()[0] == 0:
        books_data = [
            ('Cloud Computing: Concepts, Technology & Architecture', 'Thomas Erl, Ricardo Puttini', '978-0133387520', 'Cloud Computing', 5, 4),
            ('Designing Data-Intensive Applications', 'Martin Kleppmann', '978-1449373320', 'Database Systems', 4, 3),
            ('Clean Code: A Handbook of Agile Software Craftsmanship', 'Robert C. Martin', '978-0132350884', 'Software Engineering', 6, 6),
            ('Operating System Concepts', 'Abraham Silberschatz, Peter B. Galvin', '978-1119800361', 'Operating Systems', 4, 4),
            ('Computer Networking: A Top-Down Approach', 'James Kurose, Keith Ross', '978-0136681557', 'Computer Networks', 3, 3),
            ('Introduction to Algorithms (CLRS)', 'Thomas H. Cormen, Charles E. Leiserson', '978-0262046305', 'Algorithms', 5, 5),
            ('Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow', 'Aurélien Géron', '978-1492032649', 'Artificial Intelligence', 3, 3),
            ('Site Reliability Engineering', 'Betsy Beyer, Chris Jones', '978-1491929124', 'DevOps & Cloud', 4, 4)
        ]
        cur.executemany("INSERT INTO books (title, author, isbn, category, total_copies, available_copies) VALUES (?, ?, ?, ?, ?, ?)", books_data)

        today = date.today()
        cur.execute("INSERT INTO borrow_records (user_id, book_id, issue_date, due_date, return_date, fine_amount, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (2, 1, str(today - timedelta(days=5)), str(today + timedelta(days=9)), None, 0.0, 'borrowed'))
        cur.execute("INSERT INTO borrow_records (user_id, book_id, issue_date, due_date, return_date, fine_amount, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (2, 2, str(today - timedelta(days=20)), str(today - timedelta(days=6)), None, 30.0, 'overdue'))
        conn.commit()
    cur.close()


def get_db_connection():
    """
    Establishes database connection with resilient retry logic:
    - Retries MySQL up to 2 times for transient network/RDS hiccups.
    - Seamlessly falls back to SQLite (library.db) for effortless local testing.
    """
    global ACTIVE_DB_ENGINE

    if DB_TYPE == "sqlite":
        ACTIVE_DB_ENGINE = "sqlite"
        raw_conn = sqlite3.connect(SQLITE_DB_PATH, timeout=10)
        raw_conn.row_factory = sqlite3.Row
        init_sqlite_schema(raw_conn)
        return SQLiteConnectionWrapper(raw_conn)

    last_error = None
    # Attempt MySQL connection (with 2 retries for production resilience)
    for attempt in range(2):
        try:
            conn = pymysql.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=2
            )
            ACTIVE_DB_ENGINE = "mysql"
            return conn
        except Exception as e:
            last_error = e
            time.sleep(0.2)

    # If MySQL is not reachable, fall back to SQLite for local development
    ACTIVE_DB_ENGINE = "sqlite"
    raw_conn = sqlite3.connect(SQLITE_DB_PATH, timeout=10)
    raw_conn.row_factory = sqlite3.Row
    init_sqlite_schema(raw_conn)
    return SQLiteConnectionWrapper(raw_conn)


# ==========================================================
# BUSINESS LOGIC & CALCULATION HELPERS
# ==========================================================
def calculate_fine(due_date, return_date=None):
    """
    Calculates fine based on Rs 5 per day after due date.
    - If book is returned: fine is based on return_date - due_date.
    - If book is still out: fine is based on today - due_date.
    """
    reference_date = return_date if return_date else date.today()
    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()
    if isinstance(due_date, datetime):
        due_date = due_date.date()

    if reference_date > due_date:
        days_late = (reference_date - due_date).days
        return round(days_late * LATE_FEE_PER_DAY, 2)
    return 0.0


def update_overdue_statuses(cursor):
    """Updates status and calculated fine for overdue unreturned records."""
    today = date.today()
    cursor.execute("""
        SELECT id, due_date FROM borrow_records
        WHERE status = 'borrowed' AND due_date < %s
    """, (today,))
    overdue_records = cursor.fetchall()

    for rec in overdue_records:
        fine = calculate_fine(rec['due_date'])
        cursor.execute("""
            UPDATE borrow_records
            SET status = 'overdue', fine_amount = %s
            WHERE id = %s
        """, (fine, rec['id']))


def init_db_seeds():
    """Ensures admin and student seed users exist on database startup."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = 'admin'")
            admin = cursor.fetchone()
            if not admin:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s, 'admin')
                """, (
                    'admin',
                    'admin@college.edu',
                    generate_password_hash('admin123'),
                    'System Administrator'
                ))

            cursor.execute("SELECT id FROM users WHERE username = 'student1'")
            student = cursor.fetchone()
            if not student:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s, 'student')
                """, (
                    'student1',
                    'student1@college.edu',
                    generate_password_hash('student123'),
                    'Aarav Sharma'
                ))
        conn.close()
    except Exception as e:
        print(f"[Notice] DB init skipped or not yet available: {e}")


# ==========================================================
# AUTH DECORATORS (ROLE-BASED ACCESS CONTROL)
# ==========================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'admin':
            flash("Access denied. Administrator privileges required.", "danger")
            return redirect(url_for('student_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'student':
            flash("Redirected to administrator portal.", "info")
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ==========================================================
# HEALTH CHECK ENDPOINT (ALB & DevOps Monitoring)
# ==========================================================
@app.route('/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM users LIMIT 1")
        conn.close()

        return jsonify({
            "status": "healthy",
            "service": "Library Management System",
            "database": "connected",
            "engine": ACTIVE_DB_ENGINE,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 200
    except Exception:
        return jsonify({
            "status": "unhealthy",
            "service": "Library Management System",
            "database": "disconnected",
            "engine": ACTIVE_DB_ENGINE,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 503


# ==========================================================
# PUBLIC CATALOG & AUTHENTICATION
# ==========================================================
@app.route('/')
def index():
    """Home / Public catalog showing books, search, and category pills."""
    search_query = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()

    books = []
    categories = []
    stats = {"total_titles": 0, "available_books": 0}

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT category FROM books ORDER BY category ASC")
            categories = [row['category'] for row in cursor.fetchall()]

            sql = "SELECT * FROM books WHERE 1=1"
            params = []
            if search_query:
                sql += " AND (title LIKE %s OR author LIKE %s OR isbn LIKE %s)"
                term = f"%{search_query}%"
                params.extend([term, term, term])
            if category:
                sql += " AND category = %s"
                params.append(category)

            sql += " ORDER BY id DESC"
            cursor.execute(sql, tuple(params))
            books = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) as titles, SUM(available_copies) as available FROM books")
            stat_res = cursor.fetchone()
            if stat_res:
                stats['total_titles'] = stat_res['titles'] or 0
                stats['available_books'] = stat_res['available'] or 0
        conn.close()
    except Exception as e:
        flash(f"Database error while loading catalog: {e}", "danger")

    return render_template('index.html', books=books, categories=categories,
                           search=search_query, selected_category=category, stats=stats)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Student registration page with CSRF validation."""
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('role') == 'admin' else 'student_dashboard'))

    if request.method == 'POST':
        if not validate_csrf():
            flash("Session expired or invalid security token. Please try again.", "danger")
            return render_template('register.html')

        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not email or not full_name or not password:
            flash("All fields are required.", "danger")
            return render_template('register.html')

        if len(username) < 3:
            flash("Username must be at least 3 characters long.", "danger")
            return render_template('register.html')

        if '@' not in email or '.' not in email:
            flash("Please enter a valid email address.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('register.html')

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('register.html')

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
                existing = cursor.fetchone()
                if existing:
                    flash("Username or email already registered. Please sign in.", "warning")
                    conn.close()
                    return redirect(url_for('login'))

                password_hash = generate_password_hash(password)
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s, 'student')
                """, (username, email, password_hash, full_name))
            conn.close()

            flash("Registration successful! You can now sign in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Registration failed: {e}", "danger")

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Unified login for students and administrators with CSRF validation."""
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard' if session.get('role') == 'admin' else 'student_dashboard'))

    if request.method == 'POST':
        if not validate_csrf():
            flash("Session expired or invalid security token. Please try again.", "danger")
            return render_template('login.html')

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template('login.html')

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, username))
                user = cursor.fetchone()
            conn.close()

            if user and check_password_hash(user['password_hash'], password):
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['full_name'] = user['full_name']
                session['role'] = user['role']
                get_csrf_token()  # regenerate token for newly authenticated session

                flash(f"Welcome back, {user['full_name']}!", "success")
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)

                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('student_dashboard'))
            else:
                flash("Invalid username or password.", "danger")
        except Exception as e:
            flash(f"Login error: {e}", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logs the user out and clears the session."""
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('login'))


# ==========================================================
# STUDENT PORTAL ROUTES
# ==========================================================
@app.route('/student/dashboard')
@student_required
def student_dashboard():
    """Student dashboard with active loans and live stat tiles."""
    user_id = session['user_id']
    active_borrows = []
    stats = {"active_count": 0, "overdue_count": 0, "total_fines": 0.0}

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            update_overdue_statuses(cursor)

            cursor.execute("""
                SELECT br.*, b.title, b.author, b.isbn, b.category
                FROM borrow_records br
                JOIN books b ON br.book_id = b.id
                WHERE br.user_id = %s AND br.return_date IS NULL
                ORDER BY br.due_date ASC
            """, (user_id,))
            active_borrows = cursor.fetchall()

            today = date.today()
            for item in active_borrows:
                due_d = item['due_date']
                item['is_overdue'] = today > due_d
                item['days_remaining'] = (due_d - today).days
                if item['is_overdue']:
                    item['current_fine'] = calculate_fine(due_d)
                    stats['overdue_count'] += 1
                    stats['total_fines'] += item['current_fine']
                else:
                    item['current_fine'] = 0.0

            stats['active_count'] = len(active_borrows)
        conn.close()
    except Exception as e:
        flash(f"Error loading dashboard: {e}", "danger")

    return render_template('student/dashboard.html', active_borrows=active_borrows, stats=stats)


@app.route('/student/books')
@student_required
def student_books():
    """Student book browsing page with search and category filters."""
    user_id = session['user_id']
    search_query = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()

    books = []
    categories = []
    user_borrowed_book_ids = set()

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT book_id FROM borrow_records
                WHERE user_id = %s AND return_date IS NULL
            """, (user_id,))
            user_borrowed_book_ids = {row['book_id'] for row in cursor.fetchall()}

            cursor.execute("SELECT DISTINCT category FROM books ORDER BY category ASC")
            categories = [r['category'] for r in cursor.fetchall()]

            sql = "SELECT * FROM books WHERE 1=1"
            params = []
            if search_query:
                sql += " AND (title LIKE %s OR author LIKE %s OR isbn LIKE %s)"
                term = f"%{search_query}%"
                params.extend([term, term, term])
            if category:
                sql += " AND category = %s"
                params.append(category)

            sql += " ORDER BY title ASC"
            cursor.execute(sql, tuple(params))
            books = cursor.fetchall()
        conn.close()
    except Exception as e:
        flash(f"Error loading books: {e}", "danger")

    return render_template('student/books.html', books=books, categories=categories,
                           search=search_query, selected_category=category,
                           borrowed_ids=user_borrowed_book_ids)


@app.route('/student/borrow/<int:book_id>', methods=['POST'])
@student_required
def borrow_book(book_id):
    """Borrow a book for 14 days with availability and duplicate checks."""
    if not validate_csrf():
        flash("Security token mismatch. Please try again.", "danger")
        return redirect(url_for('student_books'))

    user_id = session['user_id']

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check duplicate active loan
            cursor.execute("""
                SELECT id FROM borrow_records
                WHERE user_id = %s AND book_id = %s AND return_date IS NULL
            """, (user_id, book_id))
            if cursor.fetchone():
                flash("You currently have an active copy of this book on loan.", "warning")
                conn.close()
                return redirect(url_for('student_books'))

            # Check stock
            cursor.execute("SELECT title, available_copies FROM books WHERE id = %s", (book_id,))
            book = cursor.fetchone()
            if not book:
                flash("Book not found.", "danger")
                conn.close()
                return redirect(url_for('student_books'))

            if book['available_copies'] <= 0:
                flash(f"Sorry, '{book['title']}' is currently out of stock.", "danger")
                conn.close()
                return redirect(url_for('student_books'))

            issue_date = date.today()
            due_date = issue_date + timedelta(days=DEFAULT_BORROW_DAYS)

            cursor.execute("""
                INSERT INTO borrow_records (user_id, book_id, issue_date, due_date, status)
                VALUES (%s, %s, %s, %s, 'borrowed')
            """, (user_id, book_id, issue_date, due_date))

            cursor.execute("""
                UPDATE books
                SET available_copies = available_copies - 1
                WHERE id = %s
            """, (book_id,))

        conn.close()
        flash(f"Success! You borrowed '{book['title']}'. Due date: {due_date.strftime('%b %d, %Y')}.", "success")
        return redirect(url_for('student_dashboard'))
    except Exception as e:
        flash(f"Borrowing failed: {e}", "danger")
        return redirect(url_for('student_books'))


@app.route('/student/return/<int:record_id>', methods=['POST'])
@student_required
def student_return_book(record_id):
    """Student returns their borrowed book."""
    if not validate_csrf():
        flash("Security token mismatch. Please try again.", "danger")
        return redirect(url_for('student_dashboard'))

    user_id = session['user_id']

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT br.*, b.title, b.id as b_id, b.total_copies, b.available_copies
                FROM borrow_records br
                JOIN books b ON br.book_id = b.id
                WHERE br.id = %s AND br.user_id = %s AND br.return_date IS NULL
            """, (record_id, user_id))
            record = cursor.fetchone()

            if not record:
                flash("Borrow record not found or already returned.", "danger")
                conn.close()
                return redirect(url_for('student_dashboard'))

            today = date.today()
            fine = calculate_fine(record['due_date'], today)

            cursor.execute("""
                UPDATE borrow_records
                SET return_date = %s, fine_amount = %s, status = 'returned'
                WHERE id = %s
            """, (today, fine, record_id))

            # Restock copy safely (cannot exceed total_copies)
            new_avail = min(record['total_copies'], record['available_copies'] + 1)
            cursor.execute("""
                UPDATE books
                SET available_copies = %s
                WHERE id = %s
            """, (new_avail, record['b_id']))

        conn.close()

        if fine > 0:
            flash(f"Book '{record['title']}' returned. Note: Late fee of Rs {fine:.2f} incurred.", "warning")
        else:
            flash(f"Book '{record['title']}' returned successfully with zero late fees!", "success")
        return redirect(url_for('student_dashboard'))
    except Exception as e:
        flash(f"Error returning book: {e}", "danger")
        return redirect(url_for('student_dashboard'))


@app.route('/student/history')
@student_required
def student_history():
    """Complete borrowing history for the student."""
    user_id = session['user_id']
    history = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT br.*, b.title, b.author, b.isbn, b.category
                FROM borrow_records br
                JOIN books b ON br.book_id = b.id
                WHERE br.user_id = %s
                ORDER BY br.id DESC
            """, (user_id,))
            history = cursor.fetchall()
        conn.close()
    except Exception as e:
        flash(f"Error fetching history: {e}", "danger")

    return render_template('student/history.html', history=history)


# ==========================================================
# ADMINISTRATOR PORTAL ROUTES
# ==========================================================
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard with high-level statistics and circular dial data."""
    stats = {
        "total_titles": 0,
        "total_copies": 0,
        "available_copies": 0,
        "borrowed_books": 0,
        "overdue_count": 0,
        "total_members": 0,
        "total_fines_collected": 0.0,
        "utilization_percent": 0
    }
    recent_borrows = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            update_overdue_statuses(cursor)

            cursor.execute("""
                SELECT COUNT(*) as titles,
                       COALESCE(SUM(total_copies), 0) as total,
                       COALESCE(SUM(available_copies), 0) as available
                FROM books
            """)
            book_stat = cursor.fetchone()
            if book_stat:
                stats["total_titles"] = book_stat["titles"]
                stats["total_copies"] = book_stat["total"]
                stats["available_copies"] = book_stat["available"]

            cursor.execute("SELECT COUNT(*) as active FROM borrow_records WHERE return_date IS NULL")
            stats["borrowed_books"] = cursor.fetchone()["active"]

            cursor.execute("SELECT COUNT(*) as overdue FROM borrow_records WHERE return_date IS NULL AND due_date < %s", (date.today(),))
            stats["overdue_count"] = cursor.fetchone()["overdue"]

            cursor.execute("SELECT COUNT(*) as members FROM users WHERE role = 'student'")
            stats["total_members"] = cursor.fetchone()["members"]

            cursor.execute("SELECT COALESCE(SUM(fine_amount), 0) as fines FROM borrow_records")
            stats["total_fines_collected"] = cursor.fetchone()["fines"]

            # Calculate library utilization percentage for circular dial
            if stats["total_copies"] > 0:
                stats["utilization_percent"] = round((stats["borrowed_books"] / stats["total_copies"]) * 100)

            cursor.execute("""
                SELECT br.*, b.title, u.full_name, u.username
                FROM borrow_records br
                JOIN books b ON br.book_id = b.id
                JOIN users u ON br.user_id = u.id
                ORDER BY br.id DESC LIMIT 6
            """)
            recent_borrows = cursor.fetchall()

        conn.close()
    except Exception as e:
        flash(f"Error loading admin dashboard: {e}", "danger")

    return render_template('admin/dashboard.html', stats=stats, recent_borrows=recent_borrows)


@app.route('/admin/books')
@admin_required
def admin_books():
    """Admin book catalog management."""
    search_query = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    books = []
    categories = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT category FROM books ORDER BY category ASC")
            categories = [r['category'] for r in cursor.fetchall()]

            sql = "SELECT * FROM books WHERE 1=1"
            params = []
            if search_query:
                sql += " AND (title LIKE %s OR author LIKE %s OR isbn LIKE %s)"
                term = f"%{search_query}%"
                params.extend([term, term, term])
            if category:
                sql += " AND category = %s"
                params.append(category)

            sql += " ORDER BY id DESC"
            cursor.execute(sql, tuple(params))
            books = cursor.fetchall()
        conn.close()
    except Exception as e:
        flash(f"Error loading books: {e}", "danger")

    return render_template('admin/books.html', books=books, categories=categories,
                           search=search_query, selected_category=category)


@app.route('/admin/books/add', methods=['GET', 'POST'])
@admin_required
def admin_add_book():
    """Add a new book to the catalog with validation."""
    if request.method == 'POST':
        if not validate_csrf():
            flash("Security token mismatch. Please try again.", "danger")
            return render_template('admin/add_book.html')

        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        isbn = request.form.get('isbn', '').strip()
        category = request.form.get('category', '').strip()
        copies_raw = request.form.get('total_copies', '1').strip()

        if not title or not author or not isbn or not category:
            flash("All fields are required.", "danger")
            return render_template('admin/add_book.html')

        try:
            total_copies = int(copies_raw)
            if total_copies < 1:
                raise ValueError()
        except ValueError:
            flash("Total copies must be a positive integer of at least 1.", "danger")
            return render_template('admin/add_book.html')

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM books WHERE isbn = %s", (isbn,))
                if cursor.fetchone():
                    flash("A book with this ISBN already exists in the catalog.", "warning")
                    conn.close()
                    return render_template('admin/add_book.html')

                cursor.execute("""
                    INSERT INTO books (title, author, isbn, category, total_copies, available_copies)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (title, author, isbn, category, total_copies, total_copies))
            conn.close()

            flash(f"Book '{title}' added successfully!", "success")
            return redirect(url_for('admin_books'))
        except Exception as e:
            flash(f"Failed to add book: {e}", "danger")

    return render_template('admin/add_book.html')


@app.route('/admin/books/edit/<int:book_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_book(book_id):
    """Edit book details with duplicate ISBN and stock sanity checks."""
    conn = get_db_connection()
    book = None

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM books WHERE id = %s", (book_id,))
            book = cursor.fetchone()

        if not book:
            flash("Book not found.", "danger")
            conn.close()
            return redirect(url_for('admin_books'))

        if request.method == 'POST':
            if not validate_csrf():
                flash("Security token mismatch. Please try again.", "danger")
                conn.close()
                return render_template('admin/edit_book.html', book=book)

            title = request.form.get('title', '').strip()
            author = request.form.get('author', '').strip()
            isbn = request.form.get('isbn', '').strip()
            category = request.form.get('category', '').strip()
            copies_raw = request.form.get('total_copies', '').strip()

            if not title or not author or not isbn or not category or not copies_raw:
                flash("All fields are required.", "danger")
                conn.close()
                return render_template('admin/edit_book.html', book=book)

            try:
                new_total = int(copies_raw)
                if new_total < 1:
                    raise ValueError()
            except ValueError:
                flash("Total copies must be a positive integer of at least 1.", "danger")
                conn.close()
                return render_template('admin/edit_book.html', book=book)

            borrowed_copies = book['total_copies'] - book['available_copies']
            if new_total < borrowed_copies:
                flash(f"Cannot set total copies below currently active loans ({borrowed_copies}).", "danger")
                conn.close()
                return render_template('admin/edit_book.html', book=book)

            with conn.cursor() as cursor:
                # Check duplicate ISBN on other books
                cursor.execute("SELECT id FROM books WHERE isbn = %s AND id != %s", (isbn, book_id))
                if cursor.fetchone():
                    flash("Another book already exists with this ISBN.", "warning")
                    conn.close()
                    return render_template('admin/edit_book.html', book=book)

                new_available = new_total - borrowed_copies
                cursor.execute("""
                    UPDATE books
                    SET title = %s, author = %s, isbn = %s, category = %s,
                        total_copies = %s, available_copies = %s
                    WHERE id = %s
                """, (title, author, isbn, category, new_total, new_available, book_id))

            conn.close()
            flash("Book details updated successfully!", "success")
            return redirect(url_for('admin_books'))

    except Exception as e:
        flash(f"Error editing book: {e}", "danger")

    conn.close()
    return render_template('admin/edit_book.html', book=book)


@app.route('/admin/books/delete/<int:book_id>', methods=['POST'])
@admin_required
def admin_delete_book(book_id):
    """Delete book if no active loans exist."""
    if not validate_csrf():
        flash("Security token mismatch. Please try again.", "danger")
        return redirect(url_for('admin_books'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as active FROM borrow_records
                WHERE book_id = %s AND return_date IS NULL
            """, (book_id,))
            res = cursor.fetchone()
            if res['active'] > 0:
                flash("Cannot delete this book because active loans currently exist.", "warning")
                conn.close()
                return redirect(url_for('admin_books'))

            cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
        conn.close()
        flash("Book deleted successfully from catalog.", "success")
    except Exception as e:
        flash(f"Failed to delete book: {e}", "danger")

    return redirect(url_for('admin_books'))


@app.route('/admin/issued-books')
@admin_required
def admin_issued_books():
    """View all issued books across students with filter chips."""
    filter_status = request.args.get('status', 'all')
    records = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            update_overdue_statuses(cursor)

            sql = """
                SELECT br.*, b.title, b.isbn, u.full_name, u.username, u.email
                FROM borrow_records br
                JOIN books b ON br.book_id = b.id
                JOIN users u ON br.user_id = u.id
                WHERE 1=1
            """
            params = []
            if filter_status == 'borrowed':
                sql += " AND br.return_date IS NULL"
            elif filter_status == 'overdue':
                sql += " AND br.return_date IS NULL AND br.due_date < %s"
                params.append(date.today())
            elif filter_status == 'returned':
                sql += " AND br.return_date IS NOT NULL"

            sql += " ORDER BY br.id DESC"
            cursor.execute(sql, tuple(params))
            records = cursor.fetchall()

            today = date.today()
            for r in records:
                if r['return_date'] is None:
                    due = r['due_date']
                    r['is_overdue'] = today > due
                    if r['is_overdue']:
                        r['fine_amount'] = calculate_fine(due)
        conn.close()
    except Exception as e:
        flash(f"Error fetching issued books: {e}", "danger")

    return render_template('admin/issued_books.html', records=records, current_filter=filter_status)


@app.route('/admin/return/<int:record_id>', methods=['POST'])
@admin_required
def admin_mark_returned(record_id):
    """Admin marks an issued book as returned and safely restocks inventory."""
    if not validate_csrf():
        flash("Security token mismatch. Please try again.", "danger")
        return redirect(url_for('admin_issued_books'))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT br.*, b.title, b.id as b_id, b.total_copies, b.available_copies, u.full_name
                FROM borrow_records br
                JOIN books b ON br.book_id = b.id
                JOIN users u ON br.user_id = u.id
                WHERE br.id = %s AND br.return_date IS NULL
            """, (record_id,))
            record = cursor.fetchone()

            if not record:
                flash("Record not found or already returned.", "danger")
                conn.close()
                return redirect(url_for('admin_issued_books'))

            today = date.today()
            fine = calculate_fine(record['due_date'], today)

            cursor.execute("""
                UPDATE borrow_records
                SET return_date = %s, fine_amount = %s, status = 'returned'
                WHERE id = %s
            """, (today, fine, record_id))

            new_avail = min(record['total_copies'], record['available_copies'] + 1)
            cursor.execute("""
                UPDATE books
                SET available_copies = %s
                WHERE id = %s
            """, (new_avail, record['b_id']))

        conn.close()
        flash(f"Book '{record['title']}' returned by {record['full_name']}. Fine: Rs {fine:.2f}.", "success")
    except Exception as e:
        flash(f"Error marking book returned: {e}", "danger")

    return redirect(url_for('admin_issued_books'))


# ==========================================================
# ERROR HANDLERS (404 and 500)
# ==========================================================
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html', error=str(e)), 500


# Call DB seed initialization if DB is available
init_db_seeds()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print(f"[*] Starting Library System on port {port}...")
    print(f"[*] Database Engine Active: {ACTIVE_DB_ENGINE.upper()}")
    if ACTIVE_DB_ENGINE == "sqlite":
        print(f"[*] (Local SQLite mode active - no MySQL installation required for local testing!)")
    else:
        print(f"[*] (Connected to MySQL at {DB_HOST}:{DB_PORT})")
    app.run(host='0.0.0.0', port=port, debug=debug)
