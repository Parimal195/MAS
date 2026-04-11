"""
=============================================================================
 📄 PDF COMPILER MODULE (pdf_utils.py)
 
 What this file does in plain English:
 The Artificial Intelligence naturally speaks in a messy computer text format 
 called "Markdown". This file acts as a translator and a designer. 
 It takes the raw text from the AI, injects some pretty visual styling (CSS), 
 and exports it as a professional, physical PDF document that can be emailed.
=============================================================================
"""

import markdown # Tool to read the strange markdown syntax (like converting **bold** to actual bold text)
from xhtml2pdf import pisa # Tool to draw HTML text into a literal printable PDF
import os # Tool to handle folder directories
from datetime import datetime # Tool to read the physical time on the clock

def markdown_to_pdf(markdown_content: str, output_folder: str = "reports", is_manual: bool = False) -> str:
    """
    Converts a generic markdown string to a PDF format and saves it to the hard drive.
    """
    
    # 1. Folder Management: Check if the "reports" folder exists. If not, make it!
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    # 2. File Naming Rules
    if is_manual:
        # If a human clicked the button on the UI, we stamp it with seconds so we don't accidentally
        # overwrite a PDF we made 5 minutes ago!
        date_str = datetime.now().strftime("%d-%m-%y-%H%M%S")
        prefix = "instant-report"
    else:
        # If it's the daily background robot, it just strictly names it today's simple date.
        date_str = datetime.now().strftime("%d-%m-%y")
        prefix = "report"
        
    # Combine everything to get the final path (e.g., "reports/report-11-04-26.pdf")
    output_filename = os.path.join(output_folder, f"{prefix}-{date_str}.pdf")
    
    # 3. The Stylist (CSS)
    # This block of code teaches the PDF builder how things should look visually.
    # What fonts to use, what colors to make the headers, how wide the margins are, etc.
    css = """
    @page {
        size: a4 portrait;
        margin: 2cm;
    }
    body { font-family: Helvetica, Muli, sans-serif; font-size: 11pt; color: #1a1a1a; line-height: 1.5; }
    h1 { color: #000; font-size: 24pt; border-bottom: 2px solid #000; padding-bottom: 5px; margin-bottom: 20px;}
    h2 { color: #2c3e50; font-size: 18pt; margin-top: 25px; border-bottom: 1px solid #ccc; padding-bottom: 3px;}
    h3 { color: #34495e; font-size: 14pt; margin-top: 15px;}
    p { margin-bottom: 10px; }
    ul { margin-bottom: 15px; }
    li { margin-bottom: 5px; }
    code { font-family: Courier, monospace; background-color: #f4f4f4; padding: 2px 4px; font-size: 10pt; }
    """
    
    # 4. Conversion Phase
    # Convert the Asterisks and Hashes into standard Webpage HTML format
    html_content = markdown.markdown(markdown_content, extensions=['tables'])
    
    # Wrap that Webpage inside the CSS aesthetics we built above
    full_html = f"<html><head><style>{css}</style></head><body>{html_content}</body></html>"
    
    # 5. Drawing the PDF
    # Open a blank file on the hard drive...
    with open(output_filename, "wb") as pdf_file:
        # Tell the "pisa" tool to draw our stylized webpage directly into the blank physical PDF file
        pisa_status = pisa.CreatePDF(full_html, dest=pdf_file)
        
    # Safety Check: If it failed to draw the PDF, scream loud!
    if pisa_status.err:
        raise Exception("Failed to generate PDF report")
        
    # Return the exact location on the hard drive where we saved the new PDF, so the email tool can find it!
    return output_filename
