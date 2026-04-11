"""
=============================================================================
 ✉️ EMAIL DISPATCHER MODULE (email_utils.py)
 
 What this file does in plain English:
 This file acts as the "Post Office" for the application. Once the Artificial 
 Intelligence finishes writing the PDF report, this script grabs that PDF, 
 writes a friendly email, attaches the PDF, secretly signs into a real Gmail 
 account using your App Password, and sends it out to the team!
=============================================================================
"""

import smtplib # The standard Python tool for talking to Mail Servers
from email.mime.multipart import MIMEMultipart # Tool to construct a multi-part email (Text + Attachments)
from email.mime.base import MIMEBase # Tool to handle the raw file attachment
from email.mime.text import MIMEText # Tool to write the actual words in the email
from email import encoders # Tool to safely package the PDF into the email
import os # Tool to look at the computer's secret environment variables
from datetime import datetime # Tool to check the current date and time

# This is a list of fitness quotes. The system will automatically pick one based on the day of the year.
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
    """
    This is the main function that handles the delivery.
    It takes two things: a list of email addresses, and the location of the PDF on the hard drive.
    """
    
    # 1. Grab the "From" email and password from the secure hidden vault (.env or Streamlit Secrets)
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    
    # Cloud Fallback Check: Sometimes if the app is hosted online (Streamlit Cloud), it prefers to store secrets slightly differently.
    # We check there just in case they were missing from the normal vault.
    if not sender_email or not sender_password:
        try:
            import streamlit as st
            if "SENDER_EMAIL" in st.secrets:
                sender_email = st.secrets["SENDER_EMAIL"]
            if "SENDER_PASSWORD" in st.secrets:
                sender_password = st.secrets["SENDER_PASSWORD"]
        except Exception:
            pass # If it still crashes here, we just ignore it and let the hard crash below happen to alert the user.
            
    # 2. Safety Check: If we still don't have a password, we completely stop the script and throw a red error.
    if not sender_email or not sender_password:
        raise ValueError("Backend secrets (SENDER_EMAIL/SENDER_PASSWORD) are not configured for email sending.")
        
    # Safety Check: Needs to be a list, not a single lump of text.
    if not isinstance(receiver_emails, list):
        raise ValueError("receiver_emails must be a list of email strings")
        
    # Safety Check: If the list is entirely empty, we just skip the email process entirely.
    if not receiver_emails:
        return True, "No email addresses provided, skipping email."
        
    # 3. Start building the physical Email Package
    msg = MIMEMultipart()
    msg['From'] = sender_email
    
    # We join the list of emails into a single comma separated list: "email1, email2"
    msg['To'] = ", ".join(receiver_emails)
    
    # Check the real world date to print it on the subject line!
    today_date = datetime.now().strftime("%B %d, %Y")
    msg['Subject'] = f"Daily Market Research - {today_date}"
    
    # Math trick: Calculate what day of the year it is (1-365) to rotate to a new quote predictably!
    day_of_year = datetime.now().timetuple().tm_yday
    quote = FITNESS_MOTIVATION[day_of_year % len(FITNESS_MOTIVATION)]
    
    # 4. Write the literal words inside the email box
    body = f"""Hi Team,

{quote}

Sharing today's snapshot of market trends, key research, and what competitors in the streaming space are building.

Detailed report is attached—take a quick look to stay ahead.

Don't forget to drop a thank you to Parimal for this daily journal, stay updated and go win the market like a boss!

Cheers,
Parimal"""
    
    # Stuff the words into the email package
    msg.attach(MIMEText(body, 'plain'))
    
    # 5. Attach the actual PDF document
    if os.path.exists(pdf_path):
        filename = os.path.basename(pdf_path) # Extracts just the "report.pdf" name from the long folder path
        with open(pdf_path, "rb") as attachment:
            # We treat the PDF as a raw binary "octet-stream" to send it safely over the internet
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            
        # Encode it so email servers don't scramble the file
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={filename}')
        msg.attach(part) # Stuff the PDF into the email package alongside the words!
    else:
        # If the PDF doesn't exist, hard crash!
        raise FileNotFoundError(f"PDF attachment not found at {pdf_path}")
    
    # 6. Contact Gmail and push the "Send" button!
    try:
        # Port 587 is the standard safe highway connection to Gmail servers
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Ask Gmail to securely encrypt our connection
        server.login(sender_email, sender_password) # Show Gmail our secret ID card (App Password)
        text = msg.as_string() # Convert the whole package into a giant block of internet text
        server.sendmail(sender_email, receiver_emails, text) # BOOM! FIRE!
        server.quit() # Hang up the phone with Gmail
        return True, f"Successfully dispatched to {len(receiver_emails)} recipient(s)."
    except Exception as e:
        # If Gmail rejected our password or the internet died, we gracefully fail here
        return False, f"SMTP Connection Failed: {str(e)}"
