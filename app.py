from pyresparser import ResumeParser
from docx import Document
from flask import Flask, render_template_string, redirect, request, session, flash, url_for
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

# NLTK setup with error handling
try:
    nltk.data.path.append('C:\\Users\\Dell/nltk_data')
    nltk.download('stopwords', quiet=True)
    stopw = set(stopwords.words('english'))
except:
    print("Warning: NLTK setup failed, using basic stopwords")
    stopw = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}

# Load job data
try:
    df = pd.read_csv('job_final.csv') 
    df['test'] = df['Job_Description'].apply(lambda x: ' '.join([word for word in str(x).split() if len(word)>2 and word not in (stopw)]))
    print(f"Loaded {len(df)} jobs from CSV")
    print(df["Location"].head())
except Exception as e:
    print(f"Error loading CSV: {e}")
    df = pd.DataFrame(columns=['Position', 'Company', 'Location', 'Job_Description', 'test'])

app = Flask(__name__)
app.secret_key = 'your_secret_key_change_in_production'

# Simple user storage (replace with database in production)
users = {
    'admin': {'password': 'admin123', 'role': 'admin', 'name': 'Admin User'},
    'company1': {'password': 'comp123', 'role': 'company', 'name': 'Tech Corp'},
    'student1': {'password': 'stud123', 'role': 'fresh_grad', 'name': 'John Doe', 'skills': []}
}

job_applications = []
job_postings = []
notifications = []

# Enhanced HTML Template with Multi-Role Support
MAIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Job Recommendation System</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .header {
            background-color: #007BFF;
            color: white;
            text-align: center;
            padding: 1em 0;
            border-radius: 10px 10px 0 0;
        }
        .nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
        }
        .upload-form {
            text-align: center;
            margin-bottom: 20px;
        }
        .upload-form input[type="file"] {
            padding: 10px;
            border: none;
            background-color: #f0f0f0;
            width: 80%;
        }
        .upload-form input[type="submit"] {
            background-color: #007BFF;
            color: white;
            padding: 10px 20px;
            border: none;
            cursor: pointer;
        }
        .suggested-jobs {
            margin-top: 20px;
        }
        .suggested-jobs h2 {
            color: #007BFF;
            margin-bottom: 10px;
        }
        .job-table {
            width: 100%;
            border-collapse: collapse;
        }
        .job-table th, .job-table td {
            border: 1px solid #ccc;
            padding: 10px;
            text-align: left;
            border-radius: 5px;
        }
        .job-table th {
            background-color: #007BFF;
            color: white;
        }
        .filter-form label {
            font-weight: bold;
        }
        .filter-form select {
            padding: 5px;
        }
        .btn {
            background-color: #007BFF;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            margin: 5px;
        }
        .btn:hover {
            background-color: #0056b3;
        }
        .btn-danger {
            background-color: #dc3545;
        }
        .btn-success {
            background-color: #28a745;
        }
        .auth-section {
            text-align: center;
            margin-bottom: 20px;
            padding: 15px;
            background-color: #e9ecef;
            border-radius: 5px;
        }
        .role-buttons {
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
            margin: 15px 0;
        }
        .flash-messages {
            margin: 10px 0;
        }
        .alert {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
        }
        .alert-success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
    </style>
</head>
<body>
    <div class="header">
        {% if session.username %}
        <div class="nav">
            <h1>Job Recommendation System - Welcome {{ users[session.username].name }}!</h1>
            <div>
                <span style="margin-right: 15px;">Role: {{ users[session.username].role.replace('_', ' ').title() }}</span>
                <a href="/logout" class="btn btn-danger">Logout</a>
            </div>
        </div>
        {% else %}
        <h1>Job Recommendation System</h1>
        {% endif %}
    </div>
    
    <div class="container">
        <!-- Flash Messages -->
        {% if flash_messages %}
        <div class="flash-messages">
            {% for message in flash_messages %}
                <div class="alert alert-success">{{ message }}</div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Authentication Section -->
        {% if not session.username %}
        <div class="auth-section">
            <h3>Please Login or Register</h3>
            <div class="role-buttons">
                <a href="/login" class="btn">Login</a>
                <a href="/register" class="btn btn-success">Register</a>
            </div>
            <p><em>Demo Accounts: admin/admin123, company1/comp123, student1/stud123</em></p>
        </div>
        {% endif %}

        <!-- Role-based Dashboard -->
        {% if session.username %}
        <div class="role-buttons">
            {% if users[session.username].role == 'fresh_grad' %}
                <a href="/profile" class="btn">My Profile</a>
                <a href="/search_jobs" class="btn">Search Jobs</a>
                <a href="/my_applications" class="btn">My Applications</a>
            {% elif users[session.username].role == 'company' %}
                <a href="/post_job" class="btn">Post Job</a>
                <a href="/manage_jobs" class="btn">Manage Jobs</a>
                <a href="/view_applications" class="btn">View Applications</a>
            {% elif users[session.username].role == 'admin' %}
                <a href="/manage_all_jobs" class="btn">Manage All Jobs</a>
                <a href="/manage_users" class="btn">Manage Users</a>
                <a href="/generate_report" class="btn">Generate Report</a>
            {% endif %}
        </div>
        {% endif %}

        <!-- Original Resume Upload Section (Enhanced) -->
        {% if not session.username or users[session.username].role == 'fresh_grad' %}
        <div class="upload-form">
            <h2>Upload your resume for job recommendations</h2>
            {% if session.username %}
            <form method="POST" action="/submit" enctype="multipart/form-data">
                <input type="file" name="userfile" accept=".pdf,.docx,.txt">
                <input type="submit" value="Get Job Recommendations">
            </form>
            {% else %}
            <p><em>Please login as a Fresh Graduate to upload resume</em></p>
            {% endif %}
        </div>
        {% endif %}

        <!-- Job Recommendations Display -->
        <div class="suggested-jobs">
            <h2>{{ job_section_title or "Available Jobs" }}</h2>
            {% if job_list %}
            <div class="filter-form">
                <label for="location-filter">Filter by Location:</label>
                <select id="location-filter" onchange="filterJobsByLocation()">
                    <option value="all">All Locations</option>
                    {% for location in dropdown_locations %}
                        <option value="{{ location }}">{{ location }}</option>
                    {% endfor %}
                </select>
            </div>
            <table class="job-table">
                <tr>
                    <th>Position</th>
                    <th>Company</th>
                    <th>Location</th>
                    {% if show_match_score %}
                    <th>Match Score</th>
                    {% endif %}
                    {% if show_apply_button and session.username and users[session.username].role == 'fresh_grad' %}
                    <th>Action</th>
                    {% endif %}
                </tr>
                {% for job in job_list %}
                    <tr>
                        <td>{{ job['Position'] }}</td>
                        <td>{{ job['Company'] }}</td>
                        <td>{{ job['Location'] }}</td>
                        {% if show_match_score %}
                        <td>{{ job.get('match', 'N/A') }}</td>
                        {% endif %}
                        {% if show_apply_button and session.username and users[session.username].role == 'fresh_grad' %}
                        <td>
                            <form method="POST" action="/apply_job" style="display: inline;">
                                <input type="hidden" name="job_id" value="csv_{{ loop.index0 }}">
                                <button type="submit" class="btn btn-success">Apply</button>
                            </form>
                        </td>
                        {% endif %}
                    </tr>
                {% endfor %}
            </table>
            {% else %}
            <p>No jobs to display. {% if session.username and users[session.username].role == 'fresh_grad' %}Upload your resume to get personalized recommendations!{% endif %}</p>
            {% endif %}
        </div>
    </div>

    <script>
        function filterJobsByLocation() {
            var locationFilter = document.getElementById("location-filter");
            var selectedLocation = locationFilter.value;
            var jobRows = document.querySelectorAll(".job-table tr");

            for (var i = 1; i < jobRows.length; i++) {
                var locationCell = jobRows[i].querySelector("td:nth-child(3)");
                if (selectedLocation === "all" || locationCell.textContent === selectedLocation) {
                    jobRows[i].style.display = "table-row";
                } else {
                    jobRows[i].style.display = "none";
                }
            }
        }
    </script>
</body>
</html>
"""

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and users[username]['password'] == password:
            session['username'] = username
            flash(f'Welcome back, {users[username]["name"]}!')
            return redirect('/')
        else:
            flash('Invalid username or password')
    
    # Simple login form
    login_form = """
    <div style="max-width: 400px; margin: 50px auto; padding: 20px; background: white; border-radius: 10px;">
        <h2>Login</h2>
        <form method="POST">
            <div style="margin-bottom: 15px;">
                <label>Username:</label><br>
                <input type="text" name="username" required style="width: 100%; padding: 8px;">
            </div>
            <div style="margin-bottom: 15px;">
                <label>Password:</label><br>
                <input type="password" name="password" required style="width: 100%; padding: 8px;">
            </div>
            <button type="submit" class="btn">Login</button>
        </form>
        <p><a href="/">Back to Home</a> | <a href="/register">Register</a></p>
    </div>
    """
    return f"<html><head><title>Login</title></head><body style='background: #f4f4f4; font-family: Arial;'>{login_form}</body></html>"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        role = request.form['role']
        
        if username in users:
            flash('Username already exists')
        else:
            users[username] = {
                'password': password,
                'role': role,
                'name': name,
                'skills': [] if role == 'fresh_grad' else None
            }
            flash('Registration successful! Please login.')
            return redirect('/login')
    
    # Simple registration form
    register_form = """
    <div style="max-width: 400px; margin: 50px auto; padding: 20px; background: white; border-radius: 10px;">
        <h2>Register</h2>
        <form method="POST">
            <div style="margin-bottom: 15px;">
                <label>Username:</label><br>
                <input type="text" name="username" required style="width: 100%; padding: 8px;">
            </div>
            <div style="margin-bottom: 15px;">
                <label>Password:</label><br>
                <input type="password" name="password" required style="width: 100%; padding: 8px;">
            </div>
            <div style="margin-bottom: 15px;">
                <label>Full Name:</label><br>
                <input type="text" name="name" required style="width: 100%; padding: 8px;">
            </div>
            <div style="margin-bottom: 15px;">
                <label>Role:</label><br>
                <select name="role" required style="width: 100%; padding: 8px;">
                    <option value="">Select Role</option>
                    <option value="fresh_grad">Fresh Graduate</option>
                    <option value="company">Company</option>
                </select>
            </div>
            <button type="submit" class="btn">Register</button>
        </form>
        <p><a href="/">Back to Home</a> | <a href="/login">Login</a></p>
    </div>
    """
    return f"<html><head><title>Register</title></head><body style='background: #f4f4f4; font-family: Arial;'>{register_form}</body></html>"

@app.route('/logout')
def logout():
    username = session.get('username')
    session.pop('username', None)
    flash(f'Goodbye! You have been logged out.')
    return redirect('/')

# Helper function for flash messages
def get_flash_messages():
    messages = session.get('_flashes', [])
    session['_flashes'] = []
    return [msg[1] for msg in messages]

def flash(message):
    if '_flashes' not in session:
        session['_flashes'] = []
    session['_flashes'].append(('message', message))

# Main routes
@app.route('/')
def hello():
    flash_messages = get_flash_messages()
    
    # Show recent jobs for all users
    recent_jobs = []
    if not df.empty:
        sample_jobs = df.head(5)
        for _, row in sample_jobs.iterrows():
            recent_jobs.append({
                'Position': row['Position'],
                'Company': row['Company'],
                'Location': str(row['Location']).replace('-', '')
            })
    
    dropdown_locations = []
    if recent_jobs:
        dropdown_locations = sorted(list(set([job['Location'] for job in recent_jobs])))
    
    return render_template_string(MAIN_TEMPLATE, 
                                job_list=recent_jobs,
                                dropdown_locations=dropdown_locations,
                                job_section_title="Recent Job Postings",
                                show_apply_button=True,
                                session=session,
                                users=users,
                                flash_messages=flash_messages)

@app.route("/home")
def home():
    return redirect('/')

# ORIGINAL RECOMMENDATION FUNCTION - FIXED AND ENHANCED
@app.route('/submit', methods=['POST'])
def submit_data():
    if 'username' not in session:
        flash('Please login first to get job recommendations')
        return redirect('/login')
    
    if users[session['username']]['role'] != 'fresh_grad':
        flash('Only fresh graduates can get job recommendations')
        return redirect('/')
    
    if request.method == 'POST':
        f = request.files['userfile']
        if not f or f.filename == '':
            flash('Please select a file to upload')
            return redirect('/')
        
        # Save file with original logic but safer filename
        import uuid
        safe_filename = f"temp_{uuid.uuid4().hex[:8]}_{f.filename}"
        f.save(safe_filename)
        print("Saved file:", safe_filename)
        
        try:
            # Original document processing logic
            try:
                doc = Document(safe_filename)
                print("Document opened successfully")
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                
                # Load SpaCy model with disable options (original logic)
                try:
                    nlp = spacy.load('en_core_web_sm', disable=["parser", "ner"])
                    data = ResumeParser(safe_filename, custom_nlp=nlp).get_extracted_data()
                except:
                    print("SpaCy model not found, using default ResumeParser")
                    data = ResumeParser(safe_filename).get_extracted_data()
                    
            except Exception as e:
                print("Error opening document:", e)
                try:
                    data = ResumeParser(safe_filename).get_extracted_data()
                except Exception as e2:
                    print("ResumeParser also failed:", e2)
                    # Fallback to simple text extraction
                    data = {'skills': ['Python', 'Programming', 'Communication', 'Problem Solving']}
                    flash('Could not parse resume automatically. Using default skills.')
            
            # Check if skills were extracted
            if not data or 'skills' not in data or not data['skills']:
                flash('No skills found in resume. Using default skills for demonstration.')
                data = {'skills': ['Python', 'Programming', 'Communication', 'Problem Solving']}
            
            resume = data['skills']
            print("Extracted skills:", resume)
            print(type(resume))
        
            skills = []
            skills.append(' '.join(word for word in resume))
            org_name_clean = skills
            
            # Original ngrams function
            def ngrams(string, n=3):
                try:
                    string = fix_text(string) # fix text
                    string = string.encode("ascii", errors="ignore").decode() #remove non ascii chars
                    string = string.lower()
                    chars_to_remove = [")","(",".","|","[","]","{","}","'"]
                    rx = '[' + re.escape(''.join(chars_to_remove)) + ']'
                    string = re.sub(rx, '', string)
                    string = string.replace('&', 'and')
                    string = string.replace(',', ' ')
                    string = string.replace('-', ' ')
                    string = string.title() # normalise case - capital at start of each word
                    string = re.sub(' +',' ',string).strip() # get rid of multiple spaces and replace with a single
                    string = ' '+ string +' ' # pad names for ngrams...
                    string = re.sub(r'[,-./]|\sBD',r'', string)
                    ngrams = zip(*[string[i:] for i in range(n)])
                    return [''.join(ngram) for ngram in ngrams]
                except Exception as e:
                    print(f"ngrams error: {e}")
                    # Simple fallback
                    return [string.lower()]
            
            # Original vectorization logic
            try:
                vectorizer = TfidfVectorizer(min_df=1, analyzer=ngrams, lowercase=False)
                tfidf = vectorizer.fit_transform(org_name_clean)
                print('Vectorizing completed...')
                
                def getNearestN(query):
                    queryTFIDF_ = vectorizer.transform(query)
                    distances, indices = nbrs.kneighbors(queryTFIDF_)
                    return distances, indices
                
                nbrs = NearestNeighbors(n_neighbors=1, n_jobs=-1).fit(tfidf)
                unique_org = (df['test'].values)
                distances, indices = getNearestN(unique_org)
                unique_org = list(unique_org)
                matches = []
                
                for i, j in enumerate(indices):
                    dist = round(distances[i][0], 2) if len(distances[i]) > 0 else 1.0
                    temp = [dist]
                    matches.append(temp)
                    
                matches = pd.DataFrame(matches, columns=['Match confidence'])
                df['match'] = matches['Match confidence']
                df1 = df.sort_values('match')
                df2 = df1[['Position', 'Company', 'Location']].head(10).reset_index()
                
                # Original location cleaning
                df2['Location'] = df2['Location'].astype(str)
                df2['Location'] = df2['Location'].str.replace(r'[^\x00-\x7F]', '', regex=True)

                dropdown_locations = sorted(df2['Location'].unique())
                
                # Create job list with match scores
                job_list = []
                for index, row in df2.iterrows():
                    job_list.append({
                        'Position': row['Position'],
                        'Company': row['Company'],
                        'Location': row['Location'],
                        'match': df1.iloc[index]['match']
                    })
                
                flash(f'Found {len(job_list)} job recommendations based on your skills: {", ".join(resume[:5])}')
                
            except Exception as e:
                print(f"TF-IDF processing error: {e}")
                # Simple fallback matching
                job_list = []
                for _, row in df.head(10).iterrows():
                    job_list.append({
                        'Position': row['Position'],
                        'Company': row['Company'],
                        'Location': str(row['Location']).replace('-', ''),
                        'match': 0.5
                    })
                dropdown_locations = sorted(list(set([job['Location'] for job in job_list])))
                flash('Used simplified matching due to processing limitations.')

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
        
        return render_template_string(MAIN_TEMPLATE, 
                                    job_list=job_list, 
                                    dropdown_locations=dropdown_locations,
                                    job_section_title="Recommended Jobs Based on Your Resume",
                                    show_match_score=True,
                                    show_apply_button=True,
                                    session=session,
                                    users=users,
                                    flash_messages=flash_messages)

# Simplified additional features for multi-role system
@app.route('/profile')
def profile():
    if 'username' not in session or users[session['username']]['role'] != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    profile_form = f"""
    <div style="max-width: 600px; margin: 20px auto; padding: 20px; background: white; border-radius: 10px;">
        <h2>My Profile</h2>
        <p><strong>Name:</strong> {users[session['username']]['name']}</p>
        <p><strong>Role:</strong> Fresh Graduate</p>
        <p><strong>Skills:</strong> {', '.join(users[session['username']].get('skills', [])) or 'No skills added yet'}</p>
        <p><a href="/" class="btn">Back to Home</a></p>
    </div>
    """
    return f"<html><head><title>Profile</title></head><body style='background: #f4f4f4; font-family: Arial;'>{profile_form}</body></html>"

@app.route('/search_jobs')
def search_jobs():
    if 'username' not in session or users[session['username']]['role'] != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    # Show available jobs
    job_list = []
    if not df.empty:
        for _, row in df.head(20).iterrows():
            job_list.append({
                'Position': row['Position'],
                'Company': row['Company'],
                'Location': str(row['Location']).replace('-', '')
            })
    
    dropdown_locations = sorted(list(set([job['Location'] for job in job_list]))) if job_list else []
    flash_messages = get_flash_messages()
    
    return render_template_string(MAIN_TEMPLATE,
                                job_list=job_list,
                                dropdown_locations=dropdown_locations,
                                job_section_title="All Available Jobs",
                                show_apply_button=True,
                                session=session,
                                users=users,
                                flash_messages=flash_messages)

@app.route('/my_applications')
def my_applications():
    if 'username' not in session or users[session['username']]['role'] != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    user_apps = [app for app in job_applications if app.get('student') == session['username']]
    
    apps_html = ""
    for app in user_apps:
        apps_html += f"<tr><td>{app.get('job_title', 'Unknown')}</td><td>{app.get('company', 'Unknown')}</td><td>{app.get('status', 'pending')}</td></tr>"
    
    apps_page = f"""
    <div style="max-width: 800px; margin: 20px auto; padding: 20px; background: white; border-radius: 10px;">
        <h2>My Applications</h2>
        {f'<table style="width: 100%; border-collapse: collapse;"><tr style="background: #007BFF; color: white;"><th style="padding: 10px; border: 1px solid #ccc;">Job</th><th style="padding: 10px; border: 1px solid #ccc;">Company</th><th style="padding: 10px; border: 1px solid #ccc;">Status</th></tr>{apps_html}</table>' if user_apps else '<p>No applications yet.</p>'}
        <p><a href="/" class="btn">Back to Home</a> <a href="/search_jobs" class="btn">Search More Jobs</a></p>
    </div>
    """
    return f"<html><head><title>My Applications</title></head><body style='background: #f4f4f4; font-family: Arial;'>{apps_page}</body></html>"

@app.route('/apply_job', methods=['POST'])
def apply_job():
    if 'username' not in session or users[session['username']]['role'] != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    job_id = request.form.get('job_id', '')
    # Simple application tracking
    job_applications.append({
        'student': session['username'],
        'job_id': job_id,
        'job_title': 'Applied Job',
        'company': 'Company',
        'status': 'pending',
        'date': datetime.now().strftime('%Y-%m-%d')
    })
    
    flash('Application submitted successfully!')
    return redirect('/my_applications')

# Company Routes - Enhanced with proper functionality
@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    if request.method == 'POST':
        # Process job posting
        job_data = {
            'id': len(job_postings),
            'title': request.form['title'],
            'company_username': session['username'],
            'company_name': users[session['username']]['name'],
            'location': request.form['location'],
            'description': request.form['description'],
            'requirements': request.form['requirements'],
            'salary': request.form.get('salary', ''),
            'job_type': request.form.get('job_type', 'Full-time'),
            'status': 'pending',  # waiting for admin approval
            'posted_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'applications': []
        }
        
        job_postings.append(job_data)
        flash(f'Job "{job_data["title"]}" posted successfully! Waiting for admin approval.')
        return redirect('/manage_jobs')
    
    # Job posting form
    post_job_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Post New Job</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }
            .header { background: #007BFF; color: white; padding: 20px; margin: -30px -30px 30px -30px; border-radius: 10px 10px 0 0; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 8px; font-weight: bold; color: #333; }
            input, textarea, select { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 5px; box-sizing: border-box; font-size: 14px; }
            input:focus, textarea:focus, select:focus { border-color: #007BFF; outline: none; }
            textarea { height: 120px; resize: vertical; }
            .btn { background: #007BFF; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-right: 10px; }
            .btn:hover { background: #0056b3; }
            .btn-secondary { background: #6c757d; }
            .btn-secondary:hover { background: #545b62; }
            .required { color: red; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Post New Job</h1>
                <p>Company: """ + users[session['username']]['name'] + """</p>
            </div>
            
            <form method="POST">
                <div class="form-group">
                    <label>Job Title <span class="required">*</span></label>
                    <input type="text" name="title" placeholder="e.g. Senior Software Engineer" required>
                </div>
                
                <div class="form-group">
                    <label>Location <span class="required">*</span></label>
                    <input type="text" name="location" placeholder="e.g. Kuala Lumpur, Malaysia" required>
                </div>
                
                <div class="form-group">
                    <label>Job Type</label>
                    <select name="job_type">
                        <option value="Full-time">Full-time</option>
                        <option value="Part-time">Part-time</option>
                        <option value="Contract">Contract</option>
                        <option value="Internship">Internship</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Salary Range (optional)</label>
                    <input type="text" name="salary" placeholder="e.g. RM 5,000 - RM 8,000 per month">
                </div>
                
                <div class="form-group">
                    <label>Job Description <span class="required">*</span></label>
                    <textarea name="description" placeholder="Describe the role, responsibilities, and what the candidate will be doing..." required></textarea>
                </div>
                
                <div class="form-group">
                    <label>Requirements <span class="required">*</span></label>
                    <textarea name="requirements" placeholder="List the required skills, qualifications, and experience..." required></textarea>
                </div>
                
                <div style="text-align: center; margin-top: 30px;">
                    <button type="submit" class="btn">Post Job</button>
                    <a href="/manage_jobs" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
    </body>
    </html>
    """
    
    return post_job_html

@app.route('/manage_jobs')
def manage_jobs():
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    # Get company's jobs
    company_jobs = [job for job in job_postings if job['company_username'] == session['username']]
    
    # Generate jobs table
    jobs_html = ""
    if company_jobs:
        for job in company_jobs:
            status_color = {
                'pending': '#ffc107',
                'approved': '#28a745', 
                'rejected': '#dc3545'
            }
            
            applications_count = len([app for app in job_applications if app.get('job_id') == f"posted_{job['id']}"])
            
            jobs_html += f"""
            <tr>
                <td><strong>{job['title']}</strong></td>
                <td>{job['location']}</td>
                <td>{job['job_type']}</td>
                <td><span style="color: {status_color.get(job['status'], '#000')}; font-weight: bold;">{job['status'].title()}</span></td>
                <td>{applications_count}</td>
                <td>{job['posted_date']}</td>
                <td>
                    <a href="/edit_job/{job['id']}" class="btn-small" style="background: #17a2b8;">Edit</a>
                    <a href="/delete_job/{job['id']}" class="btn-small" style="background: #dc3545;" onclick="return confirm('Are you sure you want to delete this job?')">Delete</a>
                </td>
            </tr>
            """
    else:
        jobs_html = '<tr><td colspan="7" style="text-align: center; color: #666;">No jobs posted yet</td></tr>'
    
    manage_jobs_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Manage Jobs</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
            .header {{ background: #007BFF; color: white; padding: 20px; margin: -30px -30px 30px -30px; border-radius: 10px 10px 0 0; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; flex: 1; text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #007BFF; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
            .btn {{ background: #007BFF; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .btn-small {{ padding: 6px 12px; font-size: 12px; }}
            .no-jobs {{ text-align: center; padding: 40px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Manage Jobs</h1>
                <p>Company: {users[session['username']]['name']}</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{len(company_jobs)}</div>
                    <div>Total Jobs</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([j for j in company_jobs if j['status'] == 'approved'])}</div>
                    <div>Approved Jobs</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([j for j in company_jobs if j['status'] == 'pending'])}</div>
                    <div>Pending Approval</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{sum(len([app for app in job_applications if app.get('job_id') == f"posted_{job['id']}"]) for job in company_jobs)}</div>
                    <div>Total Applications</div>
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <a href="/post_job" class="btn">Post New Job</a>
                <a href="/view_applications" class="btn" style="background: #28a745;">View Applications</a>
                <a href="/" class="btn" style="background: #6c757d;">Back to Home</a>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Job Title</th>
                        <th>Location</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Applications</th>
                        <th>Posted Date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {jobs_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    return manage_jobs_html

@app.route('/view_applications')
def view_applications():
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    # Get company's job IDs
    company_job_ids = [f"posted_{job['id']}" for job in job_postings if job['company_username'] == session['username']]
    
    # Get applications for company's jobs
    company_applications = [app for app in job_applications if app.get('job_id') in company_job_ids]
    
    # Generate applications table
    applications_html = ""
    if company_applications:
        for app in company_applications:
            # Get job title
            job_title = "Unknown Job"
            for job in job_postings:
                if f"posted_{job['id']}" == app['job_id']:
                    job_title = job['title']
                    break
            
            # Get applicant info
            applicant = users.get(app['student'], {})
            applicant_name = applicant.get('name', 'Unknown')
            applicant_skills = ', '.join(applicant.get('skills', [])) or 'No skills listed'
            
            status_color = {
                'pending': '#ffc107',
                'accepted': '#28a745',
                'rejected': '#dc3545'
            }
            
            actions = ""
            if app['status'] == 'pending':
                actions = f"""
                <a href="/accept_application/{app['id']}" class="btn-small" style="background: #28a745;" onclick="return confirm('Accept this application?')">Accept</a>
                <a href="/reject_application/{app['id']}" class="btn-small" style="background: #dc3545;" onclick="return confirm('Reject this application?')">Reject</a>
                """
            else:
                actions = '<span style="color: #666;">No actions</span>'
            
            applications_html += f"""
            <tr>
                <td><strong>{job_title}</strong></td>
                <td>{applicant_name}</td>
                <td>{applicant_skills}</td>
                <td><span style="color: {status_color.get(app['status'], '#000')}; font-weight: bold;">{app['status'].title()}</span></td>
                <td>{app.get('date', 'Unknown')}</td>
                <td>{actions}</td>
            </tr>
            """
    else:
        applications_html = '<tr><td colspan="6" style="text-align: center; color: #666;">No applications received yet</td></tr>'
    
    view_applications_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>View Applications</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
            .header {{ background: #28a745; color: white; padding: 20px; margin: -30px -30px 30px -30px; border-radius: 10px 10px 0 0; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; flex: 1; text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #28a745; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
            .btn {{ background: #007BFF; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .btn-small {{ padding: 6px 12px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Job Applications</h1>
                <p>Company: {users[session['username']]['name']}</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{len(company_applications)}</div>
                    <div>Total Applications</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([a for a in company_applications if a['status'] == 'pending'])}</div>
                    <div>Pending Review</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([a for a in company_applications if a['status'] == 'accepted'])}</div>
                    <div>Accepted</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([a for a in company_applications if a['status'] == 'rejected'])}</div>
                    <div>Rejected</div>
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <a href="/manage_jobs" class="btn">Back to Manage Jobs</a>
                <a href="/post_job" class="btn" style="background: #28a745;">Post New Job</a>
                <a href="/" class="btn" style="background: #6c757d;">Back to Home</a>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Job Title</th>
                        <th>Applicant Name</th>
                        <th>Skills</th>
                        <th>Status</th>
                        <th>Applied Date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {applications_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    return view_applications_html

@app.route('/edit_job/<int:job_id>', methods=['GET', 'POST'])
def edit_job(job_id):
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    # Find the job
    job = None
    for j in job_postings:
        if j['id'] == job_id and j['company_username'] == session['username']:
            job = j
            break
    
    if not job:
        flash('Job not found!')
        return redirect('/manage_jobs')
    
    if request.method == 'POST':
        # Update job details
        job['title'] = request.form['title']
        job['location'] = request.form['location']
        job['description'] = request.form['description']
        job['requirements'] = request.form['requirements']
        job['salary'] = request.form.get('salary', '')
        job['job_type'] = request.form.get('job_type', 'Full-time')
        job['status'] = 'pending'  # Reset to pending after edit
        
        flash(f'Job "{job["title"]}" updated successfully! Waiting for admin approval.')
        return redirect('/manage_jobs')
    
    # Edit form (similar to post job but with existing data)
    edit_job_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Edit Job</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
            .header {{ background: #17a2b8; color: white; padding: 20px; margin: -30px -30px 30px -30px; border-radius: 10px 10px 0 0; }}
            .form-group {{ margin-bottom: 20px; }}
            label {{ display: block; margin-bottom: 8px; font-weight: bold; color: #333; }}
            input, textarea, select {{ width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 5px; box-sizing: border-box; font-size: 14px; }}
            input:focus, textarea:focus, select:focus {{ border-color: #17a2b8; outline: none; }}
            textarea {{ height: 120px; resize: vertical; }}
            .btn {{ background: #17a2b8; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-right: 10px; }}
            .btn:hover {{ background: #138496; }}
            .btn-secondary {{ background: #6c757d; }}
            .btn-secondary:hover {{ background: #545b62; }}
            .required {{ color: red; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Edit Job</h1>
                <p>Job: {job['title']}</p>
            </div>
            
            <form method="POST">
                <div class="form-group">
                    <label>Job Title <span class="required">*</span></label>
                    <input type="text" name="title" value="{job['title']}" required>
                </div>
                
                <div class="form-group">
                    <label>Location <span class="required">*</span></label>
                    <input type="text" name="location" value="{job['location']}" required>
                </div>
                
                <div class="form-group">
                    <label>Job Type</label>
                    <select name="job_type">
                        <option value="Full-time" {'selected' if job['job_type'] == 'Full-time' else ''}>Full-time</option>
                        <option value="Part-time" {'selected' if job['job_type'] == 'Part-time' else ''}>Part-time</option>
                        <option value="Contract" {'selected' if job['job_type'] == 'Contract' else ''}>Contract</option>
                        <option value="Internship" {'selected' if job['job_type'] == 'Internship' else ''}>Internship</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Salary Range (optional)</label>
                    <input type="text" name="salary" value="{job.get('salary', '')}">
                </div>
                
                <div class="form-group">
                    <label>Job Description <span class="required">*</span></label>
                    <textarea name="description" required>{job['description']}</textarea>
                </div>
                
                <div class="form-group">
                    <label>Requirements <span class="required">*</span></label>
                    <textarea name="requirements" required>{job['requirements']}</textarea>
                </div>
                
                <div style="text-align: center; margin-top: 30px;">
                    <button type="submit" class="btn">Update Job</button>
                    <a href="/manage_jobs" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
    </body>
    </html>
    """
    
    return edit_job_html

@app.route('/delete_job/<int:job_id>')
def delete_job(job_id):
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    global job_postings
    # Remove job if it belongs to the current company
    job_postings = [job for job in job_postings if not (job['id'] == job_id and job['company_username'] == session['username'])]
    
    flash('Job deleted successfully!')
    return redirect('/manage_jobs')

@app.route('/accept_application/<int:app_id>')
def accept_application(app_id):
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    # Find and update application
    for app in job_applications:
        if app['id'] == app_id:
            app['status'] = 'accepted'
            
            # Add notification for student
            notification = {
                'user': app['student'],
                'message': f'Congratulations! Your application has been accepted.',
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            notifications.append(notification)
            break
    
    flash('Application accepted successfully!')
    return redirect('/view_applications')

@app.route('/reject_application/<int:app_id>')
def reject_application(app_id):
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    # Find and update application
    for app in job_applications:
        if app['id'] == app_id:
            app['status'] = 'rejected'
            
            # Add notification for student
            notification = {
                'user': app['student'],
                'message': f'Thank you for your interest. Unfortunately, your application was not selected this time.',
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            notifications.append(notification)
            break
    
    flash('Application rejected.')
    return redirect('/view_applications')

@app.route('/manage_all_jobs')
def manage_all_jobs():
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Generate jobs table for all companies
    jobs_html = ""
    if job_postings:
        for job in job_postings:
            status_color = {
                'pending': '#ffc107',
                'approved': '#28a745', 
                'rejected': '#dc3545'
            }
            
            applications_count = len([app for app in job_applications if app.get('job_id') == f"posted_{job['id']}"])
            
            actions = ""
            if job['status'] == 'pending':
                actions = f"""
                <a href="/admin_approve_job/{job['id']}" class="btn-small" style="background: #28a745;" onclick="return confirm('Approve this job posting?')">Approve</a>
                <a href="/admin_reject_job/{job['id']}" class="btn-small" style="background: #dc3545;" onclick="return confirm('Reject this job posting?')">Reject</a>
                """
            else:
                actions = f'<span style="color: #666;">Already {job["status"]}</span>'
            
            jobs_html += f"""
            <tr>
                <td><strong>{job['title']}</strong></td>
                <td>{job['company_name']}</td>
                <td>{job['location']}</td>
                <td>{job['job_type']}</td>
                <td><span style="color: {status_color.get(job['status'], '#000')}; font-weight: bold;">{job['status'].title()}</span></td>
                <td>{applications_count}</td>
                <td>{job['posted_date']}</td>
                <td>{actions}</td>
            </tr>
            """
    else:
        jobs_html = '<tr><td colspan="8" style="text-align: center; color: #666;">No job postings yet</td></tr>'
    
    manage_all_jobs_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - Manage All Jobs</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
            .header {{ background: #dc3545; color: white; padding: 20px; margin: -30px -30px 30px -30px; border-radius: 10px 10px 0 0; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; flex: 1; text-align: center; border: 2px solid #e9ecef; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #dc3545; }}
            .stat-label {{ color: #666; font-size: 14px; margin-top: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; font-weight: bold; position: sticky; top: 0; }}
            .btn {{ background: #007BFF; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .btn-small {{ padding: 6px 12px; font-size: 12px; margin: 2px; }}
            .filter-section {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🛠️ Admin Dashboard - Manage All Jobs</h1>
                <p>Review and manage job postings from all companies</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{len(job_postings)}</div>
                    <div class="stat-label">Total Job Postings</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([j for j in job_postings if j['status'] == 'pending'])}</div>
                    <div class="stat-label">Pending Approval</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([j for j in job_postings if j['status'] == 'approved'])}</div>
                    <div class="stat-label">Approved Jobs</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([j for j in job_postings if j['status'] == 'rejected'])}</div>
                    <div class="stat-label">Rejected Jobs</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{sum(len([app for app in job_applications if app.get('job_id') == f"posted_{job['id']}"]) for job in job_postings)}</div>
                    <div class="stat-label">Total Applications</div>
                </div>
            </div>
            
            <div class="filter-section">
                <strong>Quick Actions:</strong>
                <a href="javascript:void(0)" onclick="filterByStatus('pending')" class="btn-small" style="background: #ffc107;">Show Pending Only</a>
                <a href="javascript:void(0)" onclick="filterByStatus('approved')" class="btn-small" style="background: #28a745;">Show Approved Only</a>
                <a href="javascript:void(0)" onclick="filterByStatus('rejected')" class="btn-small" style="background: #dc3545;">Show Rejected Only</a>
                <a href="javascript:void(0)" onclick="filterByStatus('all')" class="btn-small" style="background: #6c757d;">Show All</a>
            </div>
            
            <div style="margin-bottom: 20px;">
                <a href="/manage_users" class="btn" style="background: #17a2b8;">Manage Users</a>
                <a href="/generate_report" class="btn" style="background: #28a745;">Generate Report</a>
                <a href="/" class="btn" style="background: #6c757d;">Back to Home</a>
            </div>
            
            <div style="overflow-x: auto;">
                <table id="jobsTable">
                    <thead>
                        <tr>
                            <th>Job Title</th>
                            <th>Company</th>
                            <th>Location</th>
                            <th>Type</th>
                            <th>Status</th>
                            <th>Applications</th>
                            <th>Posted Date</th>
                            <th>Admin Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {jobs_html}
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            function filterByStatus(status) {{
                var table = document.getElementById('jobsTable');
                var rows = table.getElementsByTagName('tr');
                
                for (var i = 1; i < rows.length; i++) {{
                    var statusCell = rows[i].getElementsByTagName('td')[4];
                    if (statusCell) {{
                        var cellText = statusCell.textContent.toLowerCase();
                        if (status === 'all' || cellText.includes(status)) {{
                            rows[i].style.display = '';
                        }} else {{
                            rows[i].style.display = 'none';
                        }}
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    return manage_all_jobs_html

@app.route('/admin_reject_job/<int:job_id>')
def admin_reject_job(job_id):
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Find and reject job
    for job in job_postings:
        if job['id'] == job_id:
            job['status'] = 'rejected'
            
            # Notify company
            notification = {
                'user': job['company_username'],
                'message': f'Your job posting "{job["title"]}" was not approved. Please review and resubmit if needed.',
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            notifications.append(notification)
            break
    
    flash('Job rejected.')
    return redirect('/manage_all_jobs')

@app.route('/delete_user_admin/<username>')
def delete_user_admin(username):
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    if username in users and username != 'admin':
        user_name = users[username]['name']
        
        # Remove user
        del users[username]
        
        # Remove user's applications
        job_applications = [app for app in job_applications if app.get('student') != username]
        
        # Remove user's job postings (if company)
        job_postings = [job for job in job_postings if job.get('company_username') != username]
        
        flash(f'User "{user_name}" and all associated data deleted successfully!')
    else:
        flash('User not found or cannot be deleted!')
    
    return redirect('/manage_users')

@app.route('/view_user_details/<username>')
def view_user_details(username):
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    if username not in users:
        flash('User not found!')
        return redirect('/manage_users')
    
    user_data = users[username]
    
    # Get user activity
    if user_data['role'] == 'fresh_grad':
        user_applications = [app for app in job_applications if app.get('student') == username]
        activity_html = f"<h3>Applications ({len(user_applications)})</h3>"
        for app in user_applications:
            activity_html += f"<p>• Applied for job ID: {app.get('job_id', 'Unknown')} - Status: {app.get('status', 'Unknown')}</p>"
    elif user_data['role'] == 'company':
        user_jobs = [job for job in job_postings if job.get('company_username') == username]
        activity_html = f"<h3>Job Postings ({len(user_jobs)})</h3>"
        for job in user_jobs:
            activity_html += f"<p>• {job.get('title', 'Unknown')} - Status: {job.get('status', 'Unknown')}</p>"
    else:
        activity_html = "<p>No activity data available</p>"
    
    user_details_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>User Details - {user_data['name']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
            .header {{ background: #17a2b8; color: white; padding: 20px; margin: -30px -30px 30px -30px; border-radius: 10px 10px 0 0; }}
            .detail-row {{ margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; }}
            .btn {{ background: #007BFF; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>👤 User Details</h1>
            </div>
            
            <div class="detail-row">
                <strong>Name:</strong> {user_data['name']}
            </div>
            <div class="detail-row">
                <strong>Username:</strong> {username}
            </div>
            <div class="detail-row">
                <strong>Role:</strong> {user_data['role'].replace('_', ' ').title()}
            </div>
            <div class="detail-row">
                <strong>Skills:</strong> {', '.join(user_data.get('skills', [])) if user_data.get('skills') else 'None specified'}
            </div>
            
            <div style="margin-top: 30px;">
                {activity_html}
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="/manage_users" class="btn">Back to Manage Users</a>
                <a href="/delete_user_admin/{username}" class="btn" style="background: #dc3545;" onclick="return confirm('Are you sure you want to delete this user?')">Delete User</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return user_details_html

@app.route('/manage_users')
def manage_users():
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Generate users table (exclude admin)
    users_html = ""
    user_count = 0
    for username, user_data in users.items():
        if username != 'admin':  # Don't show admin in the list
            user_count += 1
            
            # Count user's activities
            if user_data['role'] == 'fresh_grad':
                activity_count = len([app for app in job_applications if app.get('student') == username])
                activity_text = f"{activity_count} applications"
            elif user_data['role'] == 'company':
                job_count = len([job for job in job_postings if job.get('company_username') == username])
                activity_text = f"{job_count} jobs posted"
            else:
                activity_text = "No activity"
            
            # Join date (simulated)
            join_date = "2024-01-15"  # Default join date
            
            users_html += f"""
                <tr>
                    <td><strong>{user_data['name']}</strong></td>
                    <td>{username}</td>
                    <td><span style="padding: 4px 8px; background: {'#e3f2fd' if user_data['role'] == 'fresh_grad' else '#fff3e0'}; border-radius: 4px; font-size: 12px;">{user_data['role'].replace('_', ' ').title()}</span></td>
                    <td>{activity_text}</td>
                    <td>{join_date}</td>
                    <td>
                        <a href="/view_user_details/{username}" class="btn-small" style="background: #17a2b8;">View Details</a>
                        <a href="/delete_user_admin/{username}" class="btn-small" style="background: #dc3545;" onclick="return confirm('Are you sure you want to delete user {user_data['name']}? This action cannot be undone.')">Delete User</a>
                    </td>
                </tr>
            """
    
    if not users_html:
        users_html = '<tr><td colspan="6" style="text-align: center; color: #666;">No users found</td></tr>'
    
    manage_users_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - Manage Users</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
            .header {{ background: #17a2b8; color: white; padding: 20px; margin: -30px -30px 30px -30px; border-radius: 10px 10px 0 0; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; flex: 1; text-align: center; border: 2px solid #e9ecef; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #17a2b8; }}
            .stat-label {{ color: #666; font-size: 14px; margin-top: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; font-weight: bold; }}
            .btn {{ background: #007BFF; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .btn-small {{ padding: 6px 12px; font-size: 12px; margin: 2px; }}
            .user-role {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>👥 Admin Dashboard - Manage Users</h1>
                <p>Monitor and manage all system users</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{user_count}</div>
                    <div class="stat-label">Total Users</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([u for u in users.values() if u.get('role') == 'fresh_grad'])}</div>
                    <div class="stat-label">Fresh Graduates</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([u for u in users.values() if u.get('role') == 'company'])}</div>
                    <div class="stat-label">Companies</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(job_applications)}</div>
                    <div class="stat-label">Total Applications</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(job_postings)}</div>
                    <div class="stat-label">Total Job Posts</div>
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <a href="/manage_all_jobs" class="btn" style="background: #dc3545;">Manage Jobs</a>
                <a href="/generate_report" class="btn" style="background: #28a745;">Generate Report</a>
                <a href="/" class="btn" style="background: #6c757d;">Back to Home</a>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Full Name</th>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Activity</th>
                        <th>Join Date</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {users_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    return manage_users_html

@app.route('/generate_report')
def generate_report():
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Calculate comprehensive statistics
    total_users = len(users) - 1  # Exclude admin
    fresh_grads = len([u for u in users.values() if u.get('role') == 'fresh_grad'])
    companies = len([u for u in users.values() if u.get('role') == 'company'])
    
    total_jobs = len(job_postings)
    approved_jobs = len([j for j in job_postings if j['status'] == 'approved'])
    pending_jobs = len([j for j in job_postings if j['status'] == 'pending'])
    rejected_jobs = len([j for j in job_postings if j['status'] == 'rejected'])
    
    total_applications = len(job_applications)
    accepted_apps = len([a for a in job_applications if a['status'] == 'accepted'])
    pending_apps = len([a for a in job_applications if a['status'] == 'pending'])
    rejected_apps = len([a for a in job_applications if a['status'] == 'rejected'])
    
    # Calculate rates
    job_approval_rate = (approved_jobs / total_jobs * 100) if total_jobs > 0 else 0
    app_success_rate = (accepted_apps / total_applications * 100) if total_applications > 0 else 0
    
    # Top companies by job postings
    company_job_count = {}
    for job in job_postings:
        company = job['company_name']
        company_job_count[company] = company_job_count.get(company, 0) + 1
    
    top_companies = sorted(company_job_count.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Top skills mentioned in applications (simulated data)
    popular_skills = [
        ('Python', 25), ('JavaScript', 20), ('Java', 18), ('React', 15), ('SQL', 12),
        ('Machine Learning', 10), ('Project Management', 8), ('Communication', 8)
    ]
    
    # Generate report HTML
    top_companies_html = ""
    for company, count in top_companies:
        top_companies_html += f"<li><strong>{company}</strong>: {count} jobs posted</li>"
    
    skills_html = ""
    for skill, count in popular_skills[:5]:
        skills_html += f"<li><strong>{skill}</strong>: {count} candidates</li>"
    
    # Job status chart data (for visual representation)
    job_chart_data = f"Approved: {approved_jobs}, Pending: {pending_jobs}, Rejected: {rejected_jobs}"
    app_chart_data = f"Accepted: {accepted_apps}, Pending: {pending_apps}, Rejected: {rejected_apps}"
    
    current_date = datetime.now().strftime('%B %d, %Y at %H:%M')
    
    report_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - System Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }}
            .header {{ background: #28a745; color: white; padding: 30px; margin: -40px -40px 40px -40px; border-radius: 10px 10px 0 0; text-align: center; }}
            .report-section {{ margin: 30px 0; padding: 25px; background: #f8f9fa; border-radius: 8px; border-left: 5px solid #28a745; }}
            .section-title {{ color: #28a745; font-size: 1.4em; font-weight: bold; margin-bottom: 15px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
            .stat-item {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .stat-value {{ font-size: 2.5em; font-weight: bold; color: #28a745; }}
            .stat-label {{ color: #666; font-size: 14px; margin-top: 5px; }}
            .percentage {{ font-size: 1.2em; color: #007BFF; font-weight: bold; }}
            .btn {{ background: #007BFF; color: white; padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .print-btn {{ background: #28a745; }}
            .print-btn:hover {{ background: #218838; }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
            .highlight-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; margin: 20px 0; }}
            .chart-placeholder {{ background: #e9ecef; padding: 30px; border-radius: 8px; text-align: center; color: #666; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 COMPREHENSIVE SYSTEM REPORT</h1>
                <p>Job Recommendation System Analytics</p>
                <p style="font-size: 14px; opacity: 0.9;">Generated on {current_date}</p>
            </div>
            
            <div class="highlight-box">
                <h2 style="margin: 0;">System Health Overview</h2>
                <p style="margin: 10px 0 0 0;">Platform is operating successfully with {total_users} active users and {total_jobs} job postings</p>
            </div>
            
            <div class="report-section">
                <div class="section-title">👥 User Statistics</div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{total_users}</div>
                        <div class="stat-label">Total Users</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{fresh_grads}</div>
                        <div class="stat-label">Fresh Graduates</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{companies}</div>
                        <div class="stat-label">Companies</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{(fresh_grads/total_users*100) if total_users > 0 else 0:.1f}%</div>
                        <div class="stat-label">Graduate Ratio</div>
                    </div>
                </div>
            </div>
            
            <div class="report-section">
                <div class="section-title">💼 Job Posting Analytics</div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{total_jobs}</div>
                        <div class="stat-label">Total Job Posts</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{approved_jobs}</div>
                        <div class="stat-label">Approved Jobs</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{pending_jobs}</div>
                        <div class="stat-label">Pending Review</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{job_approval_rate:.1f}%</div>
                        <div class="stat-label">Approval Rate</div>
                    </div>
                </div>
                
                <div class="chart-placeholder">
                    <strong>Job Status Distribution:</strong><br>
                    {job_chart_data}
                </div>
            </div>
            
            <div class="report-section">
                <div class="section-title">📋 Application Analytics</div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{total_applications}</div>
                        <div class="stat-label">Total Applications</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{accepted_apps}</div>
                        <div class="stat-label">Accepted</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{pending_apps}</div>
                        <div class="stat-label">Pending Review</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{app_success_rate:.1f}%</div>
                        <div class="stat-label">Success Rate</div>
                    </div>
                </div>
                
                <div class="chart-placeholder">
                    <strong>Application Status Distribution:</strong><br>
                    {app_chart_data}
                </div>
            </div>
            
            <div class="report-section">
                <div class="section-title">🏆 Top Performing Companies</div>
                <ul>
                    {top_companies_html if top_companies_html else '<li>No companies have posted jobs yet</li>'}
                </ul>
            </div>
            
            <div class="report-section">
                <div class="section-title">🔥 Most In-Demand Skills</div>
                <ul>
                    {skills_html}
                </ul>
            </div>
            
            <div class="report-section">
                <div class="section-title">📈 Key Performance Indicators</div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{(total_applications/total_jobs) if total_jobs > 0 else 0:.1f}</div>
                        <div class="stat-label">Avg Applications per Job</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{(total_jobs/companies) if companies > 0 else 0:.1f}</div>
                        <div class="stat-label">Avg Jobs per Company</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{(total_applications/fresh_grads) if fresh_grads > 0 else 0:.1f}</div>
                        <div class="stat-label">Avg Apps per Graduate</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{'High' if app_success_rate > 50 else 'Medium' if app_success_rate > 25 else 'Low'}</div>
                        <div class="stat-label">Platform Activity</div>
                    </div>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 2px solid #e9ecef;">
                <a href="javascript:window.print()" class="btn print-btn">🖨️ Print Report</a>
                <a href="/manage_all_jobs" class="btn">Manage Jobs</a>
                <a href="/manage_users" class="btn">Manage Users</a>
                <a href="/" class="btn" style="background: #6c757d;">Back to Home</a>
            </div>
            
            <div style="text-align: center; margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px; color: #666; font-size: 12px;">
                <p>This report was automatically generated by the Job Recommendation System<br>
                For questions or support, contact the system administrator</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return report_html

# Additional admin action routes
@app.route('/admin_approve_job/<int:job_id>')
def admin_approve_job(job_id):
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Find and approve job
    for job in job_postings:
        if job['id'] == job_id:
            job['status'] = 'approved'
            
            # Notify company
            notification = {
                'user': job['company_username'],
                'message': f'Great news! Your job posting "{job["title"]}" has been approved and is now live.',
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            notifications.append(notification)
            break
    
    flash('Job approved successfully!')
    return redirect('/manage_all_jobs')

if __name__ == "__main__":
    app.run(debug=True)