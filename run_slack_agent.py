import os
from dotenv import load_dotenv
from slack_agent import SlackReporterAgent

def main():
    # Load environment variables
    load_dotenv()
    
    # Retrieve configuration
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    channel_id = os.environ.get("SLACK_CHANNEL_ID")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    
    if not all([slack_token, channel_id, gemini_api_key]):
        print("[CRITICAL ERROR] Missing required environment variables: SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, or GEMINI_API_KEY.")
        print("Aborting Slack Reporter execution.")
        return
        
    print("[RUN_SLACK_AGENT] Initializing Slack Reporter Agent...")
    
    agent = SlackReporterAgent(
        slack_token=slack_token,
        channel_id=channel_id,
        gemini_api_key=gemini_api_key
    )
    
    try:
        agent.run()
    except Exception as e:
        print(f"[CRITICAL ERROR] Slack agent failed during execution: {e}")

if __name__ == "__main__":
    main()
