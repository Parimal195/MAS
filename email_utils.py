import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os

def send_report_email(receiver_emails, pdf_path):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    
    if not sender_email or not sender_password:
        raise ValueError("Backend secrets (SENDER_EMAIL/SENDER_PASSWORD) are not configured for email sending.")
        
    if not isinstance(receiver_emails, list):
        raise ValueError("receiver_emails must be a list of email strings")
        
    if not receiver_emails:
        return True, "No email addresses provided, skipping email."
        
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ", ".join(receiver_emails)
    msg['Subject'] = "STREAMINTEL: Intelligence Scan Complete"
    
    body = "Hello,\n\nThe manual intelligence sweep you requested has concluded. Please find the compiled Confidential Intelligence Brief attached as a PDF.\n\nRegards,\nSpecter Intelligence Engine"
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach PDF if it exists
    if os.path.exists(pdf_path):
        filename = os.path.basename(pdf_path)
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={filename}')
        msg.attach(part)
    else:
        raise FileNotFoundError(f"PDF attachment not found at {pdf_path}")
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_emails, text)
        server.quit()
        return True, f"Successfully dispatched to {len(receiver_emails)} recipient(s)."
    except Exception as e:
        return False, f"SMTP Connection Failed: {str(e)}"
