import os
import re
import shutil
import logging
from datetime import datetime
from pathlib import Path
import PyPDF2
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import sys
import dateparser

# --- Logging Setup ---
def setup_logging(folder_path):
    log_path = Path(folder_path) / 'rename_log.txt'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# --- Text Extraction for PDFs ---
def extract_text_from_pdf(pdf_path, max_pages=3):
    """Extracts and combines text from up to max_pages of a PDF, normalizing whitespace. Falls back to OCR if needed."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = min(len(pdf_reader.pages), max_pages)
            for i in range(num_pages):
                page = pdf_reader.pages[i]
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        # If no text found, try OCR on first 3 pages
        if not text.strip():
            images = convert_from_path(pdf_path, first_page=1, last_page=max_pages)
            for img in images:
                text += pytesseract.image_to_string(img) + "\n"
    except Exception as e:
        logging.error(f"Error extracting text from {pdf_path}: {e}")
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- Text Extraction for Images ---
def extract_text_from_image(image_path):
    """Extracts text from an image file using OCR, normalizing whitespace."""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        logging.error(f"Error extracting text from image {image_path}: {e}")
        return ""

# --- Document Classification ---
def classify_document(text):
    text_lower = text.lower()
    doc_types = {
        'BankStatement': ['statement period', 'account number', 'balance', 'chequing', 'savings', 'deposit', 'withdrawal', 'bank statement', 'chequing account statement'],
        'DonationReceipt': ['donation', 'thank you for your gift', 'charity', 'tax receipt', 'st jude', '501(c)(3)', 'donor', 'contribution'],
        'BirthdayCard': ['happy birthday', 'wishing you', 'celebrate', 'birthday wishes', 'congratulations on your birthday'],
        'Receipt': ['total', 'amount paid', 'thank you for your purchase', 'receipt', 'change due', 'cashier', 'store', 'purchase'],
        'Invoice': ['invoice', 'bill to', 'due date', 'amount due', 'invoice number', 'payment terms'],
        'Letter': ['dear', 'sincerely', 'regards', 'yours truly', 'correspondence'],
        'Report': ['executive summary', 'findings', 'conclusion', 'report', 'analysis', 'overview'],
        'Medical': ['patient', 'diagnosis', 'treatment', 'prescription', 'medical record', 'doctor', 'hospital'],
        'Insurance': ['policy number', 'claim', 'insurance', 'coverage', 'premium', 'insured'],
        'Legal': ['court', 'plaintiff', 'defendant', 'legal', 'case number', 'attorney', 'law firm'],
        'Travel': ['itinerary', 'flight', 'boarding pass', 'hotel', 'reservation', 'booking', 'departure', 'arrival'],
        'Education': ['transcript', 'grade', 'course', 'university', 'school', 'student', 'degree', 'diploma'],
        'Employment': ['resume', 'curriculum vitae', 'cv', 'job title', 'employer', 'employment', 'position'],
        'UtilityBill': ['utility bill', 'electricity', 'water', 'gas', 'account number', 'billing period'],
        'Tax': ['irs', 'tax year', 'taxpayer', 'tax return', 'form 1040', 'taxable', 'refund'],
        'Shipping': ['tracking number', 'shipment', 'delivery', 'shipping', 'carrier', 'package'],
        'EventTicket': ['admit one', 'ticket', 'event', 'seat', 'row', 'venue', 'showtime'],
        'Membership': ['membership', 'member id', 'renewal', 'expiration date', 'club', 'association'],
    }
    for doc_type, keywords in doc_types.items():
        for kw in keywords:
            if kw in text_lower:
                return doc_type
    return 'Document'

# --- Flexible Extraction Logic ---
def extract_abbrev_date_purpose(text):
    """
    Tries, in order:
    1. Regex: Abbreviation - [optional Date] - Purpose
    2. Purpose keywords: find line with best match to known purpose keywords
    3. Longest line (most text-rich)
    4. First 7 words of the document
    """
    # 1. Regex
    pattern = r'([A-Za-z0-9]+)\s*-\s*(?:(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*-\s*)?(.+?)(?=\s{2,}|$)'
    match = re.search(pattern, text)
    if match:
        abbrev = match.group(1)
        date = match.group(2)
        purpose = match.group(3).strip() if match.group(3) else None
        if purpose:
            return abbrev, date, purpose

    # 2. Purpose keywords
    purpose_keywords = [
        'statement period', 'invoice', 'donation', 'receipt', 'payment', 'thank you', 'account summary',
        'report', 'policy', 'claim', 'membership', 'grade', 'course', 'transcript', 'utility bill', 'tax year',
        'tracking number', 'event', 'admit one', 'boarding pass', 'reservation', 'prescription', 'diagnosis'
    ]
    lines = text.split('\n')
    best_line = None
    best_score = 0
    for line in lines:
        for kw in purpose_keywords:
            if kw in line.lower():
                # Score: longer match and more words is better
                score = len(kw) + len(line.split())
                if score > best_score:
                    best_score = score
                    best_line = line.strip()
    if best_line:
        return 'DOC', None, best_line

    # 3. Longest line (most text-rich)
    longest_line = max((l for l in lines if len(l.split()) > 3), key=len, default=None)
    if longest_line:
        return 'DOC', None, longest_line.strip()

    # 4. Fallback: first 7 words
    words = text.split()
    purpose = ' '.join(words[:7]) if words else 'Document'
    return 'DOC', None, purpose

def load_keywords(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def extract_provider(text, provider_keywords):
    """
    Extracts the provider/company/bank name from the top of the document.
    Looks for known names and also uses the first line(s) as a fallback.
    """
    lines = text.split('\n')
    # Check first 5 lines for provider
    for line in lines[:5]:
        for provider in provider_keywords:
            if provider.lower() in line.lower():
                return provider.replace(' ', '')
    # Fallback: use the first non-empty line, sanitized
    for line in lines:
        if line.strip():
            return re.sub(r'[^A-Za-z0-9]', '', line.strip())[:20]
    return 'UnknownProvider'

def extract_date(text):
    """
    Extracts the first date found in a wide variety of formats.
    Returns 'unknown' if no date is found.
    """
    # Regex for many date formats (e.g., June 5, 2003, 05/06/2003, 2003-06-05, 5 June 2003, etc.)
    date_patterns = [
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s*\d{4}\b',  # June 5, 2003
        r'\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?),?\s*\d{4}\b',  # 5 June 2003
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # 05/06/2003 or 5-6-03
        r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',    # 2003-06-05
        r'\b\d{1,2}\s+\w+\s+\d{4}\b',          # 5 June 2003
    ]
    for pattern in date_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            date = dateparser.parse(match.group(0), settings={'PREFER_DATES_FROM': 'past'})
            if date:
                return date.strftime('%m.%d.%Y')
    return 'unknown'

def extract_purpose(text, purpose_keywords):
    """
    Extracts the document purpose using a prioritized list of types.
    """
    for kw in purpose_keywords:
        if kw in text.lower():
            return kw.title().replace(' ', '')
    return 'UnknownPurpose'

# --- Main Renaming Logic ---
def process_file(file_path, processed_dir, provider_keywords, purpose_keywords):
    try:
        ext = file_path.suffix.lower()
        if ext in ['.pdf']:
            text = extract_text_from_pdf(file_path)
        elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            text = extract_text_from_image(file_path)
        else:
            logging.warning(f"Unsupported file type: {file_path.name}")
            return

        abbrev = 'DOC'
        date = extract_date(text)
        provider = extract_provider(text, provider_keywords)
        purpose = extract_purpose(text, purpose_keywords)

        # If any field is missing, use 'unknown' (already handled above)
        new_name = f"{abbrev}-{date}-{provider}-{purpose}{ext}"
        new_name = re.sub(r'[<>:"/\\|?*]', '_', new_name)
        new_name = re.sub(r'\s+', '_', new_name)
        if len(new_name) > 100:
            name, ext2 = os.path.splitext(new_name)
            new_name = name[:100-len(ext2)] + ext2

        dest_path = processed_dir / new_name
        counter = 1
        while dest_path.exists():
            name, ext2 = os.path.splitext(new_name)
            dest_path = processed_dir / f"{name}({counter}){ext2}"
            counter += 1
        shutil.move(str(file_path), str(dest_path))
        logging.info(f"Renamed {file_path.name} to {dest_path.name}")
        return new_name

    except Exception as e:
        logging.error(f"Error processing {file_path.name}: {e}")
        return None

# --- Main Batch Processing ---
def batch_rename(folder_path, provider_keywords, purpose_keywords):
    folder = Path(folder_path)
    processed_dir = folder / 'Processed'
    processed_dir.mkdir(exist_ok=True)
    setup_logging(folder)
    for file_path in folder.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            process_file(file_path, processed_dir, provider_keywords, purpose_keywords)

# --- Run Script ---
if __name__ == "__main__":
    provider_keywords = load_keywords('provider_keywords.txt')
    purpose_keywords = load_keywords('purpose_keywords.txt')
    folder_path = sys.argv[1] if len(sys.argv) > 1 else "pdfs"
    batch_rename(folder_path, provider_keywords, purpose_keywords) 