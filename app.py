from flask import Flask, request, send_from_directory, jsonify
import os
from pathlib import Path
import shutil
import re
import string
import PyPDF2
import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter
import dateparser
from rapidfuzz import fuzz, process

def load_keywords(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Keyword file not found: {filename}. Using empty list.")
        return []

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
provider_keywords = load_keywords(os.path.join(BASE_DIR, 'provider_keywords.txt'))
purpose_keywords = load_keywords(os.path.join(BASE_DIR, 'purpose_keywords.txt'))

BANK_ASSOCIATIONS = ['bank', 'account', 'statement', 'checking', 'savings', 'balance']

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def normalize_text(text):
    # Lowercase, remove punctuation, and normalize whitespace
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def keyword_in_text(keyword, text):
    # Match as a whole word, case-insensitive
    return re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text.lower()) is not None

def extract_text_from_pdf(pdf_path, max_pages=3):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = min(len(pdf_reader.pages), max_pages)
            for i in range(num_pages):
                page = pdf_reader.pages[i]
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        if not text.strip():
            images = convert_from_path(pdf_path, first_page=1, last_page=max_pages)
            for img in images:
                try:
                    ocr_text = pytesseract.image_to_string(img)
                    text += ocr_text + "\n"
                except Exception as ocr_e:
                    print(f"[ERROR] Tesseract OCR failed for {pdf_path}: {ocr_e}")
    except Exception as e:
        print(f"[ERROR] Extracting text from {pdf_path}: {e}")
    text = re.sub(r'\s+', ' ', text).strip()
    print(f"[DEBUG] Extracted text for {pdf_path} (first 500 chars): {text[:500]}")
    if not text:
        print(f"[WARN] OCR/text extraction returned empty for {pdf_path}")
    return text

def preprocess_image(image_path):
    img = Image.open(image_path).convert('L')  # Grayscale
    img = img.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)
    return img

def extract_text_from_image(image_path):
    try:
        img = preprocess_image(image_path)
        text = pytesseract.image_to_string(img, config='--psm 6')
        text = re.sub(r'\s+', ' ', text).strip()
        print(f"[DEBUG] Extracted text for {image_path} (first 500 chars): {text[:500]}")
        if not text:
            print(f"[WARN] OCR returned empty for image {image_path}")
        return text
    except Exception as e:
        print(f"[ERROR] Extracting text from image {image_path}: {e}")
        return ""

def extract_provider_and_purpose(text, provider_keywords, purpose_keywords, threshold=85):
    norm_text = normalize_text(text)
    provider = 'UnknownProvider'
    purpose = 'UnknownPurpose'

    # Provider: prioritize header (first 5 lines)
    lines = text.split('\n')
    header = ' '.join(lines[:5])
    found_in_header = False
    for keyword in provider_keywords:
        if keyword_in_text(keyword, header):
            provider = keyword
            found_in_header = True
            break
    if not found_in_header:
        # Association logic: if bank/account words are present, prioritize bank providers
        if any(word in norm_text for word in BANK_ASSOCIATIONS):
            bank_providers = [k for k in provider_keywords if 'bank' in k.lower()]
            for keyword in bank_providers:
                if keyword_in_text(keyword, norm_text):
                    provider = keyword
                    break
            else:
                matches = process.extract(norm_text, [normalize_text(k) for k in bank_providers], scorer=fuzz.partial_ratio, limit=1)
                if matches and matches[0][1] >= threshold:
                    idx = [normalize_text(k) for k in bank_providers].index(matches[0][0])
                    provider = bank_providers[idx]
        else:
            # Fallback to original logic with whole-word matching
            for keyword in provider_keywords:
                if keyword_in_text(keyword, norm_text):
                    provider = keyword
                    break
            else:
                matches = process.extract(norm_text, [normalize_text(k) for k in provider_keywords], scorer=fuzz.partial_ratio, limit=1)
                if matches and matches[0][1] >= threshold:
                    idx = [normalize_text(k) for k in provider_keywords].index(matches[0][0])
                    provider = provider_keywords[idx]

    # Purpose: search whole text for keywords (can expand with context if needed)
    for keyword in purpose_keywords:
        if keyword_in_text(keyword, norm_text):
            purpose = keyword
            break
    else:
        matches = process.extract(norm_text, [normalize_text(k) for k in purpose_keywords], scorer=fuzz.partial_ratio, limit=1)
        if matches and matches[0][1] >= threshold:
            idx = [normalize_text(k) for k in purpose_keywords].index(matches[0][0])
            purpose = purpose_keywords[idx]
    return provider, purpose

def extract_date(text):
    date_patterns = [
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s*\d{4}\b',
        r'\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?),?\s*\d{4}\b',
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
        r'\b\d{1,2}\s+\w+\s+\d{4}\b',
        r'\b\d{4}\b',  # fallback: just a year
    ]
    for pattern in date_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            date = dateparser.parse(match.group(0), settings={'PREFER_DATES_FROM': 'past'})
            if date:
                return date.strftime('%m.%d.%Y')
    return 'unknown'

def rename_logic(filepath, provider_keywords, purpose_keywords):
    ext = Path(filepath).suffix.lower()
    if ext == '.pdf':
        text = extract_text_from_pdf(filepath)
    else:
        text = extract_text_from_image(filepath)
    print(f"[DEBUG] Extracted text for {filepath}: {text[:300]}")
    abbrev = 'DOC'
    date = extract_date(text)
    provider, purpose = extract_provider_and_purpose(text, provider_keywords, purpose_keywords)
    print(f"[DEBUG] Fields for {filepath}: date={date}, provider={provider}, purpose={purpose}")
    new_name = f"{abbrev}-{date}-{provider}-{purpose}{ext}"
    new_name = re.sub(r'[<>:"/\\|?*]', '_', new_name)
    new_name = re.sub(r'\s+', '_', new_name)
    if len(new_name) > 100:
        name, ext2 = os.path.splitext(new_name)
        new_name = name[:100-len(ext2)] + ext2
    return new_name, {'date': date, 'provider': provider, 'purpose': purpose, 'text': text[:500]}

app = Flask(__name__)

@app.route('/debug_ocr', methods=['POST'])
def debug_ocr():
    file = request.files['file']
    filename = str(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)
    ext = Path(save_path).suffix.lower()
    if ext == '.pdf':
        text = extract_text_from_pdf(save_path)
    else:
        text = extract_text_from_image(save_path)
    print(f"[DEBUG_OCR] Extracted text for {save_path}: {text[:1000]}")
    return jsonify({'filename': filename, 'text': text[:1000]})

@app.route('/upload', methods=['POST'])
def upload_files():
    files = request.files.getlist('files')
    results = []
    for file in files:
        filename = str(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        try:
            file_size = os.path.getsize(save_path)
            print(f"[UPLOAD] Saved file to {save_path} (size: {file_size} bytes)")
            ext = Path(save_path).suffix.lower()
            print(f"[UPLOAD] File extension: {ext}")
            renamed, fields = rename_logic(save_path, provider_keywords, purpose_keywords)
            print(f"[UPLOAD] Renamed: {renamed}")
            print(f"[UPLOAD] Extracted fields: {fields}")
            if not renamed or not isinstance(renamed, str):
                renamed = 'UnknownFile' + os.path.splitext(str(filename))[1]
            shutil.copy(save_path, os.path.join(PROCESSED_FOLDER, str(renamed)))
            results.append({'original': filename, 'renamed': renamed, 'status': 'success', 'fields': fields})
        except Exception as e:
            print(f"[ERROR] Processing {filename}: {e}")
            results.append({'original': filename, 'renamed': None, 'status': 'error', 'error': str(e)})
    return jsonify({'files': results})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(PROCESSED_FOLDER, filename, as_attachment=True)

@app.route('/')
def index():
    return open('index.html').read()

if __name__ == "__main__":
    app.run(debug=True, port=5001)