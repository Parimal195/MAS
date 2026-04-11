import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os
from datetime import datetime

FITNESS_MOTIVATION = [
    "A 30-minute workout is just 2% of your day. No excuses.",
    "Your health is your true wealth; invest in your physical fitness today.",
    "Push yourself, because no one else is going to do it for you.",
    "Success starts with self-discipline. Make time to sweat today.",
    "Take care of your body. It's the only place you have to live.",
    "Energy and persistence conquer all things. Keep moving!",
    "You don't have to be extreme, just consistent. Drink water and stretch!",
    "Exercise not only changes your body, it changes your mind, attitude, and mood.",
    "The harder the workout, the better the end result. Stay resilient.",
    "Don't stop when you're tired. Stop when you're done."
]

def send_report_email(receiver_emails, pdf_path):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    
    # Cloud Fallback Check
    if not sender_email or not sender_password:
        try:
            import streamlit as st
            sender_email = st.secrets.get("SENDER_EMAIL")
            sender_password = st.secrets.get("SENDER_PASSWORD")
        except ImportError:
            pass
            
    if not sender_email or not sender_password:
        raise ValueError("Backend secrets (SENDER_EMAIL/SENDER_PASSWORD) are not configured for email sending.")
        
    if not isinstance(receiver_emails, list):
        raise ValueError("receiver_emails must be a list of email strings")
        
    if not receiver_emails:
        return True, "No email addresses provided, skipping email."
        
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ", ".join(receiver_emails)
    
    today_date = datetime.now().strftime("%B %d, %Y")
    msg['Subject'] = f"Daily Market Research - {today_date}"
    
    # Rotate securely based on the day of the year
    day_of_year = datetime.now().timetuple().tm_yday
    quote = FITNESS_MOTIVATION[day_of_year % len(FITNESS_MOTIVATION)]
    
    body = f"""Hi Team,

{quote}

Sharing today's snapshot of market trends, key research, and what competitors in the streaming space are building.

Detailed report is attached—take a quick look to stay ahead.

Don't forget to drop a thank you to Parimal for this daily journal, stay updated and go win the market like a boss!

Cheers,
Parimal"""
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
