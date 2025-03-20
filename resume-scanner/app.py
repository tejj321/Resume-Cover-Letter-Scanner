import os
import re
import chardet
import pickle
from flask import Flask, render_template, request, redirect, url_for, flash, session
from docx import Document
import psycopg2
import hashlib
import tensorflow as tf
from tensorflow.keras.models import load_model
import numpy as np
from tensorflow.keras.preprocessing.text import tokenizer_from_json
from sklearn.preprocessing import OneHotEncoder

app = Flask(__name__)

# Secret key for session management (make sure this is kept secure)
app.secret_key = os.environ.get('SECRET_KEY', 'your_default_secret_key')

# Configure the database connection
DATABASE_URI = "postgresql://postgres:admin@localhost:5432/resume_scanner"

# Load the trained model
model = load_model('model/model.h5')

# Load scaler and tokenizer from the model folder
with open('model/scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)

with open('tokenizer.pkl', 'rb') as f:
    tokenizer = pickle.load(f)

# Function to read a DOCX file and extract text
def extract_text_from_docx(file):
    """Extract text from a DOCX file."""
    doc = Document(file)
    return "\n".join(para.text for para in doc.paragraphs)

# Function to read cover letter with automatic encoding detection
# Function to read the cover letter with automatic encoding detection
def read_cover_letter_with_encoding(file):
    """Read the cover letter and handle different encodings safely."""
    raw_data = file.read(10000)  # Read a chunk of data for encoding detection
    result = chardet.detect(raw_data)
    encoding = result['encoding'] if result['encoding'] else 'utf-8'  # Default to UTF-8 if encoding is None
    file.seek(0)  # Reset the file pointer to the beginning

    try:
        return file.read().decode(encoding, errors='ignore')
    except (UnicodeDecodeError, TypeError):
        return file.read().decode('utf-8', errors='ignore')  # Default fallback

# Function to extract structured resume data
def extract_resume_data(text):
    """Extract structured data from DOCX resume text."""
    patterns = {
        "Age": r"Age:\s*(\d+)",
        "Experience (Years)": r"Experience \(Years\):\s*(\d+)",
        "Education": r"Education:\s*(.+)",
        "Skills": r"Skills:\s*(.+)",
        "Certifications": r"Certifications:\s*(.+)",
    }
    return {key: re.search(pattern, text).group(1).strip() if re.search(pattern, text) else "" for key, pattern in patterns.items()}

# Function to preprocess the resume data
# Function to preprocess the resume data
def preprocess_resume_data(resume_data):
    """Preprocess numerical resume data."""
    def safe_int(value):
        """Convert value to int, return 0 if invalid."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    # Extract numerical features
    numerical_data = np.array([
        safe_int(resume_data.get("Age", 0)),
        safe_int(resume_data.get("Experience (Years)", 0)),
        safe_int(resume_data.get("Certifications", 0))
    ]).reshape(1, -1)

    # Ensure it matches the format scaler was trained on
    numerical_data = np.asarray(numerical_data, dtype=np.float32)  # Convert to float32

    return scaler.transform(numerical_data)  # Scale numerical data


# Function to preprocess the cover letter
def preprocess_cover_letter(text, max_len=50):
    """Preprocess cover letter text using tokenizer."""
    sequences = tokenizer.texts_to_sequences([text])
    
    # Check if the tokenized sequence is empty
    if not sequences or len(sequences[0]) == 0:
        sequences = [[0]]  # Avoid empty sequence issues
    
    return tf.keras.preprocessing.sequence.pad_sequences(sequences, maxlen=max_len, padding='post')

# Database connection function
def get_db_connection():
    return psycopg2.connect(DATABASE_URI)

# Function to check user credentials
def check_user_login(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and hashlib.sha256(password.encode()).hexdigest() == user[3]:
        return user
    return None

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login requests."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = check_user_login(email, password)

        if user:
            session['user_id'] = user[0]
            session['user_role'] = user[4]
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle registration requests."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        role = request.form['role']

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password, name, role) VALUES (%s, %s, %s, %s)",
                       (email, hashed_password, name, role))
        conn.commit()
        conn.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Home route
@app.route('/index')
def index():
    """Render the main page after login."""
    return render_template('index.html')
# About Page
@app.route('/about')
def about():
    """Render the About page."""
    return render_template('about.html')

# Privacy Policy / Terms of Use Page
@app.route('/privacy')
def privacy():
    """Render the Privacy Policy page."""
    return render_template('privacy.html')


# Upload and analyze resume
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handle resume and cover letter upload."""
    if request.method == 'POST':
        resume_file = request.files['resume']
        cover_letter_file = request.files['cover_letter']
        selected_roles = request.form.getlist('role')
        print("Selected Roles:", selected_roles)  # Debugging

        if not selected_roles:
            flash("No roles selected. Please choose at least one.", "danger")
            return redirect(url_for('upload_file'))

        if resume_file and cover_letter_file:
            resume_text = extract_text_from_docx(resume_file)
            cover_letter_text = read_cover_letter_with_encoding(cover_letter_file)

            resume_data = extract_resume_data(resume_text)
            preprocessed_resume_data = preprocess_resume_data(resume_data)
            preprocessed_cover_letter = preprocess_cover_letter(cover_letter_text)

            print("Resume Data Shape:", preprocessed_resume_data.shape)
            print("Cover Letter Data Shape:", preprocessed_cover_letter.shape)

            # Predict using the model (only **once**)
            prediction = model.predict([preprocessed_resume_data, preprocessed_cover_letter])
            print("Raw Model Predictions:", prediction)

            results = {}

            # Function to determine suitability text
            def get_suitability_text(score):
                if score >= 80:
                    return "Highly Suitable"
                elif 70 <= score < 80:
                    return "Suitable"
                elif 60 <= score < 70:
                    return "Not So Suitable"
                else:
                    return "Not Suitable"

            # Compute separate scores for each role
            if "Chemical Engineer" in selected_roles:
                chem_eng_score = prediction[0][0] * 100  # First column is Chemical Engineer
                results["Chemical Engineer"] = {
                    "resume_score": chem_eng_score,
                    "cover_letter_score": chem_eng_score,  # Adjust based on model output
                    "average_score": chem_eng_score,
                    "suitability_text": get_suitability_text(chem_eng_score)
                }

            if "Accountant" in selected_roles:
                accountant_score = prediction[0][1] * 100  # Second column is Accountant
                results["Accountant"] = {
                    "resume_score": accountant_score,
                    "cover_letter_score": accountant_score,  # Adjust based on model output
                    "average_score": accountant_score,
                    "suitability_text": get_suitability_text(accountant_score)
                }

            return render_template('result.html', results=results)

    return render_template('upload.html')



if __name__ == '__main__':
    app.run(debug=True)
