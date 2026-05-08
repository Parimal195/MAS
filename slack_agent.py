import os
import re
import json
import time
import requests
from datetime import datetime
from google import genai


class SlackReporterAgent:
    GITHUB_REPORT_BASE_URL = "https://github.com/Parimal195/MAS/blob/main/reports"

    def __init__(self, webhook_url, gemini_api_key):
        self.webhook_url = webhook_url
        self.genai_client = genai.Client(api_key=gemini_api_key)

        self.reports_dir = "reports"
        self.state_file = os.path.join(self.reports_dir, "slack_state.json")

    # ------------------------------------------------------------------ state
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

    # --------------------------------------------------------- report helpers
    def _get_today_report_filename(self):
        """Construct the report filename for today in dd-mm-yy format."""
        return datetime.now().strftime("report-%d-%m-%y.pdf")

    def _report_exists(self, filename):
        """Check if the report file exists locally."""
        path = os.path.join(self.reports_dir, filename)
        return os.path.isfile(path)

    def _get_github_url(self, filename):
        """Build the GitHub URL for a given report filename."""
        return f"{self.GITHUB_REPORT_BASE_URL}/{filename}"

    # -------------------------------------------------------- Gemini summary
    def _summarize_pdf(self, pdf_path):
        print(f"[SlackReporter] Extracting summary from {pdf_path}...")
        try:
            import pypdf
            reader = pypdf.PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"

            # Look for the Trend summary or general summary section
            # The prompt asks for: "Trend summary (macro shifts)"
            import re
            
            # Attempt to find the Trend Summary or Summary heading and capture the following text
            # until the next major heading (which typically starts with a capital letter and has a colon or is a number)
            # We use a non-greedy match until the end of the string or another possible heading
            match = re.search(r'(?i)(?:Trend Summary|Macro Shifts).*?\n(.*?)(?=\n[A-Z0-9].*?:|\n#|\Z)', text, re.DOTALL)
            
            if match and match.group(1).strip():
                summary_text = match.group(1).strip()
                # Clean up lines
                lines = [line.strip() for line in summary_text.split('\n') if line.strip()]
                extracted_summary = " ".join(lines)
                if len(extracted_summary) > 500:
                    extracted_summary = extracted_summary[:497] + "..."
                return extracted_summary
                
            # If no specific Trend Summary is found, just grab the first few meaningful lines after the title
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            # Skip the first line assuming it's the title/date
            if len(lines) > 1:
                extracted_summary = " ".join(lines[1:6])
            else:
                extracted_summary = " ".join(lines)
                
            if len(extracted_summary) > 500:
                extracted_summary = extracted_summary[:497] + "..."
            return extracted_summary
            
        except Exception as e:
            print(f"[SlackReporter] Error reading PDF: {e}")
            return "Summary unavailable due to an error reading the PDF."

    # ---------------------------------------------------- Slack webhook send
    def _send_to_slack(self, filename, github_url, summary):
        """Send a rich message to Slack via Incoming Webhook."""
        print(f"[SlackReporter] Sending {filename} to Slack via webhook...")
        try:
            title = filename.replace(".pdf", "").replace("-", " ").title()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            payload = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"📄 {title}",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Generated at:* {timestamp}"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Summary:*\n{summary}"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"📎 *<{github_url}|View Full Report on GitHub>*"
                        }
                    }
                ]
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 200 and response.text == "ok":
                return True
            else:
                print(f"[SlackReporter] Webhook returned: {response.status_code} – {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"[SlackReporter] Network error sending to Slack: {e}")
            return False
        except Exception as e:
            print(f"[SlackReporter] Unexpected error sending to Slack: {e}")
            return False

    # ------------------------------------------------------------------- run
    def run(self):
        print("[SlackReporter] Starting agent run...")

        filename = self._get_today_report_filename()
        print(f"[SlackReporter] Looking for today's report: {filename}")

        if not self._report_exists(filename):
            print(f"[SlackReporter] Today's report ({filename}) does not exist yet. Nothing to send.")
            return

        # Check if already sent
        state = self._load_state()
        sent_reports = set(state.get("sent_reports", []))

        if filename in sent_reports:
            print(f"[SlackReporter] Today's report ({filename}) was already sent. Skipping.")
            return

        # Summarize and send
        pdf_path = os.path.join(self.reports_dir, filename)
        summary = self._summarize_pdf(pdf_path)
        github_url = self._get_github_url(filename)

        success = self._send_to_slack(filename, github_url, summary)

        if success:
            print(f"[SlackReporter] Successfully sent {filename}")
            sent_reports.add(filename)
            state["sent_reports"] = list(sent_reports)
            self._save_state(state)
        else:
            print(f"[SlackReporter] Failed to send {filename}. Will retry next time.")

        print("[SlackReporter] Run completed.")
