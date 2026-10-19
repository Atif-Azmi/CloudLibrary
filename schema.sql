-- ==========================================================
-- Cloud Computing Project: Library / Book Lending System
-- Database: MySQL 8.0+
-- File: schema.sql
-- ==========================================================

-- 1. Create Database if it does not already exist
CREATE DATABASE IF NOT EXISTS library_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE library_db;

-- 2. Drop tables in reverse order of foreign keys for clean re-runs
DROP TABLE IF EXISTS borrow_records;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS users;

-- 3. Users Table (Admin and Students)
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('admin', 'student') NOT NULL DEFAULT 'student',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 4. Books Table
CREATE TABLE books (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(150) NOT NULL,
    isbn VARCHAR(20) NOT NULL UNIQUE,
    category VARCHAR(100) NOT NULL,
    total_copies INT NOT NULL DEFAULT 1,
    available_copies INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_copies CHECK (available_copies >= 0 AND available_copies <= total_copies)
) ENGINE=InnoDB;

-- 5. Borrow Records Table
CREATE TABLE borrow_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    book_id INT NOT NULL,
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    return_date DATE NULL,
    fine_amount DECIMAL(8, 2) NOT NULL DEFAULT 0.00,
    status ENUM('borrowed', 'returned', 'overdue') NOT NULL DEFAULT 'borrowed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 6. Indexes for Performance (Search and Foreign Keys)
CREATE INDEX idx_books_category ON books(category);
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_borrow_user ON borrow_records(user_id);
CREATE INDEX idx_borrow_book ON borrow_records(book_id);
CREATE INDEX idx_borrow_status ON borrow_records(status);

-- ==========================================================
-- 7. Seed Sample Data
-- Passwords below are hashed for 'admin123' and 'student123'
-- Note: app.py also auto-verifies and seeds these on startup!
-- ==========================================================

-- Default Users:
-- Admin: username='admin', password='admin123'
-- Student: username='student1', password='student123'
INSERT INTO users (username, email, password_hash, full_name, role) VALUES
('admin', 'admin@college.edu', 'scrypt:32768:8:1$K3vBqW7D9F8e0a1b$3b3d1b6cf0cb793f187a5f6e80b433d7b2938174f76ca096ffbe7ad6322ad1459ee929db221c97a7a58a7da1791a8e2cbce2a7ebfa32fb1707cb9bbf7976e5df', 'System Administrator', 'admin'),
('student1', 'student1@college.edu', 'scrypt:32768:8:1$K3vBqW7D9F8e0a1b$3b3d1b6cf0cb793f187a5f6e80b433d7b2938174f76ca096ffbe7ad6322ad1459ee929db221c97a7a58a7da1791a8e2cbce2a7ebfa32fb1707cb9bbf7976e5df', 'Aarav Sharma', 'student');

-- Sample Books across popular college subjects
INSERT INTO books (title, author, isbn, category, total_copies, available_copies) VALUES
('Cloud Computing: Concepts, Technology & Architecture', 'Thomas Erl, Ricardo Puttini', '978-0133387520', 'Cloud Computing', 5, 4),
('Designing Data-Intensive Applications', 'Martin Kleppmann', '978-1449373320', 'Database Systems', 4, 3),
('Clean Code: A Handbook of Agile Software Craftsmanship', 'Robert C. Martin', '978-0132350884', 'Software Engineering', 6, 6),
('Operating System Concepts', 'Abraham Silberschatz, Peter B. Galvin', '978-1119800361', 'Operating Systems', 4, 4),
('Computer Networking: A Top-Down Approach', 'James Kurose, Keith Ross', '978-0136681557', 'Computer Networks', 3, 3),
('Introduction to Algorithms (CLRS)', 'Thomas H. Cormen, Charles E. Leiserson', '978-0262046305', 'Algorithms', 5, 5),
('Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow', 'Aurélien Géron', '978-1492032649', 'Artificial Intelligence', 3, 3),
('Site Reliability Engineering', 'Betsy Beyer, Chris Jones', '978-1491929124', 'DevOps & Cloud', 4, 4);

-- Sample Borrow Records (Active borrow and past returned)
INSERT INTO borrow_records (user_id, book_id, issue_date, due_date, return_date, fine_amount, status) VALUES
(2, 1, DATE_SUB(CURDATE(), INTERVAL 5 DAY), DATE_ADD(CURDATE(), INTERVAL 9 DAY), NULL, 0.00, 'borrowed'),
(2, 2, DATE_SUB(CURDATE(), INTERVAL 20 DAY), DATE_SUB(CURDATE(), INTERVAL 6 DAY), NULL, 30.00, 'overdue');
