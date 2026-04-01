import os
from dotenv import load_dotenv
from agent import Agent
from pydantic import BaseModel
from typing import List

# Load environment variables
load_dotenv()

class ResearchPoints(BaseModel):
    topic: str
    key_points: List[str]
    summary: str

def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY not found in environment variables.")
        print("Please copy .env.example to .env and add your API key.")
        return

    # Define the agents
    researcher = Agent(
        name="Researcher",
        instructions="You are an expert researcher. Your goal is to gather the most important and accurate information about a topic and return it as a structured list of key points."
    )

    writer = Agent(
        name="Writer",
        instructions="You are a professional technical writer and copywriter. You take research notes and transform them into a well-structured, engaging, and easy-to-read article. Format the output in Markdown."
    )

    topic = "The potential impact of quantum computing on modern cryptography"
    print(f"--- Starting MAS task on topic: '{topic}' ---\n")

    # Step 1: Researcher works on the topic
    print("-> Researcher is gathering information...")
    research_result = researcher.generate(
        prompt=f"Please research this topic: {topic}",
        schema=ResearchPoints
    )
    
    print("\n[Researcher Output]")
    print(f"Summary: {research_result.summary}")
    for i, pt in enumerate(research_result.key_points):
        print(f"  {i+1}. {pt}")
    print("\n" + "="*50 + "\n")

    # Step 2: Writer takes the research and drafts the article
    print("-> Writer is drafting the article based on research...")
    prompt_for_writer = f"""
    Please write a comprehensive article based on the following research:
    
    Topic: {research_result.topic}
    Summary: {research_result.summary}
    Key Points:
    {chr(10).join(['- ' + pt for pt in research_result.key_points])}
    
    Make it engaging and use clear headings.
    """
    
    article = writer.generate(prompt=prompt_for_writer)
    
    print("\n[Writer Output: Final Article]")
    print(article)
    print("\n--- MAS task complete ---")

if __name__ == "__main__":
    main()
