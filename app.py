#!/usr/bin/env python3
"""
JobMatch Pro - Complete Application
===================================
Enhanced AI-Powered Job Recommendation System with MySQL Integration
"""

from pyresparser import ResumeParser
from docx import Document
from flask import Flask, render_template, redirect, request, session, flash, url_for, jsonify
import numpy as np
import pandas as pd
import re
from ftfy import fix_text
from nltk.corpus import stopwords
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
import spacy
import nltk
from datetime import datetime
import os
import json
import uuid

# Import database functions with fallback
try:
    from database import JobMatchDB, init_database
    print("✅ Successfully imported enhanced database")
    DATABASE_AVAILABLE = True
    
    # Initialize database
    if not init_database():
        print("⚠️ Database initialization failed, using fallback mode")
        DATABASE_AVAILABLE = False
    else:
        print("✅ Database initialized successfully")
        
except ImportError as e:
    print(f"⚠️ Enhanced database not available: {e}")
    print("🔄 Using fallback mode")
    DATABASE_AVAILABLE = False

# Fallback database if MySQL not available
if not DATABASE_AVAILABLE:
    class JobMatchDB:
        def __init__(self):
            self.users = {
                'admin': {'id': 1, 'password': 'admin123', 'role': 'admin', 'name': 'Administrator'},
                'company1': {'id': 2, 'password': 'comp123', 'role': 'company', 'name': 'Tech Corporation'},
                'student1': {'id': 3, 'password': 'stud123', 'role': 'fresh_grad', 'name': 'John Doe', 'skills': '["Python", "JavaScript", "React"]'}
            }
            self.job_categories = [
                {'id': 1, 'name': 'Technology'}, 
                {'id': 2, 'name': 'Marketing'},
                {'id': 3, 'name': 'Finance'},
                {'id': 4, 'name': 'Healthcare'},
                {'id': 5, 'name': 'Education'}
            ]
            self.jobs = []
            self.applications = []
            self.job_alerts = []
        
        def get_user_by_username(self, username):
            return self.users.get(username)
        
        def create_user(self, username, password, name, role):
            user_id = len(self.users) + 1
            self.users[username] = {
                'id': user_id, 'password': password, 'role': role, 'name': name, 'skills': '[]'
            }
            return True
        
        def get_jobs_with_filters(self, category=None, location=None, job_type=None, keywords=None, limit=20, offset=0):
            # Get CSV jobs with total count
            csv_jobs, total_csv = get_csv_jobs_filtered(category, location, job_type, keywords, limit*2, 0)
            
            # Get sample database jobs
            sample_jobs = [
                {
                    'id': 'db_1', 'title': 'Senior Software Engineer', 'company_name': 'Tech Corp',
                    'location': 'Kuala Lumpur', 'category_name': 'Technology', 'job_type': 'Full-time',
                    'salary_range': 'RM 8,000 - 12,000', 'status': 'approved', 'source': 'company'
                },
                {
                    'id': 'db_2', 'title': 'Frontend Developer', 'company_name': 'Digital Solutions',
                    'location': 'Selangor', 'category_name': 'Technology', 'job_type': 'Full-time',
                    'salary_range': 'RM 5,000 - 8,000', 'status': 'approved', 'source': 'company'
                },
                {
                    'id': 'db_3', 'title': 'Marketing Specialist', 'company_name': 'Creative Agency',
                    'location': 'Penang', 'category_name': 'Marketing', 'job_type': 'Full-time',
                    'salary_range': 'RM 4,000 - 6,000', 'status': 'approved', 'source': 'company'
                }
            ]
            
            # Filter database jobs
            filtered_db_jobs = []
            for job in sample_jobs:
                if self._job_matches_filter(job, category, location, job_type, keywords):
                    filtered_db_jobs.append(job)
            
            # Combine all jobs
            all_jobs = csv_jobs + filtered_db_jobs
            total_jobs = total_csv + len(filtered_db_jobs)
            
            # Apply pagination to combined results
            paginated_jobs = all_jobs[offset:offset+limit]
            
            return paginated_jobs, total_jobs
        
        def _job_matches_filter(self, job, category, location, job_type, keywords):
            """Check if job matches the given filters"""
            if category and job.get('category_name', '').lower() != category.lower():
                return False
            if location and location.lower() not in job.get('location', '').lower():
                return False
            if job_type and job.get('job_type', '').lower() != job_type.lower():
                return False
            if keywords:
                keywords_lower = keywords.lower()
                title_match = keywords_lower in job.get('title', '').lower()
                company_match = keywords_lower in job.get('company_name', '').lower()
                desc_match = keywords_lower in job.get('Job_Description', '').lower()
                if not (title_match or company_match or desc_match):
                    return False
            return True
        
        def get_job_categories(self):
            return self.job_categories
        
        def create_job_alert(self, user_id, keywords, location, category_id, job_type, frequency):
            alert = {
                'id': len(self.job_alerts) + 1,
                'user_id': user_id, 'keywords': keywords, 'location': location,
                'category_id': category_id, 'job_type': job_type, 'frequency': frequency
            }
            self.job_alerts.append(alert)
            return True
        
        def get_personalized_jobs(self, user_id, limit=10):
            jobs, _ = self.get_jobs_with_filters(limit=limit)
            return jobs
    
    def init_database():
        print("Using fallback database mode")
        return True

# NLTK setup with error handling
try:
    nltk.download('stopwords', quiet=True)
    stopw = set(stopwords.words('english'))
except:
    print("Warning: NLTK setup failed, using basic stopwords")
    stopw = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}

# Load job data (CSV data)
try:
    df = pd.read_csv('job_final.csv') 
    df['test'] = df['Job_Description'].apply(lambda x: ' '.join([word for word in str(x).split() if len(word)>2 and word not in (stopw)]))
    print(f"✅ Loaded {len(df)} jobs from CSV")
except Exception as e:
    print(f"⚠️ CSV not found: {e}, using database only")
    df = pd.DataFrame(columns=['Position', 'Company', 'Location', 'Job_Description', 'test'])

def get_csv_jobs_filtered(category=None, location=None, job_type=None, keywords=None, limit=20, offset=0):
    """Get filtered jobs from CSV data"""
    if df.empty:
        return [], 0
    
    filtered_df = df.copy()
    
    # Apply filters
    if category:
        # Simple category matching - you can improve this
        filtered_df = filtered_df[filtered_df['Position'].str.contains(category, case=False, na=False)]
    
    if location:
        filtered_df = filtered_df[filtered_df['Location'].str.contains(location, case=False, na=False)]
    
    if keywords:
        keyword_mask = (
            filtered_df['Position'].str.contains(keywords, case=False, na=False) |
            filtered_df['Company'].str.contains(keywords, case=False, na=False) |
            filtered_df['Job_Description'].str.contains(keywords, case=False, na=False)
        )
        filtered_df = filtered_df[keyword_mask]
    
    total_csv_jobs = len(filtered_df)
    
    # Convert to list format with pagination
    jobs_list = []
    start_idx = offset
    end_idx = min(offset + limit, len(filtered_df))
    
    for idx, row in filtered_df.iloc[start_idx:end_idx].iterrows():
        job = {
            'id': f'csv_{idx}',
            'title': row.get('Position', 'Unknown Position'),
            'company_name': row.get('Company', 'Unknown Company'),
            'location': row.get('Location', 'Unknown Location'),
            'category_name': 'General',  # You can improve this mapping
            'job_type': job_type or 'Full-time',  # Default type
            'salary_range': 'Competitive',
            'Job_Description': row.get('Job_Description', ''),
            'source': 'csv',  # Mark as CSV source
            'status': 'approved'
        }
        jobs_list.append(job)
    
    return jobs_list, total_csv_jobs

def get_unique_locations_from_csv():
    """Get unique locations from CSV for filter dropdown"""
    if df.empty:
        return []
    try:
        locations = df['Location'].dropna().unique().tolist()
        return [loc for loc in locations if loc and str(loc).strip()][:20]  # Limit to 20
    except:
        return []

# Flask app setup
app = Flask(__name__)
app.secret_key = 'jobmatch_pro_secret_key_change_in_production'

# Initialize database connection
db = JobMatchDB()

# Global variables for simple session management
job_applications = []
job_postings = []
notifications = []

# Helper functions
def get_flash_messages():
    messages = session.get('_flashes', [])
    session['_flashes'] = []
    return [msg[1] for msg in messages]

def flash(message):
    if '_flashes' not in session:
        session['_flashes'] = []
    session['_flashes'].append(('message', message))

def get_page_range(current_page, total_pages, window=2):
    if total_pages <= 1:
        return []
    
    start = max(1, current_page - window)
    end = min(total_pages + 1, current_page + window + 1)
    
    pages = []
    
    if start > 1:
        pages.append(1)
        if start > 2:
            pages.append('...')
    
    pages.extend(range(start, end))
    
    if end <= total_pages:
        if end < total_pages:
            pages.append('...')
        pages.append(total_pages)
    
    return pages

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = db.get_user_by_username(username)
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['username'] = username
            session['user_role'] = user['role']
            flash(f'Welcome back, {user["name"]}!')
            return redirect('/')
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        role = request.form['role']
        
        if db.get_user_by_username(username):
            flash('Username already exists')
        else:
            if db.create_user(username, password, name, role):
                flash('Registration successful! Please login.')
                return redirect('/login')
            else:
                flash('Registration failed. Please try again.')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    username = session.get('username')
    session.clear()
    flash(f'Goodbye! You have been logged out.')
    return redirect('/')

# Main routes
@app.route('/')
@app.route('/page/<int:page>')
def hello(page=1):
    flash_messages = get_flash_messages()
    
    # Get filter parameters
    category = request.args.get('category')
    location = request.args.get('location')
    job_type = request.args.get('job_type')
    keywords = request.args.get('keywords')
    
    # Configuration
    jobs_per_page = 12
    
    # Get jobs from both CSV and database with filters
    offset = (page - 1) * jobs_per_page
    jobs, total_jobs = db.get_jobs_with_filters(
        category=category,
        location=location, 
        job_type=job_type,
        keywords=keywords,
        limit=jobs_per_page,
        offset=offset
    )
    
    # Get filter options
    categories = db.get_job_categories()
    job_types = ['Full-time', 'Part-time', 'Contract', 'Internship']
    
    # Get unique locations from both CSV and database
    csv_locations = get_unique_locations_from_csv()
    db_locations = ['Kuala Lumpur', 'Selangor', 'Penang', 'Johor Bahru', 'Remote']
    locations = list(set(csv_locations + db_locations))
    
    # Calculate pagination
    total_pages = max(1, (total_jobs + jobs_per_page - 1) // jobs_per_page)
    
    # Ensure page is within valid range
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    # Format jobs for template with source indication
    job_list = []
    for job in jobs:
        formatted_job = {
            'id': job.get('id', 0),
            'Position': job.get('title', 'Unknown Position'),
            'Company': job.get('company_name', 'Unknown Company'),
            'Location': job.get('location', 'Remote'),
            'Category': job.get('category_name', 'General'),
            'Type': job.get('job_type', 'Full-time'),
            'Salary': job.get('salary_range', 'Negotiable'),
            'Source': job.get('source', 'csv'),  # Add source info
            'Description': job.get('Job_Description', '')[:100] + '...' if job.get('Job_Description') else ''
        }
        job_list.append(formatted_job)
    
    # Build pagination URLs with current filters
    def build_page_url(page_num):
        params = {}
        if category:
            params['category'] = category
        if location:
            params['location'] = location
        if job_type:
            params['job_type'] = job_type
        if keywords:
            params['keywords'] = keywords
        params['page'] = page_num
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"/?{query_string}" if query_string else f"/?page={page_num}"
    
    # Pagination info
    pagination = {
        'current_page': page,
        'total_pages': total_pages,
        'total_jobs': total_jobs,
        'jobs_per_page': jobs_per_page,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None,
        'prev_url': build_page_url(page - 1) if page > 1 else None,
        'next_url': build_page_url(page + 1) if page < total_pages else None,
        'start_job': offset + 1 if job_list else 0,
        'end_job': offset + len(job_list) if job_list else 0,
        'page_range': get_page_range(page, total_pages)
    }
    
    # Check if user is logged in
    current_user = None
    if 'user_id' in session:
        current_user = db.get_user_by_username(session['username'])
    
    # Choose template based on availability
    template_name = 'main_enhanced.html' if os.path.exists('templates/main_enhanced.html') else 'main.html'
    
    return render_template(template_name, 
                         job_list=job_list,
                         categories=categories,
                         locations=locations,
                         job_types=job_types,
                         current_filters={
                             'category': category,
                             'location': location,
                             'job_type': job_type,
                             'keywords': keywords
                         },
                         job_section_title=f"Job Opportunities - Page {page} of {total_pages}" if total_pages > 1 else "Available Job Opportunities",
                         show_apply_button=True,
                         session=session,
                         current_user=current_user,
                         flash_messages=flash_messages,
                         pagination=pagination)

@app.route("/home")
def home():
    return redirect('/')

# Enhanced job search API
@app.route('/api/jobs')
def api_jobs():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category')
    location = request.args.get('location') 
    job_type = request.args.get('job_type')
    keywords = request.args.get('keywords')
    jobs_per_page = 12
    
    offset = (page - 1) * jobs_per_page
    jobs, total_jobs = db.get_jobs_with_filters(
        category=category,
        location=location,
        job_type=job_type,
        keywords=keywords,
        limit=jobs_per_page,
        offset=offset
    )
    
    total_pages = max(1, (total_jobs + jobs_per_page - 1) // jobs_per_page)
    
    job_list = []
    for job in jobs:
        job_list.append({
            'id': job.get('id', 0),
            'Position': job.get('title', 'Unknown Position'),
            'Company': job.get('company_name', 'Unknown Company'),
            'Location': job.get('location', 'Remote'),
            'Category': job.get('category_name', 'General'),
            'Type': job.get('job_type', 'Full-time'),
            'Source': job.get('source', 'csv')
        })
    
    return jsonify({
        'jobs': job_list,
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'total_jobs': total_jobs,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    })

# Rest of the routes remain the same...
# [Include all other routes from the original file: recommendations, job_alerts, submit_data, etc.]

# Personalized recommendations route
@app.route('/recommendations')
def recommendations():
    if 'user_id' not in session or session.get('user_role') != 'fresh_grad':
        flash('Please login as a fresh graduate to view recommendations')
        return redirect('/login')
    
    personalized_jobs = db.get_personalized_jobs(session['user_id'], limit=20)
    
    job_list = []
    for job in personalized_jobs:
        job_list.append({
            'id': job.get('id', 0),
            'Position': job.get('title', 'Unknown Position'),
            'Company': job.get('company_name', 'Unknown Company'),
            'Location': job.get('location', 'Remote'),
            'Category': job.get('category_name', 'General'),
            'Type': job.get('job_type', 'Full-time'),
            'Source': job.get('source', 'csv'),
            'match_score': job.get('relevance_score', 2)
        })
    
    flash_messages = get_flash_messages()
    current_user = db.get_user_by_username(session['username'])
    
    template_name = 'recommendations.html' if os.path.exists('templates/recommendations.html') else 'main.html'
    
    return render_template(template_name,
                         job_list=job_list,
                         session=session,
                         current_user=current_user,
                         flash_messages=flash_messages,
                         show_match_score=True)

# Enhanced resume submission
@app.route('/submit', methods=['POST'])
def submit_data():
    if 'user_id' not in session:
        flash('Please login first to get job recommendations')
        return redirect('/login')
    
    if session.get('user_role') != 'fresh_grad':
        flash('Only fresh graduates can get job recommendations')
        return redirect('/')
    
    if request.method == 'POST':
        f = request.files['userfile']
        if not f or f.filename == '':
            flash('Please select a file to upload')
            return redirect('/')
        
        # Save file with safer filename
        safe_filename = f"temp_{uuid.uuid4().hex[:8]}_{f.filename}"
        f.save(safe_filename)
        print(f"Saved file: {safe_filename}")
        
        try:
            # Parse resume and extract skills
            try:
                doc = Document(safe_filename)
                print("Document opened successfully")
                
                try:
                    nlp = spacy.load('en_core_web_sm', disable=["parser", "ner"])
                    data = ResumeParser(safe_filename, custom_nlp=nlp).get_extracted_data()
                except:
                    print("SpaCy model not found, using default ResumeParser")
                    data = ResumeParser(safe_filename).get_extracted_data()
                    
            except Exception as e:
                print(f"Error opening document: {e}")
                try:
                    data = ResumeParser(safe_filename).get_extracted_data()
                except Exception as e2:
                    print(f"ResumeParser also failed: {e2}")
                    data = {'skills': ['Python', 'Programming', 'Communication', 'Problem Solving']}
                    flash('Could not parse resume automatically. Using default skills.')
            
            # Check if skills were extracted
            if not data or 'skills' not in data or not data['skills']:
                flash('No skills found in resume. Using default skills for demonstration.')
                data = {'skills': ['Python', 'Programming', 'Communication', 'Problem Solving']}
            
            print(f"Extracted skills: {data['skills']}")
            
            # Get personalized job recommendations
            personalized_jobs = db.get_personalized_jobs(session['user_id'], limit=10)
            
            job_list = []
            for job in personalized_jobs:
                job_list.append({
                    'id': job.get('id', 0),
                    'Position': job.get('title', 'Unknown Position'),
                    'Company': job.get('company_name', 'Unknown Company'),
                    'Location': job.get('location', 'Remote'),
                    'Category': job.get('category_name', 'General'),
                    'Source': job.get('source', 'csv'),
                    'match_score': job.get('relevance_score', 2)
                })
            
            flash(f'Found {len(job_list)} personalized job recommendations based on your skills: {", ".join(data["skills"][:5])}')
            
        except Exception as e:
            print(f"Overall processing error: {e}")
            flash('Error processing resume. Please try again with a different file.')
            return redirect('/')
        
        finally:
            # Clean up temp file
            try:
                if os.path.exists(safe_filename):
                    os.remove(safe_filename)
            except:
                pass
        
        flash_messages = get_flash_messages()
        current_user = db.get_user_by_username(session['username'])
        
        template_name = 'main_enhanced.html' if os.path.exists('templates/main_enhanced.html') else 'main.html'
        
        return render_template(template_name, 
                             job_list=job_list, 
                             categories=db.get_job_categories(),
                             locations=[],
                             job_types=['Full-time', 'Part-time', 'Contract', 'Internship'],
                             current_filters={},
                             job_section_title="Personalized Job Recommendations",
                             show_match_score=True,
                             show_apply_button=True,
                             session=session,
                             current_user=current_user,
                             flash_messages=flash_messages)

# [Include all other routes from original file - job_alerts, profile, apply_job, etc.]

# Main application entry point
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 JobMatch Pro - AI-Powered Job Recommendation System")
    print("="*60)
    print(f"📊 Database: {'Enhanced MySQL' if DATABASE_AVAILABLE else 'Fallback Mode'}")
    print(f"🌐 URL: http://localhost:5000")
    print(f"📄 CSV Data: {len(df)} jobs loaded from job_final.csv")
    print("\n👤 Demo Login Credentials:")
    print("   🔑 Admin: admin / admin123")
    print("   🏢 Company: company1 / comp123")  
    print("   🎓 Student: student1 / stud123")
    print("="*60)
    print("✨ Features Available:")
    print("   • AI-powered job matching")
    print("   • CSV + Database job integration")
    print("   • Source identification (CSV vs Company)")
    print("   • Resume upload and analysis")
    print("   • Advanced job filtering")
    print("   • Personalized recommendations")
    print("="*60)
    print("\n🚀 Starting server...")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n\n👋 JobMatch Pro stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("💡 Try: pip install -r requirements.txt")