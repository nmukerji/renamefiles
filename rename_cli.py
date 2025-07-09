import argparse
import os
import shutil
from pathlib import Path
from app import (
    provider_keywords, purpose_keywords, rename_logic, UPLOAD_FOLDER, PROCESSED_FOLDER
)

def main():
    parser = argparse.ArgumentParser(description="Rename documents using OCR and keyword detection.")
    parser.add_argument('--files', nargs='+', required=True, help='Files to process (PDFs or images)')
    parser.add_argument('--custom-code', default='DOC', help='Custom code prefix for renamed files')
    parser.add_argument('--output-dir', default='processed', help='Directory to save renamed files')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"[ERROR] File not found: {filepath}")
            continue
        print(f"[INFO] Processing: {filepath}")
        new_name, fields = rename_logic(filepath, provider_keywords, purpose_keywords, args.custom_code)
        dest_path = os.path.join(args.output_dir, new_name)
        shutil.copy(filepath, dest_path)
        print(f"[RESULT] {os.path.basename(filepath)} -> {new_name}")
        print(f"         Fields: {fields}")

if __name__ == "__main__":
    main() 