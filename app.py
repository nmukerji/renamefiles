# === OCR/Document Analysis Enhancement Suggestions ===
# For best results with logos, fonts, and complex layouts, consider using a commercial OCR API:
# - Google Cloud Vision API: https://cloud.google.com/vision/docs/ocr
# - AWS Textract: https://aws.amazon.com/textract/
# - Microsoft Azure Computer Vision: https://azure.microsoft.com/en-us/products/ai-services/computer-vision/
# These APIs can detect text, logos, and document structure with much higher accuracy than Tesseract.
# To use, sign up for the service, get API credentials, and use their Python SDK to send images and receive structured results.
# ================================================

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
import numpy as np

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

STRONG_BRANDS = [
    # Airlines
    'Delta', 'American Airlines', 'United', 'Southwest', 'JetBlue', 'Alaska', 'Spirit', 'Frontier',
    'Hawaiian Airlines', 'Allegiant', 'Sun Country', 'British Airways', 'Lufthansa', 'Air France',
    'KLM', 'Qantas', 'Emirates', 'Qatar Airways', 'Singapore Airlines', 'Turkish Airlines',
    'Air Canada', 'ANA', 'JAL', 'Aeromexico', 'Avianca', 'Copa Airlines', 'LATAM',
    # Banks & Financial (expanded)
    'Chase', 'Bank of America', 'Wells Fargo', 'Citi', 'Citibank', 'PNC', 'Capital One', 'US Bank', 'Barclays',
    'ING', 'HSBC', 'Santander', 'TD Bank', 'BBVA', 'SunTrust', 'Regions', 'Fifth Third', 'KeyBank',
    'Ally', 'Charles Schwab', 'Fidelity', 'Robinhood', 'Vanguard', 'PayPal', 'Venmo', 'Zelle',
    'Discover', 'Synchrony', 'American Express', 'Mastercard', 'Visa', 'BMO', 'M&T Bank', 'Huntington',
    'Citizens Bank', 'First Republic', 'Silicon Valley Bank', 'Truist', 'Navy Federal', 'USAA', 'BECU',
    'TD Ameritrade', 'Morgan Stanley', 'Goldman Sachs', 'Credit Suisse', 'UBS', 'RBC', 'Scotiabank',
    'Desjardins', 'CIBC', 'National Bank', 'Société Générale', 'BNP Paribas', 'Deutsche Bank',
    # Restaurants (fast food and sit-down)
    'McDonald\'s', 'Burger King', 'Wendy\'s', 'Taco Bell', 'KFC', 'Subway', 'Domino\'s', 'Pizza Hut',
    'Papa John\'s', 'Dunkin\' Donuts', 'Starbucks', 'Chipotle', 'Panera', 'Chick-fil-A', 'Sonic',
    'Arby\'s', 'Jack in the Box', 'Little Caesars', 'Panda Express', 'Five Guys', 'Culver\'s',
    'In-N-Out', 'Shake Shack', 'Buffalo Wild Wings', 'Applebee\'s', 'Olive Garden', 'Red Lobster',
    'Outback Steakhouse', 'IHOP', 'Denny\'s', 'Cheesecake Factory', 'Texas Roadhouse', 'Chili\'s',
    'Cracker Barrel', 'Carrabba\'s', 'Bonefish Grill', 'P.F. Chang\'s', 'Ruth\'s Chris',
    # Retailers & Online
    'Lowe\'s', 'Home Depot', 'Costco', 'Walmart', 'Target', 'Amazon', 'Apple', 'Google', 'Microsoft',
    'Best Buy', 'Staples', 'Office Depot', 'Sam\'s Club', 'Kroger', 'Publix', 'Walgreens', 'CVS',
    'Rite Aid', 'Macy\'s', 'Nordstrom', 'Kohl\'s', 'JCPenney', 'Sears', 'IKEA', 'Wayfair',
    # Travel & Hospitality
    'Hilton', 'Marriott', 'Hyatt', 'IHG', 'Holiday Inn', 'Hampton', 'Sheraton', 'Westin', 'Radisson',
    'Expedia', 'Booking.com', 'Airbnb', 'VRBO', 'Enterprise', 'Hertz', 'Avis', 'Budget', 'National',
    'Uber', 'Lyft', 'Amtrak', 'Greyhound',
    # Utilities & Telecom
    'Comcast', 'Xfinity', 'AT&T', 'Verizon', 'T-Mobile', 'Sprint', 'Spectrum', 'Cox', 'DirectTV',
    # Insurance & Medical (expanded)
    'Aetna', 'Cigna', 'UnitedHealthcare', 'Blue Cross', 'Kaiser', 'MetLife', 'Allstate', 'State Farm',
    'Geico', 'Progressive', 'Liberty Mutual', 'Humana', 'Anthem', 'Guardian', 'Mutual of Omaha',
    'Transamerica', 'Prudential', 'New York Life', 'MassMutual', 'Banner Life', 'Lincoln Financial',
    'Delta Dental', 'VSP', 'Blue Shield', 'Health Net', 'Oscar', 'Molina', 'Centene', 'WellCare',
    'Magellan', 'Cleveland Clinic', 'Mayo Clinic', 'Johns Hopkins', 'Cleveland Clinic', 'HCA Healthcare',
    'Tenet Healthcare', 'Ascension', 'Sutter Health', 'Dignity Health',
    # Education & Nonprofit
    'MIT', 'Harvard', 'Stanford', 'Yale', 'Princeton', 'Cornell', 'UCLA', 'NYU', 'Columbia',
    'St. Jude', 'Red Cross', 'UNICEF', 'Doctors Without Borders',
    # Government & Tax
    'IRS', 'Social Security', 'US Treasury', 'DMV', 'SSA', 'Medicare', 'Medicaid',
    # Add more as needed for your use case
]

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
    img = enhancer.enhance(3)  # More aggressive contrast
    # Use NumPy for binarization
    arr = np.array(img)
    arr = np.where(arr > 128, 255, 0).astype(np.uint8)
    img = Image.fromarray(arr, mode='L').convert('1')
    return img

def ocr_with_best_psm(img):
    psm_modes = [6, 7, 11]
    results = []
    for psm in psm_modes:
        try:
            text = pytesseract.image_to_string(img, config=f'--psm {psm}')
            results.append((text, psm))
        except Exception as e:
            print(f"[ERROR] Tesseract OCR failed with psm {psm}: {e}")
    # Pick the result with the most text
    best = max(results, key=lambda x: len(x[0].strip()) if x[0] else 0)
    print(f"[DEBUG_OCR] Best OCR result (psm {best[1]}):\n{best[0][:1000]}")
    return best[0]

def extract_text_from_image(image_path):
    try:
        img = preprocess_image(image_path)
        text = ocr_with_best_psm(img)
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
    # 1. Try strong brands in header (whole word, min length 3)
    for keyword in STRONG_BRANDS:
        if keyword_in_text(keyword, header):
            provider = keyword
            found_in_header = True
            break
    # 2. Try provider_keywords in header (whole word, min length 4 or in strong brands)
    if not found_in_header:
        for keyword in provider_keywords:
            if (len(keyword) >= 4 or keyword in STRONG_BRANDS) and keyword_in_text(keyword, header):
                provider = keyword
                found_in_header = True
                break
    # 3. Fallback: try strong brands in full text
    if not found_in_header:
        for keyword in STRONG_BRANDS:
            if keyword_in_text(keyword, norm_text):
                provider = keyword
                found_in_header = True
                break
    # 4. Fallback: try provider_keywords in full text (whole word, min length 4 or in strong brands)
    if not found_in_header:
        for keyword in provider_keywords:
            if (len(keyword) >= 4 or keyword in STRONG_BRANDS) and keyword_in_text(keyword, norm_text):
                provider = keyword
                found_in_header = True
                break
    # 5. Fuzzy fallback (only for keywords with len >= 4 or in strong brands)
    if not found_in_header:
        candidates = [k for k in provider_keywords if len(k) >= 4 or k in STRONG_BRANDS]
        matches = process.extract(norm_text, [normalize_text(k) for k in candidates], scorer=fuzz.partial_ratio, limit=1)
        if matches and matches[0][1] >= threshold:
            idx = [normalize_text(k) for k in candidates].index(matches[0][0])
            provider = candidates[idx]

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

def rename_logic(filepath, provider_keywords, purpose_keywords, custom_code='DOC'):
    ext = Path(filepath).suffix.lower()
    if ext == '.pdf':
        text = extract_text_from_pdf(filepath)
    else:
        text = extract_text_from_image(filepath)
    print(f"[DEBUG] Extracted text for {filepath}: {text[:300]}")
    abbrev = custom_code if custom_code else 'DOC'
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
    custom_code = request.form.get('custom_code', 'DOC')
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
            renamed, fields = rename_logic(save_path, provider_keywords, purpose_keywords, custom_code)
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