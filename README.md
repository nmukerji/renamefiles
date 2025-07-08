# PDF/Image Renamer Tool

## Overview
This tool automatically renames PDF and image files based on their content, extracting provider, date, and document purpose using OCR and keyword lists. It features a Flask backend and a drag-and-drop HTML frontend.

## Setup Instructions

### 1. Install Dependencies

You need Python 3.8+ and the following packages:

```sh
pip install flask PyPDF2 pytesseract pdf2image pillow dateparser
```

You also need to install Tesseract OCR and poppler:
- **macOS:**
  ```sh
  brew install tesseract poppler
  ```
- **Ubuntu:**
  ```sh
  sudo apt-get install tesseract-ocr poppler-utils
  ```

### 2. Required Files

Create two keyword files in the project root:

- `provider_keywords.txt` — one provider/company per line (e.g. Chase, Bank of America, etc.)
- `purpose_keywords.txt` — one document purpose per line (e.g. Invoice, Statement, Legal, BankStatement, etc.)

**Example:**

`provider_keywords.txt`
```
Chase
Bank of America
Wells Fargo
Citi
```

`purpose_keywords.txt`
```
Invoice
Statement
Legal
BankStatement
```

### 3. Run the App

```sh
python3 app.py
```

Visit [http://localhost:5000](http://localhost:5000) in your browser. Use the drag-and-drop interface to upload files. Renamed files will be available for download.

### 4. Notes
- The app creates `uploads/` and `processed/` folders automatically.
- If a keyword is not found, the filename will use `UnknownProvider` or `UnknownPurpose`.
- All renaming logic is in `app.py`. You can expand the keyword lists as needed.
- For best OCR results, ensure Tesseract and poppler are installed and in your PATH. 

## Project Structure (Required for Flask App)

Your project root should look like this:

```
CS_external/
  app.py
  index.html
  provider_keywords.txt
  purpose_keywords.txt
  uploads/         # auto-created by app.py
  processed/       # auto-created by app.py
  archive_scripts/ # (optional, for old scripts)
```

- Only the files above are needed for the web renamer app.
- The `archive_scripts/` folder is for any old scripts you want to keep but not use with the Flask app.
- You do NOT need `rename_pdfs.py`, PowerShell scripts, or the `Renaming/` folder for the web app to work. 