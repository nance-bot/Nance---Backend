# gmail_auth/pdf_utils.py

from pdfminer.high_level import extract_text

def extract_text_from_pdf(file_path):
    try:
        return extract_text(file_path)
    except Exception as e:
        print("PDF parse error:", e)
        return ""
