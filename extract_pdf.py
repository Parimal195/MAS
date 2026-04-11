#!/usr/bin/env python3

import PyPDF2
import sys

def extract_pdf_text(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ''
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += f'\n=== PAGE {page_num + 1} ===\n'
                text += page_text + '\n'

            return text
    except Exception as e:
        print(f"Error reading PDF: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    pdf_path = "Stablecoin Wallet PRD.pdf"
    extracted_text = extract_pdf_text(pdf_path)

    if extracted_text:
        print("=== PDF EXTRACTION SUCCESSFUL ===")
        print(extracted_text)
        print("=== END OF PDF CONTENT ===")
    else:
        print("Failed to extract PDF content")