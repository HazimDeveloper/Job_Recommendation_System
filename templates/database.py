try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    import pymysql
    from pymysql import Error
    # PyMySQL compatibility
    mysql = type('mysql', (), {})()
    mysql.connector = pymysql
import json
from datetime import datetime

class Database:
    def __init__(self, host='localhost', database='jobmatch_pro', user='root', password=''):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.connection = None
        
    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )
            print("Successfully connected to MySQL database")
            return True
        except Error as e:
            print(f"Error while connecting to MySQL: {e}")
            return False
    
    def disconnect(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("MySQL connection is closed")
    
    def create_tables(self):
        if not self.connection:
            if not self.connect():
                return False
        
        cursor = self.connection.cursor()
        
        # Users table
        users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            name VARCHAR(100) NOT NULL,
            role ENUM('admin', 'company', 'fresh_grad') NOT NULL,
            skills JSON DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
        
        # Companies table (extended info for companies)
        companies_table = """
        CREATE TABLE IF NOT EXISTS companies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            company_name VARCHAR(200),
            industry VARCHAR(100),
            location VARCHAR(200),
            description TEXT,
            website VARCHAR(255),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        
        # Job categories table
        job_categories_table = """
        CREATE TABLE IF NOT EXISTS job_categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        # Jobs table (enhanced)
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
            status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
            source VARCHAR(100) DEFAULT 'internal',
            external_url VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES job_categories(id) ON DELETE SET NULL
        )
        """
        
        # Applications table
        applications_table = """
        CREATE TABLE IF NOT EXISTS applications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            job_id INT,
            status ENUM('pending', 'accepted', 'rejected') DEFAULT 'pending',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            UNIQUE KEY unique_application (user_id, job_id)
        )
        """
        
        # Job alerts table
        job_alerts_table = """
        CREATE TABLE IF NOT EXISTS job_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            keywords VARCHAR(500),
            location VARCHAR(200),
            category_id INT,
            job_type VARCHAR(50),
            frequency ENUM('daily', 'weekly') DEFAULT 'weekly',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES job_categories(id) ON DELETE SET NULL
        )
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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        
        # Job sources table (for aggregation)
        job_sources_table = """
        CREATE TABLE IF NOT EXISTS job_sources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            url VARCHAR(500),
            is_active BOOLEAN DEFAULT TRUE,
            last_scraped TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        tables = [
            ("users", users_table),
            ("companies", companies_table),
            ("job_categories", job_categories_table),
            ("jobs", jobs_table),
            ("applications", applications_table),
            ("job_alerts", job_alerts_table),
            ("user_preferences", user_preferences_table),
            ("job_sources", job_sources_table)
        ]
        
        try:
            for table_name, query in tables:
                cursor.execute(query)
                print(f"Table {table_name} created successfully")
            
            self.connection.commit()
            cursor.close()
            
            # Insert default data
            self.insert_default_data()
            return True
            
        except Error as e:
            print(f"Error creating tables: {e}")
            return False
    
    def insert_default_data(self):
        cursor = self.connection.cursor()
        
        try:
            # Default job categories
            categories = [
                ('Technology', 'Software development, IT, and tech-related jobs'),
                ('Marketing', 'Digital marketing, advertising, and promotion'),
                ('Finance', 'Banking, accounting, and financial services'),
                ('Healthcare', 'Medical, nursing, and healthcare services'),
                ('Education', 'Teaching, training, and educational services'),
                ('Engineering', 'Civil, mechanical, electrical engineering'),
                ('Sales', 'Sales representatives and business development'),
                ('Human Resources', 'HR management and recruitment'),
                ('Customer Service', 'Support and customer relations'),
                ('Manufacturing', 'Production and manufacturing roles')
            ]
            
            for category in categories:
                cursor.execute(
                    "INSERT IGNORE INTO job_categories (name, description) VALUES (%s, %s)",
                    category
                )
            
            # Default admin user
            cursor.execute("""
                INSERT IGNORE INTO users (username, password, name, role) 
                VALUES ('admin', 'admin123', 'Administrator', 'admin')
            """)
            
            # Default job sources
            sources = [
                ('JobStreet', 'https://www.jobstreet.com.my'),
                ('Indeed', 'https://my.indeed.com'),
                ('LinkedIn', 'https://www.linkedin.com/jobs'),
                ('Glassdoor', 'https://www.glassdoor.com'),
                ('Monster', 'https://www.monster.com')
            ]
            
            for source in sources:
                cursor.execute(
                    "INSERT IGNORE INTO job_sources (name, url) VALUES (%s, %s)",
                    source
                )
            
            self.connection.commit()
            print("Default data inserted successfully")
            
        except Error as e:
            print(f"Error inserting default data: {e}")
        
        cursor.close()

# Database utility functions
class JobMatchDB:
    def __init__(self):
        self.db = Database()
        self.db.connect()
    
    def get_user_by_username(self, username):
        cursor = self.db.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        return user
    
    def create_user(self, username, password, name, role):
        cursor = self.db.connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password, name, role) VALUES (%s, %s, %s, %s)",
                (username, password, name, role)
            )
            self.db.connection.commit()
            
            # If company, create company record
            if role == 'company':
                user_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO companies (user_id, company_name) VALUES (%s, %s)",
                    (user_id, name)
                )
                self.db.connection.commit()
            
            cursor.close()
            return True
        except Error as e:
            print(f"Error creating user: {e}")
            cursor.close()
            return False
    
    def get_jobs_with_filters(self, category=None, location=None, job_type=None, keywords=None, limit=20, offset=0):
        cursor = self.db.connection.cursor(dictionary=True)
        
        query = """
            SELECT j.*, c.company_name, cat.name as category_name 
            FROM jobs j 
            LEFT JOIN companies c ON j.company_id = c.id
            LEFT JOIN job_categories cat ON j.category_id = cat.id
            WHERE j.status = 'approved'
        """
        params = []
        
        if category:
            query += " AND cat.name = %s"
            params.append(category)
        
        if location:
            query += " AND j.location LIKE %s"
            params.append(f"%{location}%")
        
        if job_type:
            query += " AND j.job_type = %s"
            params.append(job_type)
        
        if keywords:
            query += " AND (j.title LIKE %s OR j.description LIKE %s OR j.requirements LIKE %s)"
            keyword_param = f"%{keywords}%"
            params.extend([keyword_param, keyword_param, keyword_param])
        
        query += " ORDER BY j.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        jobs = cursor.fetchall()
        cursor.close()
        return jobs
    
    def get_job_categories(self):
        cursor = self.db.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM job_categories ORDER BY name")
        categories = cursor.fetchall()
        cursor.close()
        return categories
    
    def create_job_alert(self, user_id, keywords, location, category_id, job_type, frequency):
        cursor = self.db.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO job_alerts (user_id, keywords, location, category_id, job_type, frequency) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, keywords, location, category_id, job_type, frequency))
            self.db.connection.commit()
            cursor.close()
            return True
        except Error as e:
            print(f"Error creating job alert: {e}")
            cursor.close()
            return False
    
    def get_personalized_jobs(self, user_id, limit=10):
        cursor = self.db.connection.cursor(dictionary=True)
        
        # Get user skills and preferences
        cursor.execute("SELECT skills FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if user and user['skills']:
            skills = json.loads(user['skills']) if isinstance(user['skills'], str) else user['skills']
            
            # Simple matching based on skills in job title or description
            placeholders = ', '.join(['%s'] * len(skills))
            query = f"""
                SELECT j.*, c.company_name, cat.name as category_name,
                       (
                           CASE 
                               WHEN j.title REGEXP %s THEN 3
                               WHEN j.description REGEXP %s THEN 2
                               WHEN j.requirements REGEXP %s THEN 1
                               ELSE 0
                           END
                       ) as relevance_score
                FROM jobs j 
                LEFT JOIN companies c ON j.company_id = c.id
                LEFT JOIN job_categories cat ON j.category_id = cat.id
                WHERE j.status = 'approved'
                ORDER BY relevance_score DESC, j.created_at DESC 
                LIMIT %s
            """
            
            # Create regex pattern from skills
            skills_pattern = '|'.join(skills)
            cursor.execute(query, (skills_pattern, skills_pattern, skills_pattern, limit))
        else:
            # Fallback to recent jobs
            query = """
                SELECT j.*, c.company_name, cat.name as category_name 
                FROM jobs j 
                LEFT JOIN companies c ON j.company_id = c.id
                LEFT JOIN job_categories cat ON j.category_id = cat.id
                WHERE j.status = 'approved'
                ORDER BY j.created_at DESC 
                LIMIT %s
            """
            cursor.execute(query, (limit,))
        
        jobs = cursor.fetchall()
        cursor.close()
        return jobs

# Initialize database
def init_database():
    db = Database()
    if db.connect():
        if db.create_tables():
            print("Database initialized successfully!")
            return True
        else:
            print("Failed to create tables")
            return False
    else:
        print("Failed to connect to database")
        return False

if __name__ == "__main__":
    init_database()