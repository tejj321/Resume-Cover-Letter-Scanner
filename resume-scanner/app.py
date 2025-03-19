import os
import re
import chardet
from flask import Flask, render_template, request, redirect, url_for, flash, session
from docx import Document
import psycopg2
import hashlib

app = Flask(__name__)

# Secret Key for Flask session
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')

# Configure the database connection
DATABASE_URI = "postgresql://postgres:admin@localhost:5432/resume_scanner"

# Function to read a DOCX file and extract text
def extract_text_from_docx(file):
    """Extract text from a DOCX file."""
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# Function to read the cover letter with automatic encoding detection
def read_cover_letter_with_encoding(file):
    """Read the cover letter and handle different encodings."""
    raw_data = file.read(10000)
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    file.seek(0)  # Reset the file pointer to the beginning
    try:
        return file.read().decode(encoding)
    except (UnicodeDecodeError, TypeError):
        return file.read().decode('utf-8', errors='ignore')

# Function to extract resume data from the DOCX text
def extract_resume_data(text):
    """Extract structured data from DOCX resume text."""
    patterns = {
        "Age": r"Age:\s*(\d+)",
        "Experience (Years)": r"Experience \(Years\):\s*(\d+)",
        "Education": r"Education:\s*(.+)",
        "Skills": r"Skills:\s*(.+)",
        "Certifications": r"Certifications:\s*(.+)",
        "Region": r"Region:\s*(.+)",
        "Languages Spoken": r"Languages Spoken:\s*(.+)",
        "Previous Job Role": r"Previous Job Role:\s*(.+)",
        "Location": r"Location:\s*(.+)",
        "Education Institution": r"Education Institution:\s*(.+)"
    }
    data = {key: re.search(pattern, text).group(1).strip() if re.search(pattern, text) else "" for key, pattern in patterns.items()}
    return data

# Function to preprocess input data (you can apply label encoding or other processing here)
def preprocess_input(resume_data):
    """Preprocess the resume data for model input."""
    return resume_data

# Function to analyze the job suitability (replace with your actual model)
def analyze_suitability(resume_data, selected_roles):
    """Simulate analyzing job suitability and return percentage suitability."""
    results = {}
    for role in selected_roles:
        score = 0
        total_criteria = 0
        experience_years = int(resume_data.get("Experience (Years)", 0))

        if role == "Accountant":
            total_criteria += 1
            if resume_data.get("Education") in ["Bachelor's Degree", "Master’s Degree"]:
                score += 1

        elif role == "Chemical Engineer":
            total_criteria += 1
            if experience_years > 2:
                score += 1

        if total_criteria > 0:
            suitability_percentage = (score / total_criteria) * 100
        else:
            suitability_percentage = 0
        
        results[role] = {
            "Suitability": "Suitable" if suitability_percentage >= 50 else "Not Suitable",
            "Suitability Percentage": round(suitability_percentage, 2)
        }
    
    return results

# Database connection function
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URI)
    return conn

# Function to check if the user exists and verify password
def check_user_login(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and hashlib.sha256(password.encode()).hexdigest() == user[3]:  # Compare hashed password
        return user
    return None

# Function to register a new user
def register_user(email, password, role):
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (email, password, role) VALUES (%s, %s, %s)", (email, hashed_password, role))
    conn.commit()
    conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle the login page."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check user credentials in the database
        user = check_user_login(email, password)

        if user:
            session['user_id'] = user[0]  # Store the user ID in the session
            session['user_role'] = user[4]  # Store the user role in the session
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle the registration page."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # Role: 'Admin' or 'User'

        # Check if the email already exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            flash('Email already registered. Please log in.', 'danger')
            return redirect(url_for('login'))

        # Register the user
        register_user(email, password, role)
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route("/", methods=["GET", "POST"])
def index():
    """Handle the file upload and analysis."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        resume_file = request.files["resume"]
        cover_letter_file = request.files["cover_letter"]

        try:
            # Extract text from resume and cover letter
            resume_text = extract_text_from_docx(resume_file)
            cover_letter_text = read_cover_letter_with_encoding(cover_letter_file)
        except Exception as e:
            return f"Error processing file: {str(e)}", 400

        # Extract resume data
        resume_data = extract_resume_data(resume_text)
        resume_data["Cover Letter"] = cover_letter_text

        # Get the selected roles from the checkbox
        selected_roles = request.form.getlist("role")  # This returns a list of selected roles

        # Preprocess the input data (e.g., numerical encoding, etc.)
        resume_data = preprocess_input(resume_data)

        # Analyze suitability based on the selected roles
        results = analyze_suitability(resume_data, selected_roles)

        # Return the results to the user
        return render_template("result.html", results=results)

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
