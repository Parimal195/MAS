import os
from dotenv import load_dotenv
from slack_agent import SlackReporterAgent

def main():
    # Load environment variables
    load_dotenv()

    # Retrieve configuration
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")

    if not all([webhook_url, gemini_api_key]):
        print("[CRITICAL ERROR] Missing required environment variables: SLACK_WEBHOOK_URL or GEMINI_API_KEY.")
        print("Aborting Slack Reporter execution.")
        return

    print("[RUN_SLACK_AGENT] Initializing Slack Reporter Agent...")

    agent = SlackReporterAgent(
        webhook_url=webhook_url,
        gemini_api_key=gemini_api_key
    )

    try:
        agent.run()
    except Exception as e:
        print(f"[CRITICAL ERROR] Slack agent failed during execution: {e}")

if __name__ == "__main__":
    main()
