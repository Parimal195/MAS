import os
import json
from dotenv import load_dotenv

from streamintel_agent import StreamIntelAgent
from pdf_utils import markdown_to_pdf
from email_utils import send_report_email

def main():
    # Load environment variables (useful for local testing)
    load_dotenv()
    
    API_KEY = os.environ.get("GEMINI_API_KEY")
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
    
    if not API_KEY:
        print("[CRITICAL ERROR] GEMINI_API_KEY is missing. Aborting.")
        return
        
    print("[RUN_AGENT] Initializing Headless Automation Script...")
    
    # Load configs
    config_path = "config.json"
    keywords = []
    emails = []
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            try:
                cfg = json.load(f)
                keywords = cfg.get("keywords", [])
                emails = cfg.get("emails", [])
            except Exception as e:
                print(f"[WARNING] Failed to parse config.json: {e}")
    else:
        print("[WARNING] config.json not found, using default fallback vectors.")
        
    print(f"[RUN_AGENT] Loaded {len(keywords)} Target Vectors and {len(emails)} Target Emails.")
    
    # Run the agent
    agent = StreamIntelAgent(api_key=API_KEY, tavily_api_key=TAVILY_API_KEY)
    
    try:
        report_md = agent.generate_report(keywords, engine="tavily")
        print("[RUN_AGENT] Intelligence report successfully generated.")
        
        # Generate PDF
        pdf_path = markdown_to_pdf(report_md, is_manual=False)
        print(f"[RUN_AGENT] PDF generated successfully at: {pdf_path}")
        
        # Send Email
        if emails:
            success, msg = send_report_email(emails, pdf_path)
            if success:
                print(f"[RUN_AGENT] Success! Email dispatch complete: {msg}")
            else:
                print(f"[ERROR] Email dispatch failed: {msg}")
        else:
            print("[RUN_AGENT] No target emails configured. Skipping email dispatch.")
            
    except Exception as e:
        print(f"[CRITICAL ERROR] Pipeline failed: {e}")

if __name__ == "__main__":
    main()
