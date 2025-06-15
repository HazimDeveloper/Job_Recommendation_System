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
            # Return sample jobs for demo
            sample_jobs = [
                {
                    'id': 1, 'title': 'Senior Software Engineer', 'company_name': 'Tech Corp',
                    'location': 'Kuala Lumpur', 'category_name': 'Technology', 'job_type': 'Full-time',
                    'salary_range': 'RM 8,000 - 12,000', 'status': 'approved'
                },
                {
                    'id': 2, 'title': 'Frontend Developer', 'company_name': 'Digital Solutions',
                    'location': 'Selangor', 'category_name': 'Technology', 'job_type': 'Full-time',
                    'salary_range': 'RM 5,000 - 8,000', 'status': 'approved'
                },
                {
                    'id': 3, 'title': 'Marketing Specialist', 'company_name': 'Creative Agency',
                    'location': 'Penang', 'category_name': 'Marketing', 'job_type': 'Full-time',
                    'salary_range': 'RM 4,000 - 6,000', 'status': 'approved'
                }
            ]
            return sample_jobs[offset:offset+limit]
        
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
            return self.get_jobs_with_filters(limit=limit)
    
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

# Load job data (fallback CSV data)
try:
    df = pd.read_csv('job_final.csv') 
    df['test'] = df['Job_Description'].apply(lambda x: ' '.join([word for word in str(x).split() if len(word)>2 and word not in (stopw)]))
    print(f"✅ Loaded {len(df)} jobs from CSV as fallback")
except Exception as e:
    print(f"⚠️ CSV not found: {e}, using database only")
    df = pd.DataFrame(columns=['Position', 'Company', 'Location', 'Job_Description', 'test'])

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
    
    # Get jobs from database with filters
    offset = (page - 1) * jobs_per_page
    jobs = db.get_jobs_with_filters(
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
    
    # Get unique locations
    all_jobs = db.get_jobs_with_filters(limit=1000)
    locations = list(set([job.get('location', '') for job in all_jobs if job.get('location')]))
    
    # Pagination calculation
    total_jobs = len(db.get_jobs_with_filters(
        category=category,
        location=location,
        job_type=job_type, 
        keywords=keywords,
        limit=10000
    ))
    total_pages = max(1, (total_jobs + jobs_per_page - 1) // jobs_per_page)
    
    # Ensure page is within valid range
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    # Format jobs for template
    job_list = []
    for job in jobs:
        job_list.append({
            'id': job.get('id', 0),
            'Position': job.get('title', 'Unknown Position'),
            'Company': job.get('company_name', 'Unknown Company'),
            'Location': job.get('location', 'Remote'),
            'Category': job.get('category_name', 'General'),
            'Type': job.get('job_type', 'Full-time'),
            'Salary': job.get('salary_range', 'Negotiable')
        })
    
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
    jobs = db.get_jobs_with_filters(
        category=category,
        location=location,
        job_type=job_type,
        keywords=keywords,
        limit=jobs_per_page,
        offset=offset
    )
    
    total_jobs = len(db.get_jobs_with_filters(
        category=category,
        location=location,
        job_type=job_type,
        keywords=keywords,
        limit=10000
    ))
    total_pages = max(1, (total_jobs + jobs_per_page - 1) // jobs_per_page)
    
    job_list = []
    for job in jobs:
        job_list.append({
            'id': job.get('id', 0),
            'Position': job.get('title', 'Unknown Position'),
            'Company': job.get('company_name', 'Unknown Company'),
            'Location': job.get('location', 'Remote'),
            'Category': job.get('category_name', 'General'),
            'Type': job.get('job_type', 'Full-time')
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

# Job alerts management
@app.route('/job_alerts', methods=['GET', 'POST'])
def job_alerts():
    if 'user_id' not in session or session.get('user_role') != 'fresh_grad':
        flash('Please login as a fresh graduate to manage job alerts')
        return redirect('/login')
    
    if request.method == 'POST':
        keywords = request.form.get('keywords', '')
        location = request.form.get('location', '')
        category_id = request.form.get('category_id')
        job_type = request.form.get('job_type', '')
        frequency = request.form.get('frequency', 'weekly')
        
        if db.create_job_alert(session['user_id'], keywords, location, 
                              category_id if category_id else None, job_type, frequency):
            flash('Job alert created successfully!')
        else:
            flash('Failed to create job alert. Please try again.')
        
        return redirect('/job_alerts')
    
    # Get categories for the form
    categories = db.get_job_categories()
    job_types = ['Full-time', 'Part-time', 'Contract', 'Internship']
    
    flash_messages = get_flash_messages()
    current_user = db.get_user_by_username(session['username'])
    
    template_name = 'job_alerts.html' if os.path.exists('templates/job_alerts.html') else 'main.html'
    
    return render_template(template_name,
                         categories=categories,
                         job_types=job_types,
                         session=session,
                         current_user=current_user,
                         flash_messages=flash_messages)

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
            
            # Try to update user skills in database if available
            try:
                if DATABASE_AVAILABLE:
                    cursor = db.db.connection.cursor()
                    skills_json = json.dumps(data['skills'])
                    cursor.execute("UPDATE users SET skills = %s WHERE id = %s", 
                                 (skills_json, session['user_id']))
                    db.db.connection.commit()
                    cursor.close()
            except Exception as e:
                print(f"Could not update user skills: {e}")
            
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

# Student/Fresh Graduate Routes
@app.route('/profile')
def profile():
    if 'user_id' not in session or session.get('user_role') != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    current_user = db.get_user_by_username(session['username'])
    template_name = 'profile.html' if os.path.exists('templates/profile.html') else 'main.html'
    return render_template(template_name, user=current_user)

@app.route('/search_jobs')
def search_jobs():
    if 'user_id' not in session or session.get('user_role') != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    return redirect('/')

@app.route('/my_applications')
def my_applications():
    if 'user_id' not in session or session.get('user_role') != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    # Get applications from global list (fallback) or database
    user_apps = [app for app in job_applications if app.get('student') == session['username']]
    
    template_name = 'my_applications.html' if os.path.exists('templates/my_applications.html') else 'main.html'
    return render_template(template_name, applications=user_apps)

@app.route('/apply_job', methods=['POST'])
def apply_job():
    if 'user_id' not in session or session.get('user_role') != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    job_id = request.form.get('job_id')
    
    # Simple application tracking (fallback)
    application = {
        'id': len(job_applications),
        'student': session['username'],
        'job_id': job_id,
        'job_title': 'Applied Job',
        'company': 'Company',
        'status': 'pending',
        'date': datetime.now().strftime('%Y-%m-%d')
    }
    job_applications.append(application)
    
    flash('Application submitted successfully!')
    return redirect('/my_applications')

# Company Routes
@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if 'user_id' not in session or session.get('user_role') != 'company':
        flash('Access denied')
        return redirect('/')
    
    if request.method == 'POST':
        # Process job posting (simplified)
        job_data = {
            'id': len(job_postings),
            'title': request.form['title'],
            'company_username': session['username'],
            'company_name': db.get_user_by_username(session['username'])['name'],
            'location': request.form['location'],
            'description': request.form['description'],
            'requirements': request.form['requirements'],
            'salary': request.form.get('salary', ''),
            'job_type': request.form.get('job_type', 'Full-time'),
            'status': 'pending',
            'posted_date': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        
        job_postings.append(job_data)
        flash(f'Job "{job_data["title"]}" posted successfully! Waiting for admin approval.')
        return redirect('/manage_jobs')
    
    categories = db.get_job_categories()
    current_user = db.get_user_by_username(session['username'])
    
    template_name = 'post_job_enhanced.html' if os.path.exists('templates/post_job_enhanced.html') else 'post_job.html'
    
    return render_template(template_name, 
                         categories=categories,
                         company_name=current_user['name'])

@app.route('/manage_jobs')
def manage_jobs():
    if 'user_id' not in session or session.get('user_role') != 'company':
        flash('Access denied')
        return redirect('/')
    
    # Get company jobs from global list (fallback)
    company_jobs = [job for job in job_postings if job['company_username'] == session['username']]
    
    current_user = db.get_user_by_username(session['username'])
    template_name = 'manage_jobs.html' if os.path.exists('templates/manage_jobs.html') else 'main.html'
    
    return render_template(template_name, 
                         jobs=company_jobs, 
                         company_name=current_user['name'])

@app.route('/view_applications')
def view_applications():
    if 'user_id' not in session or session.get('user_role') != 'company':
        flash('Access denied')
        return redirect('/')
    
    # Get applications for company's jobs (simplified)
    company_applications = []
    
    current_user = db.get_user_by_username(session['username'])
    template_name = 'view_applications.html' if os.path.exists('templates/view_applications.html') else 'main.html'
    
    return render_template(template_name, 
                         applications=company_applications,
                         company_name=current_user['name'])

# Admin Routes
@app.route('/manage_all_jobs')
def manage_all_jobs():
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Access denied')
        return redirect('/')
    
    template_name = 'manage_all_jobs.html' if os.path.exists('templates/manage_all_jobs.html') else 'main.html'
    return render_template(template_name, jobs=job_postings)

@app.route('/manage_users')
def manage_users():
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Access denied')
        return redirect('/')
    
    template_name = 'manage_users.html' if os.path.exists('templates/manage_users.html') else 'main.html'
    
    # Get all users (simplified)
    if hasattr(db, 'users'):
        all_users = db.users
    else:
        all_users = {'admin': {'name': 'Administrator', 'role': 'admin'}}
    
    return render_template(template_name, 
                         users=all_users, 
                         job_applications=job_applications,
                         job_postings=job_postings)

@app.route('/generate_report')
def generate_report():
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Calculate statistics
    if hasattr(db, 'users'):
        total_users = len(db.users) - 1  # Exclude admin
        fresh_grads = len([u for u in db.users.values() if u.get('role') == 'fresh_grad'])
        companies = len([u for u in db.users.values() if u.get('role') == 'company'])
    else:
        total_users = 0
        fresh_grads = 0
        companies = 0
    
    stats = {
        'total_users': total_users,
        'fresh_grads': fresh_grads,
        'companies': companies,
        'total_jobs': len(job_postings),
        'approved_jobs': len([j for j in job_postings if j.get('status') == 'approved']),
        'pending_jobs': len([j for j in job_postings if j.get('status') == 'pending']),
        'rejected_jobs': len([j for j in job_postings if j.get('status') == 'rejected']),
        'total_applications': len(job_applications),
        'accepted_apps': len([a for a in job_applications if a.get('status') == 'accepted']),
        'pending_apps': len([a for a in job_applications if a.get('status') == 'pending']),
        'rejected_apps': len([a for a in job_applications if a.get('status') == 'rejected'])
    }
    
    template_name = 'generate_report.html' if os.path.exists('templates/generate_report.html') else 'main.html'
    return render_template(template_name, stats=stats)

# Admin action routes
@app.route('/admin_approve_job/<int:job_id>')
def admin_approve_job(job_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Find and approve job
    for job in job_postings:
        if job['id'] == job_id:
            job['status'] = 'approved'
            break
    
    flash('Job approved successfully!')
    return redirect('/manage_all_jobs')

@app.route('/admin_reject_job/<int:job_id>')
def admin_reject_job(job_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Find and reject job
    for job in job_postings:
        if job['id'] == job_id:
            job['status'] = 'rejected'
            break
    
    flash('Job rejected.')
    return redirect('/manage_all_jobs')

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('main.html', 
                         job_list=[], 
                         categories=db.get_job_categories(),
                         locations=[], 
                         job_types=[],
                         flash_messages=['Page not found']), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('main.html', 
                         job_list=[], 
                         categories=db.get_job_categories(),
                         locations=[], 
                         job_types=[],
                         flash_messages=['Internal server error']), 500

# Main application entry point
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 JobMatch Pro - AI-Powered Job Recommendation System")
    print("="*60)
    print(f"📊 Database: {'Enhanced MySQL' if DATABASE_AVAILABLE else 'Fallback Mode'}")
    print(f"🌐 URL: http://localhost:5000")
    print(f"📄 CSV Data: {'Available' if len(df) > 0 else 'Not available'}")
    print("\n👤 Demo Login Credentials:")
    print("   🔑 Admin: admin / admin123")
    print("   🏢 Company: company1 / comp123")  
    print("   🎓 Student: student1 / stud123")
    print("="*60)
    print("✨ Features Available:")
    print("   • AI-powered job matching")
    print("   • Resume upload and analysis")
    print("   • Advanced job filtering")
    print("   • Personalized recommendations")
    print("   • Job alerts system")
    print("   • Multi-role dashboard")
    print("="*60)
    print("\n🚀 Starting server...")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n\n👋 JobMatch Pro stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("💡 Try: pip install -r requirements.txt")