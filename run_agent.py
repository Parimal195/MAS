"""
=============================================================================
 🤖 BACKGROUND ROBOT SCRIPT (run_agent.py)
 
 What this file does in plain English:
 This is the "Headless" script. Headless means it runs invisibly on a server 
 without any user interface, buttons, or website attached. GitHub automatically 
 triggers this exact file to run every morning (like a scheduled alarm clock).
 
 It wakes up, checks the `config.json` notebook to see what topics you told it 
 to research, asks the AI to build the report, and then tells the Post Office 
 (email script) to mail it out to the team!
=============================================================================
"""

import os # Tool to read secure system variables
from dotenv import load_dotenv # Tool to load local secret files (.env)
from streamintel_agent import StreamIntelAgent # Import our actual AI Brain
from pdf_utils import markdown_to_pdf # Import our PDF Maker
from email_utils import send_report_email # Import our Post Office Emailer
import sys # Tool to violently crash/stop the python script if something breaks

# Load variables from the local .env file (if running locally on a computer)
load_dotenv()

def run_specter_task():
    """
    This is the main function that runs when GitHub wakes the script up.
    """
    # 1. Grab our API Keys (The credit cards needed to pay Google and Tavily for the search)
    # We strip() them to make sure no accidental spaces were included
    API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()
    
    # Safety Check: If someone forgot to add the keys to GitHub, we crash the robot.
    if not API_KEY or not TAVILY_API_KEY:
        print("[ERROR] API Keys missing. Set GEMINI_API_KEY and TAVILY_API_KEY in environment variables.")
        sys.exit(1) # Panic stop!

    print("=== SPECTER HEADLESS INITIALIZED ===")
    
    # 2. Check the "Notebook" (config.json).
    # This prevents keywords from being hardcoded forever. The UI can edit config.json, and this script reads it!
    keywords = ["Twitch engagement", "YouTube Live discovery", "Kick creator revenue", "TikTok Live vertical"] # Fallback topics
    target_emails = [] # Fallback empty email list
    
    try:
        # Try to open the notebook file
        if os.path.exists("config.json"):
            import json
            with open("config.json", "r") as f:
                config_data = json.load(f) # Read the entire book
                if "keywords" in config_data:
                    keywords = config_data["keywords"] # Overwrite fallback with the new saved topics!
                if "emails" in config_data:
                    target_emails = config_data["emails"] # Overwrite fallback with the team's email addresses!
    except Exception as e:
        print(f"[WARNING] Could not construct config object: {e}")
        
    print(f"[AUTORUN] Using TAVILY strictly for automated deep search on vectors: {keywords}...")
    if target_emails:
        print(f"[AUTORUN] Will distribute output to targets: {target_emails}")
    
    # 3. Execution Phase
    try:
        # Turn the Artificial Intelligence Brain ON
        agent = StreamIntelAgent(api_key=API_KEY, tavily_api_key=TAVILY_API_KEY)
        
        # Tell the Brain to scan the internet using the "Tavily" deep search engine!
        # This takes about 30 seconds to run.
        report_md = agent.generate_report(keywords, engine="tavily")
        
        # Take the text the AI just wrote, and run it through the PDF Maker
        pdf_path = markdown_to_pdf(report_md)
        print(f"\n[SUCCESS] Intelligence Brief generated and saved at: {pdf_path}")
        
        # 4. Email Dispatch Phase
        if target_emails: # Only attempt to send emails if the list isn't empty
            print(f"[AUTORUN] Attempting email distribution...")
            try:
                # Call the Post Office module!
                success, msg = send_report_email(target_emails, pdf_path)
                if success:
                    print(f"📧 EMAIL SUCCESS: {msg}")
                else:
                    print(f"📧 EMAIL ERROR: {msg}")
            except Exception as e:
                print(f"📧 EMAIL FATAL FAILURE: {e}")
                
        print("=== SPECTER EXECUTION COMPLETE ===")
        
    except Exception as e:
        # If the internet dies or Google's API goes down, we show the crash log.
        print(f"\n[ERROR] Specter execution failed during intelligence sweep: {e}")
        sys.exit(1) # Panic stop!

# This special "if __name__" line is just standard Python code that says:
# "Only run this function if a human or Github triggered this file directly!"
if __name__ == "__main__":
    run_specter_task()
