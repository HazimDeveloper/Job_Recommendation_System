from pyresparser import ResumeParser
from docx import Document
from flask import Flask, render_template, redirect, request, session, flash, url_for
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

# Helper function for flash messages
def get_flash_messages():
    messages = session.get('_flashes', [])
    session['_flashes'] = []
    return [msg[1] for msg in messages]

def flash(message):
    if '_flashes' not in session:
        session['_flashes'] = []
    session['_flashes'].append(('message', message))

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
    
    return render_template('login.html')

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
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    username = session.get('username')
    session.pop('username', None)
    flash(f'Goodbye! You have been logged out.')
    return redirect('/')

# Main routes with Pagination
@app.route('/')
@app.route('/page/<int:page>')
def hello(page=1):
    flash_messages = get_flash_messages()
    
    # Configuration
    jobs_per_page = 12  # Number of jobs per page
    
    # Get all unique locations for dropdown (from all data)
    dropdown_locations = []
    if not df.empty:
        all_locations = df['Location'].astype(str).str.replace('-', '').unique()
        dropdown_locations = sorted([loc for loc in all_locations if loc != 'nan' and loc != ''])
    
    # Calculate pagination
    total_jobs = len(df) if not df.empty else 0
    total_pages = (total_jobs + jobs_per_page - 1) // jobs_per_page  # Ceiling division
    
    # Ensure page is within valid range
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    
    # Get jobs for current page only (lazy loading)
    recent_jobs = []
    if not df.empty and total_jobs > 0:
        start_idx = (page - 1) * jobs_per_page
        end_idx = start_idx + jobs_per_page
        page_jobs = df.iloc[start_idx:end_idx]
        
        for _, row in page_jobs.iterrows():
            recent_jobs.append({
                'Position': row['Position'],
                'Company': row['Company'],
                'Location': str(row['Location']).replace('-', '')
            })
    
    # Pagination info for template
    pagination = {
        'current_page': page,
        'total_pages': total_pages,
        'total_jobs': total_jobs,
        'jobs_per_page': jobs_per_page,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None,
        'start_job': start_idx + 1 if recent_jobs else 0,
        'end_job': start_idx + len(recent_jobs) if recent_jobs else 0,
        'page_range': get_page_range(page, total_pages)  # For pagination buttons
    }
    
    return render_template('main.html', 
                         job_list=recent_jobs,
                         dropdown_locations=dropdown_locations,
                         job_section_title=f"Job Postings - Page {page} of {total_pages}" if total_pages > 1 else "Recent Job Postings",
                         show_apply_button=True,
                         session=session,
                         users=users,
                         flash_messages=flash_messages,
                         pagination=pagination)

# Helper function for pagination range
def get_page_range(current_page, total_pages, window=2):
    """Generate page range for pagination with window around current page"""
    if total_pages <= 1:
        return []
    
    start = max(1, current_page - window)
    end = min(total_pages + 1, current_page + window + 1)
    
    pages = []
    
    # Add first page if not in range
    if start > 1:
        pages.append(1)
        if start > 2:
            pages.append('...')
    
    # Add pages in range
    pages.extend(range(start, end))
    
    # Add last page if not in range
    if end <= total_pages:
        if end < total_pages:
            pages.append('...')
        pages.append(total_pages)
    
    return pages

# Optional: Add route for AJAX job loading (for dynamic pagination)
@app.route('/api/jobs')
def api_jobs():
    page = request.args.get('page', 1, type=int)
    location_filter = request.args.get('location', '')
    jobs_per_page = 12
    
    # Filter by location if provided
    filtered_df = df
    if location_filter and location_filter != 'all':
        filtered_df = df[df['Location'].astype(str).str.replace('-', '') == location_filter]
    
    total_jobs = len(filtered_df)
    total_pages = (total_jobs + jobs_per_page - 1) // jobs_per_page
    
    # Get jobs for current page
    start_idx = (page - 1) * jobs_per_page
    end_idx = start_idx + jobs_per_page
    page_jobs = filtered_df.iloc[start_idx:end_idx]
    
    jobs = []
    for _, row in page_jobs.iterrows():
        jobs.append({
            'Position': row['Position'],
            'Company': row['Company'],
            'Location': str(row['Location']).replace('-', '')
        })
    
    return {
        'jobs': jobs,
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'total_jobs': total_jobs,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    }

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
        
        return render_template('main.html', 
                             job_list=job_list, 
                             dropdown_locations=dropdown_locations,
                             job_section_title="Recommended Jobs Based on Your Resume",
                             show_match_score=True,
                             show_apply_button=True,
                             session=session,
                             users=users,
                             flash_messages=flash_messages)

# Student/Fresh Graduate Routes
@app.route('/profile')
def profile():
    if 'username' not in session or users[session['username']]['role'] != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    return render_template('profile.html', user=users[session['username']])

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
    
    return render_template('main.html',
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
    return render_template('my_applications.html', applications=user_apps)

@app.route('/apply_job', methods=['POST'])
def apply_job():
    if 'username' not in session or users[session['username']]['role'] != 'fresh_grad':
        flash('Access denied')
        return redirect('/')
    
    job_id = request.form.get('job_id', '')
    # Simple application tracking
    job_applications.append({
        'id': len(job_applications),
        'student': session['username'],
        'job_id': job_id,
        'job_title': 'Applied Job',
        'company': 'Company',
        'status': 'pending',
        'date': datetime.now().strftime('%Y-%m-%d')
    })
    
    flash('Application submitted successfully!')
    return redirect('/my_applications')

# Company Routes
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
    
    return render_template('post_job.html', company_name=users[session['username']]['name'])

@app.route('/manage_jobs')
def manage_jobs():
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    company_jobs = [job for job in job_postings if job['company_username'] == session['username']]
    return render_template('manage_jobs.html', 
                         jobs=company_jobs, 
                         company_name=users[session['username']]['name'],
                         job_applications=job_applications)

@app.route('/view_applications')
def view_applications():
    if 'username' not in session or users[session['username']]['role'] != 'company':
        flash('Access denied')
        return redirect('/')
    
    # Get company's job IDs
    company_job_ids = [f"posted_{job['id']}" for job in job_postings if job['company_username'] == session['username']]
    
    # Get applications for company's jobs
    company_applications = [app for app in job_applications if app.get('job_id') in company_job_ids]
    
    return render_template('view_applications.html', 
                         applications=company_applications,
                         company_name=users[session['username']]['name'],
                         job_postings=job_postings,
                         users=users)

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
    
    return render_template('edit_job.html', job=job)

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

# Admin Routes
@app.route('/manage_all_jobs')
def manage_all_jobs():
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    return render_template('manage_all_jobs.html', 
                         jobs=job_postings, 
                         job_applications=job_applications)

@app.route('/manage_users')
def manage_users():
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    return render_template('manage_users.html', 
                         users=users, 
                         job_applications=job_applications,
                         job_postings=job_postings)

@app.route('/generate_report')
def generate_report():
    if 'username' not in session or users[session['username']]['role'] != 'admin':
        flash('Access denied')
        return redirect('/')
    
    # Calculate comprehensive statistics
    stats = {
        'total_users': len(users) - 1,  # Exclude admin
        'fresh_grads': len([u for u in users.values() if u.get('role') == 'fresh_grad']),
        'companies': len([u for u in users.values() if u.get('role') == 'company']),
        'total_jobs': len(job_postings),
        'approved_jobs': len([j for j in job_postings if j['status'] == 'approved']),
        'pending_jobs': len([j for j in job_postings if j['status'] == 'pending']),
        'rejected_jobs': len([j for j in job_postings if j['status'] == 'rejected']),
        'total_applications': len(job_applications),
        'accepted_apps': len([a for a in job_applications if a['status'] == 'accepted']),
        'pending_apps': len([a for a in job_applications if a['status'] == 'pending']),
        'rejected_apps': len([a for a in job_applications if a['status'] == 'rejected'])
    }
    
    return render_template('generate_report.html', stats=stats)

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
    user_activity = []
    if user_data['role'] == 'fresh_grad':
        user_applications = [app for app in job_applications if app.get('student') == username]
        user_activity = user_applications
    elif user_data['role'] == 'company':
        user_jobs = [job for job in job_postings if job.get('company_username') == username]
        user_activity = user_jobs
    
    return render_template('user_details.html', 
                         username=username,
                         user_data=user_data,
                         user_activity=user_activity)

# Admin action routes
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
        global job_applications
        job_applications = [app for app in job_applications if app.get('student') != username]
        
        # Remove user's job postings (if company)
        global job_postings
        job_postings = [job for job in job_postings if job.get('company_username') != username]
        
        flash(f'User "{user_name}" and all associated data deleted successfully!')
    else:
        flash('User not found or cannot be deleted!')
    
    return redirect('/manage_users')

if __name__ == "__main__":
    app.run(debug=True)