import os
import re
import json
import time
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from google import genai
from google.genai import types

class SlackReporterAgent:
    def __init__(self, slack_token, channel_id, gemini_api_key):
        self.slack_client = WebClient(token=slack_token)
        self.channel_id = channel_id
        self.genai_client = genai.Client(api_key=gemini_api_key)
        
        self.reports_dir = "reports"
        self.state_file = os.path.join(self.reports_dir, "slack_state.json")
        self.report_pattern = re.compile(r"^report-\d{2}-\d{2}-\d{2}\.pdf$")
        
    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[SlackReporter] Error loading state: {e}")
        return {"sent_reports": []}
        
    def _save_state(self, state):
        os.makedirs(self.reports_dir, exist_ok=True)
        try:
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"[SlackReporter] Error saving state: {e}")

    def _get_unsent_reports(self):
        if not os.path.exists(self.reports_dir):
            print(f"[SlackReporter] Reports directory {self.reports_dir} does not exist.")
            return []
            
        state = self._load_state()
        sent_reports = set(state.get("sent_reports", []))
        
        unsent = []
        for filename in os.listdir(self.reports_dir):
            if self.report_pattern.match(filename) and filename not in sent_reports:
                unsent.append(os.path.join(self.reports_dir, filename))
                
        # Sort by creation time so we process oldest unsent first
        unsent.sort(key=lambda x: os.path.getctime(x))
        return unsent

    def _summarize_pdf(self, pdf_path):
        print(f"[SlackReporter] Summarizing {pdf_path} using Gemini API...")
        try:
            # Upload the file to Gemini
            uploaded_file = self.genai_client.files.upload(file=pdf_path)
            
            # Wait for file to be processed
            retries = 10
            while retries > 0:
                file_info = self.genai_client.files.get(name=uploaded_file.name)
                if file_info.state.name == "ACTIVE":
                    break
                elif file_info.state.name == "FAILED":
                    print(f"[SlackReporter] Failed to process document: {pdf_path}")
                    return "Summary unavailable (document processing failed)."
                print(".", end="", flush=True)
                time.sleep(2)
                retries -= 1
                
            prompt = "Please provide a concise 3-5 line summary of this intelligence report. Focus on the main findings."
            
            response = self.genai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[uploaded_file, prompt]
            )
            
            # Clean up the file
            self.genai_client.files.delete(name=uploaded_file.name)
            
            return response.text.strip()
        except Exception as e:
            print(f"[SlackReporter] Error summarizing PDF: {e}")
            return "Summary unavailable due to an error during analysis."

    def _send_to_slack(self, pdf_path, filename, summary):
        print(f"[SlackReporter] Sending {filename} to Slack...")
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = filename.replace(".pdf", "").replace("-", " ").title()
            
            # Modern Slack SDK uses WebClient.files_upload_v2 for file uploads
            message = f"*{title}*\n*Generated at:* {timestamp}\n\n*Summary:*\n{summary}"
            
            response = self.slack_client.files_upload_v2(
                channel=self.channel_id,
                file=pdf_path,
                title=title,
                initial_comment=message
            )
            return True
        except SlackApiError as e:
            print(f"[SlackReporter] Slack API Error: {e.response['error']}")
            return False
        except Exception as e:
            print(f"[SlackReporter] Unexpected error sending to Slack: {e}")
            return False

    def run(self):
        print("[SlackReporter] Starting agent run...")
        unsent_reports = self._get_unsent_reports()
        
        if not unsent_reports:
            print("[SlackReporter] No new reports to send.")
            return
            
        print(f"[SlackReporter] Found {len(unsent_reports)} new report(s).")
        
        state = self._load_state()
        sent_reports = set(state.get("sent_reports", []))
        
        for pdf_path in unsent_reports:
            filename = os.path.basename(pdf_path)
            summary = self._summarize_pdf(pdf_path)
            
            success = self._send_to_slack(pdf_path, filename, summary)
            
            if success:
                print(f"[SlackReporter] Successfully sent {filename}")
                sent_reports.add(filename)
                state["sent_reports"] = list(sent_reports)
                self._save_state(state)
            else:
                print(f"[SlackReporter] Failed to send {filename}. Will retry next time.")
                
        print("[SlackReporter] Run completed.")
