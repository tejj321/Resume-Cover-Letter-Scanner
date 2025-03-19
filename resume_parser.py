import docx
import re

def extract_text_from_docx(file):
    """Extract text from a DOCX file using python-docx."""
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

def extract_resume_data(file):
    """Extracts structured data from a DOCX resume."""
    filename = file.filename.lower()
    
    if not filename.endswith(".docx"):
        raise ValueError("Unsupported file format. Please upload a DOCX file.")

    text = extract_text_from_docx(file)
    
    if not text:
        raise ValueError("Failed to extract text. Ensure the resume has readable content.")

    # Extract relevant fields using regex
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

    # Extract fields from resume using regex
    data = {key: re.search(pattern, text).group(1).strip() if re.search(pattern, text) else "" for key, pattern in patterns.items()}

    return data
