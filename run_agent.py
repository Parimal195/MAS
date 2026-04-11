import os
from dotenv import load_dotenv
from streamintel_agent import StreamIntelAgent
from pdf_utils import markdown_to_pdf
from email_utils import send_report_email
import sys

# Load variables
load_dotenv()

def run_specter_task():
    # Retrieve keys securely from environment
    API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()
    
    if not API_KEY or not TAVILY_API_KEY:
        print("[ERROR] API Keys missing. Set GEMINI_API_KEY and TAVILY_API_KEY in environment variables.")
        sys.exit(1)

    print("=== SPECTER HEADLESS INITIALIZED ===")
    
    # Load dynamic configuration from the repository mapping file
    # This prevents keywords from being hardcoded inside the execution script itself
    keywords = ["Twitch engagement", "YouTube Live discovery", "Kick creator revenue", "TikTok Live vertical"]
    target_emails = []
    try:
        if os.path.exists("config.json"):
            import json
            with open("config.json", "r") as f:
                config_data = json.load(f)
                if "keywords" in config_data:
                    keywords = config_data["keywords"]
                if "emails" in config_data:
                    target_emails = config_data["emails"]
    except Exception as e:
        print(f"[WARNING] Could not construct config object: {e}")
        
    print(f"[AUTORUN] Using TAVILY strictly for automated deep search on vectors: {keywords}...")
    if target_emails:
        print(f"[AUTORUN] Will distribute output to targets: {target_emails}")
    
    try:
        agent = StreamIntelAgent(api_key=API_KEY, tavily_api_key=TAVILY_API_KEY)
        report_md = agent.generate_report(keywords, engine="tavily")
        
        pdf_path = markdown_to_pdf(report_md)
        print(f"\n[SUCCESS] Intelligence Brief generated and saved at: {pdf_path}")
        
        if target_emails:
            print(f"[AUTORUN] Attempting email distribution...")
            try:
                success, msg = send_report_email(target_emails, pdf_path)
                if success:
                    print(f"📧 EMAIL SUCCESS: {msg}")
                else:
                    print(f"📧 EMAIL ERROR: {msg}")
            except Exception as e:
                print(f"📧 EMAIL FATAL FAILURE: {e}")
                
        print("=== SPECTER EXECUTION COMPLETE ===")
        
    except Exception as e:
        print(f"\n[ERROR] Specter execution failed during intelligence sweep: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_specter_task()
