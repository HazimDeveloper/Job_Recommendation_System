#!/usr/bin/env python3
"""
JobMatch Pro Database Setup Script
==================================

This script sets up the MySQL database for JobMatch Pro including:
- Creating the database
- Creating all required tables
- Inserting sample data
- Setting up indexes for better performance

Usage:
    python setup_database.py

Requirements:
    - MySQL server running
    - mysql-connector-python installed
    - Appropriate MySQL user permissions
"""

import mysql.connector
from mysql.connector import Error
import json
import getpass
from datetime import datetime
import sys

def get_database_config():
    """Get database configuration from user input"""
    print("=== JobMatch Pro Database Setup ===\n")
    print("Please provide your MySQL database configuration:")
    
    config = {
        'host': input("MySQL Host (default: localhost): ").strip() or 'localhost',
        'user': input("MySQL Username (default: root): ").strip() or 'root',
        'password': getpass.getpass("MySQL Password: "),
        'database': input("Database Name (default: jobmatch_pro): ").strip() or 'jobmatch_pro'
    }
    
    return config

def create_database(config):
    """Create the database if it doesn't exist"""
    try:
        # Connect without specifying database
        connection = mysql.connector.connect(
            host=config['host'],
            user=config['user'],
            password=config['password']
        )
        
        cursor = connection.cursor()
        
        # Create database
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✓ Database '{config['database']}' created or already exists")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"✗ Error creating database: {e}")
        return False

def setup_tables(config):
    """Create all required tables"""
    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        # Users table
        users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            name VARCHAR(100) NOT NULL,
            role ENUM('admin', 'company', 'fresh_grad') NOT NULL,
            skills JSON DEFAULT NULL,
            email VARCHAR(100) DEFAULT NULL,
            phone VARCHAR(20) DEFAULT NULL,
            profile_picture VARCHAR(255) DEFAULT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            last_login TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_username (username),
            INDEX idx_role (role),
            INDEX idx_email (email)
        ) ENGINE=InnoDB
        """
        
        # Companies table
        companies_table = """
        CREATE TABLE IF NOT EXISTS companies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            company_name VARCHAR(200) NOT NULL,
            industry VARCHAR(100),
            location VARCHAR(200),
            description TEXT,
            website VARCHAR(255),
            logo_url VARCHAR(255),
            company_size ENUM('1-10', '11-50', '51-200', '201-500', '500+') DEFAULT '1-10',
            founded_year YEAR,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_company_name (company_name),
            INDEX idx_industry (industry),
            INDEX idx_location (location)
        ) ENGINE=InnoDB
        """
        
        # Job categories table
        job_categories_table = """
        CREATE TABLE IF NOT EXISTS job_categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            icon VARCHAR(50) DEFAULT 'fas fa-briefcase',
            is_active BOOLEAN DEFAULT TRUE,
            sort_order INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_name (name),
            INDEX idx_sort_order (sort_order)
        ) ENGINE=InnoDB
        """
        
        # Skills table
        skills_table = """
        CREATE TABLE IF NOT EXISTS skills (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            category VARCHAR(50),
            popularity_score INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_name (name),
            INDEX idx_category (category),
            INDEX idx_popularity (popularity_score)
        ) ENGINE=InnoDB
        """
        
        # Jobs table
        jobs_table = """
        CREATE TABLE IF NOT EXISTS jobs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            company_id INT,
            category_id INT,
            location VARCHAR(200),
            job_type ENUM('Full-time', 'Part-time', 'Contract', 'Internship') DEFAULT 'Full-time',
            salary_range VARCHAR(100),
            description TEXT,
            requirements TEXT,
            skills_required JSON,
            experience_level ENUM('Entry', 'Mid', 'Senior', 'Executive') DEFAULT 'Entry',
            remote_allowed BOOLEAN DEFAULT FALSE,
            status ENUM('pending', 'approved', 'rejected', 'closed') DEFAULT 'pending',
            source VARCHAR(100) DEFAULT 'internal',
            external_url VARCHAR(500),
            views_count INT DEFAULT 0,
            applications_count INT DEFAULT 0,
            expires_at TIMESTAMP NULL,
            featured BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES job_categories(id) ON DELETE SET NULL,
            INDEX idx_title (title),
            INDEX idx_location (location),
            INDEX idx_job_type (job_type),
            INDEX idx_status (status),
            INDEX idx_created_at (created_at),
            INDEX idx_featured (featured),
            FULLTEXT idx_search (title, description, requirements)
        ) ENGINE=InnoDB
        """
        
        # Applications table
        applications_table = """
        CREATE TABLE IF NOT EXISTS applications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            job_id INT,
            status ENUM('pending', 'accepted', 'rejected', 'withdrawn') DEFAULT 'pending',
            cover_letter TEXT,
            resume_url VARCHAR(255),
            notes TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE KEY unique_application (user_id, job_id),
            INDEX idx_user_id (user_id),
            INDEX idx_job_id (job_id),
            INDEX idx_status (status),
            INDEX idx_applied_at (applied_at)
        ) ENGINE=InnoDB
        """
        
        # Job alerts table
        job_alerts_table = """
        CREATE TABLE IF NOT EXISTS job_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            title VARCHAR(200) NOT NULL,
            keywords VARCHAR(500),
            location VARCHAR(200),
            category_id INT,
            job_type VARCHAR(50),
            salary_min INT,
            salary_max INT,
            frequency ENUM('daily', 'weekly') DEFAULT 'weekly',
            is_active BOOLEAN DEFAULT TRUE,
            last_sent TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES job_categories(id) ON DELETE SET NULL,
            INDEX idx_user_id (user_id),
            INDEX idx_is_active (is_active),
            INDEX idx_frequency (frequency)
        ) ENGINE=InnoDB
        """
        
        # User preferences table
        user_preferences_table = """
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNIQUE,
            preferred_locations JSON,
            preferred_categories JSON,
            preferred_job_types JSON,
            salary_expectations VARCHAR(100),
            work_arrangement ENUM('office', 'remote', 'hybrid', 'any') DEFAULT 'any',
            experience_level ENUM('Entry', 'Mid', 'Senior', 'Executive') DEFAULT 'Entry',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
        """
        
        # Job sources table
        job_sources_table = """
        CREATE TABLE IF NOT EXISTS job_sources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            url VARCHAR(500),
            api_endpoint VARCHAR(500),
            is_active BOOLEAN DEFAULT TRUE,
            last_scraped TIMESTAMP NULL,
            jobs_count INT DEFAULT 0,
            success_rate DECIMAL(5,2) DEFAULT 100.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_name (name),
            INDEX idx_is_active (is_active)
        ) ENGINE=InnoDB
        """
        
        # Saved jobs table
        saved_jobs_table = """
        CREATE TABLE IF NOT EXISTS saved_jobs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            job_id INT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE KEY unique_saved_job (user_id, job_id),
            INDEX idx_user_id (user_id),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB
        """
        
        # Analytics table
        analytics_table = """
        CREATE TABLE IF NOT EXISTS analytics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            job_id INT,
            action ENUM('view', 'apply', 'save', 'share', 'click') NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            referrer VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id),
            INDEX idx_job_id (job_id),
            INDEX idx_action (action),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB
        """
        
        tables = [
            ("users", users_table),
            ("companies", companies_table),
            ("job_categories", job_categories_table),
            ("skills", skills_table),
            ("jobs", jobs_table),
            ("applications", applications_table),
            ("job_alerts", job_alerts_table),
            ("user_preferences", user_preferences_table),
            ("job_sources", job_sources_table),
            ("saved_jobs", saved_jobs_table),
            ("analytics", analytics_table)
        ]
        
        for table_name, query in tables:
            cursor.execute(query)
            print(f"✓ Table '{table_name}' created successfully")
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"✗ Error creating tables: {e}")
        return False

def insert_sample_data(config):
    """Insert sample data for testing"""
    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        
        print("\nInserting sample data...")
        
        # Sample job categories
        categories = [
            ('Technology', 'Software development, IT, and tech-related jobs', 'fas fa-laptop-code'),
            ('Marketing', 'Digital marketing, advertising, and promotion', 'fas fa-bullhorn'),
            ('Finance', 'Banking, accounting, and financial services', 'fas fa-chart-line'),
            ('Healthcare', 'Medical, nursing, and healthcare services', 'fas fa-heartbeat'),
            ('Education', 'Teaching, training, and educational services', 'fas fa-graduation-cap'),
            ('Engineering', 'Civil, mechanical, electrical engineering', 'fas fa-cogs'),
            ('Sales', 'Sales representatives and business development', 'fas fa-handshake'),
            ('Human Resources', 'HR management and recruitment', 'fas fa-users'),
            ('Customer Service', 'Support and customer relations', 'fas fa-headset'),
            ('Manufacturing', 'Production and manufacturing roles', 'fas fa-industry'),
            ('Design', 'Graphic design, UI/UX, and creative roles', 'fas fa-palette'),
            ('Data Science', 'Data analysis, machine learning, and AI', 'fas fa-database')
        ]
        
        for category in categories:
            cursor.execute(
                "INSERT IGNORE INTO job_categories (name, description, icon) VALUES (%s, %s, %s)",
                category
            )
        
        # Sample skills
        skills = [
            ('Python', 'Programming'),
            ('JavaScript', 'Programming'),
            ('Java', 'Programming'),
            ('React', 'Frontend'),
            ('Angular', 'Frontend'),
            ('Vue.js', 'Frontend'),
            ('Node.js', 'Backend'),
            ('Django', 'Backend'),
            ('Flask', 'Backend'),
            ('MySQL', 'Database'),
            ('PostgreSQL', 'Database'),
            ('MongoDB', 'Database'),
            ('AWS', 'Cloud'),
            ('Azure', 'Cloud'),
            ('Docker', 'DevOps'),
            ('Kubernetes', 'DevOps'),
            ('Git', 'Tools'),
            ('Jira', 'Tools'),
            ('Photoshop', 'Design'),
            ('Figma', 'Design'),
            ('Communication', 'Soft Skills'),
            ('Leadership', 'Soft Skills'),
            ('Problem Solving', 'Soft Skills'),
            ('Project Management', 'Management'),
            ('Digital Marketing', 'Marketing'),
            ('SEO', 'Marketing'),
            ('Content Writing', 'Marketing'),
            ('Data Analysis', 'Analytics'),
            ('Machine Learning', 'AI/ML'),
            ('TensorFlow', 'AI/ML')
        ]
        
        for skill in skills:
            cursor.execute(
                "INSERT IGNORE INTO skills (name, category) VALUES (%s, %s)",
                skill
            )
        
        # Default admin user
        admin_skills = json.dumps(['System Administration', 'User Management', 'Database Management'])
        cursor.execute("""
            INSERT IGNORE INTO users (username, password, name, role, skills, email) 
            VALUES ('admin', 'admin123', 'System Administrator', 'admin', %s, 'admin@jobmatch.com')
        """, (admin_skills,))
        
        # Sample company user
        cursor.execute("""
            INSERT IGNORE INTO users (username, password, name, role, email) 
            VALUES ('techcorp', 'company123', 'Tech Corporation', 'company', 'hr@techcorp.com')
        """)
        
        # Get the company user ID and create company profile
        cursor.execute("SELECT id FROM users WHERE username = 'techcorp'")
        result = cursor.fetchone()
        if result:
            company_user_id = result[0]
            cursor.execute("""
                INSERT IGNORE INTO companies (user_id, company_name, industry, location, description, website, company_size) 
                VALUES (%s, 'Tech Corporation', 'Technology', 'Kuala Lumpur, Malaysia', 
                       'Leading technology company specializing in innovative software solutions', 
                       'https://techcorp.com', '51-200')
            """, (company_user_id,))
        
        # Sample fresh graduate user
        student_skills = json.dumps(['Python', 'JavaScript', 'React', 'Node.js', 'MySQL', 'Git'])
        cursor.execute("""
            INSERT IGNORE INTO users (username, password, name, role, skills, email) 
            VALUES ('student1', 'student123', 'John Doe', 'fresh_grad', %s, 'john.doe@email.com')
        """, (student_skills,))
        
        # Sample job sources
        sources = [
            ('JobStreet', 'https://www.jobstreet.com.my', 'https://api.jobstreet.com'),
            ('Indeed', 'https://my.indeed.com', 'https://api.indeed.com'),
            ('LinkedIn', 'https://www.linkedin.com/jobs', 'https://api.linkedin.com'),
            ('Glassdoor', 'https://www.glassdoor.com', 'https://api.glassdoor.com'),
            ('Monster', 'https://www.monster.com', 'https://api.monster.com')
        ]
        
        for source in sources:
            cursor.execute(
                "INSERT IGNORE INTO job_sources (name, url, api_endpoint) VALUES (%s, %s, %s)",
                source
            )
        
        # Sample jobs
        cursor.execute("SELECT id FROM companies WHERE company_name = 'Tech Corporation'")
        company_result = cursor.fetchone()
        
        cursor.execute("SELECT id FROM job_categories WHERE name = 'Technology'")
        tech_category_result = cursor.fetchone()
        
        if company_result and tech_category_result:
            company_id = company_result[0]
            tech_category_id = tech_category_result[0]
            
            sample_jobs = [
                ('Senior Software Engineer', company_id, tech_category_id, 'Kuala Lumpur, Malaysia', 'Full-time', 
                 'RM 8,000 - RM 12,000', 
                 'We are looking for a Senior Software Engineer to join our dynamic team. You will be responsible for developing scalable web applications and mentoring junior developers.',
                 'Bachelor\'s degree in Computer Science, 5+ years experience in software development, Strong knowledge of Python/JavaScript, Experience with cloud platforms (AWS/Azure)',
                 '["Python", "JavaScript", "React", "AWS", "Docker"]', 'Senior', 'approved'),
                
                ('Frontend Developer', company_id, tech_category_id, 'Remote', 'Full-time',
                 'RM 5,000 - RM 8,000',
                 'Join our frontend team to create amazing user experiences. You will work with modern frameworks and collaborate with designers and backend developers.',
                 'Bachelor\'s degree preferred, 3+ years frontend experience, Proficient in React/Vue.js, Strong CSS and HTML skills, Experience with responsive design',
                 '["React", "Vue.js", "CSS", "HTML", "JavaScript"]', 'Mid', 'approved'),
                
                ('Data Scientist Intern', company_id, tech_category_id, 'Kuala Lumpur, Malaysia', 'Internship',
                 'RM 1,500 - RM 2,500',
                 'Great opportunity for students to gain hands-on experience in data science and machine learning projects.',
                 'Currently pursuing degree in Data Science/Computer Science/Statistics, Basic knowledge of Python and SQL, Familiarity with data analysis libraries',
                 '["Python", "SQL", "Data Analysis", "Machine Learning"]', 'Entry', 'approved')
            ]
            
            for job in sample_jobs:
                cursor.execute("""
                    INSERT IGNORE INTO jobs (title, company_id, category_id, location, job_type, salary_range, 
                                           description, requirements, skills_required, experience_level, status) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, job)
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print("✓ Sample data inserted successfully")
        return True
        
    except Error as e:
        print(f"✗ Error inserting sample data: {e}")
        return False

def main():
    """Main setup function"""
    print("Starting JobMatch Pro database setup...\n")
    
    # Get database configuration
    config = get_database_config()
    
    # Test connection
    try:
        test_connection = mysql.connector.connect(
            host=config['host'],
            user=config['user'],
            password=config['password']
        )
        test_connection.close()
        print("✓ Database connection successful\n")
    except Error as e:
        print(f"✗ Database connection failed: {e}")
        print("Please check your MySQL server and credentials.")
        sys.exit(1)
    
    # Create database
    if not create_database(config):
        sys.exit(1)
    
    # Setup tables
    if not setup_tables(config):
        sys.exit(1)
    
    # Insert sample data
    sample_data = input("\nDo you want to insert sample data for testing? (y/N): ").strip().lower()
    if sample_data in ['y', 'yes']:
        if not insert_sample_data(config):
            sys.exit(1)
    
    print("\n" + "="*50)
    print("🎉 JobMatch Pro database setup completed successfully!")
    print("="*50)
    print(f"\nDatabase: {config['database']}")
    print(f"Host: {config['host']}")
    print(f"User: {config['user']}")
    
    if sample_data in ['y', 'yes']:
        print("\n📝 Sample login credentials:")
        print("Admin: admin / admin123")
        print("Company: techcorp / company123")  
        print("Student: student1 / student123")
    
    print("\n🚀 You can now run the application with: python app_updated.py")
    print("\nNote: Make sure to update the database credentials in your app_updated.py file")

if __name__ == "__main__":
    main()