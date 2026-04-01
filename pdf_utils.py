import markdown
from xhtml2pdf import pisa
import os
from datetime import datetime

def markdown_to_pdf(markdown_content: str, output_folder: str = "reports") -> str:
    """Converts a markdown string to a PDF format and saves it to the output folder."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = os.path.join(output_folder, f"SPECTER_intel_report_{timestamp}.pdf")
    
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
    
    html_content = markdown.markdown(markdown_content, extensions=['tables'])
    full_html = f"<html><head><style>{css}</style></head><body>{html_content}</body></html>"
    
    with open(output_filename, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(full_html, dest=pdf_file)
        
    if pisa_status.err:
        raise Exception("Failed to generate PDF report")
        
    return output_filename
