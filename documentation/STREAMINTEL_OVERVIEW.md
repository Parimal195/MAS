# STREAMINTEL (Project Specter)
## Product & Architecture Overview

Welcome to the non-technical master document for **STREAMINTEL**! This guide is written in plain English to help anyone—regardless of coding experience—understand exactly what this software does, how it is built, and how all the different pieces talk to each other.

---

## 1. Product Requirements Document (PRD)

### Executive Summary
Streamintel is an autonomous "ghost agent" that behaves like a digital researcher. Every day, it wakes up, searches the internet for new trends, features, and rumors regarding live streaming platforms (like Twitch, YouTube, and Kick), compiles a beautiful PDF intelligence report, and emails it directly to the team. 

It provides an interactive website (the Dashboard) where a team manager can remotely steer the agent's focus and manually trigger research scans at any time.

### Core Goals
- **Save Time:** Completely replace the need for human analysts to endlessly scroll social media to find streaming industry updates.
- **Deep Research:** Utilize "Retrieval-Augmented" AI to go beyond surface-level answers and stitch together weak signals into a coherent strategy report.
- **Set & Forget Operations:** The system must run flawlessly in the background, forever, for free, without needing a developer to constantly manage a server.
- **Distribution:** Automatically put the final PDF report directly into the hands of stakeholders via email.

### The Two Ways to Use Streamintel
1. **The Remote Dashboard (Streamlit Cloud):** A website where you can type in new search targets (e.g., "Find out what Kick is doing with monetization"), and hit a giant "Execute" button to force a scan right now. You can also type in comma-separated emails to instantly send the results to colleagues.
2. **The Automated Robot (GitHub Actions):** A silent background process running on GitHub servers. Every day (e.g., at 8:00 AM), it wakes up, reads the instructions you saved from the Dashboard, does the research, and automatically emails the daily summary to the team's mailing list.

---

## 2. Entity Relationship & Architecture Diagram (ERD)

This diagram tracks the flow of data through our entire ecosystem. It shows how the User (you) interacts with the website, and how the website relays instructions to the invisible background robot.

```mermaid
flowchart TD
    %% User Inputs
    User([🕵️ The User])
    
    %% The Interface
    subgraph UI [The Dashboard Website app.py]
        ManualSweep[Manual Sweep Button]
        ConfigTab[Online Configuration Tab]
    end
    
    %% The Brain
    subgraph Core [The Specter Agent streamintel_agent.py]
        Agent[StreamIntel Agent Model]
        Tavily[Tavily Deep Search]
        Gemini[Google Gemini AI]
    end
    
    %% The Utilities
    Emailer[SMTP Mailer email_utils.py]
    PDFMaker[PDF Generator pdf_utils.py]
    
    %% The Permanent Storage
    subgraph Storage [The Remote Server]
        GitHubRepo[(GitHub Repository)]
        ConfigJSON[config.json]
    end
    
    %% The Background Robot
    GitHubAction[[Daily Robot run_agent.py]]

    %% Workflow Connections
    User -->|Visits Website| UI
    
    ConfigTab -->|Saves Search Targets\n& Daily Emails| GitHubRepo
    GitHubRepo -.-> ConfigJSON
    
    GitHubAction -.->|Wakes up daily\nReads instructions| ConfigJSON
    GitHubAction -->|Hands instructions to Brain| Core
    
    ManualSweep -->|Clicks Execute| Core
    
    %% Agent Logic
    Agent -->|1. Searches the Internet| Tavily
    Tavily -->|Raw Data| Agent
    Agent -->|2. Asks AI to organize data| Gemini
    Gemini -->|Returns Markdown Report| Agent
    
    %% Post Processing
    Agent -->|Sends Text to be Styled| PDFMaker
    PDFMaker -->|Creates PDF| Agent
    
    %% Distribution
    Agent -->|Hands PDF off| Emailer
    Emailer -->|Delivers to Inboxes| User
```

---

## 3. How the "Specter" Agent Actually Works

The brain of this application lives in `streamintel_agent.py`. It uses a methodology known in the AI world as **Retrieval-Augmented Generation (RAG) with Direct Prompting**.

**Here is the plain-English translation of that process:**

1. **The Wake Up:** The agent starts by receiving a list of "Target Vectors" (your keywords).
2. **The Hunt (Retrieval):** The agent does *not* immediately ask the AI to answer the underlying question. Instead, it uses **Tavily** (a specialized search engine built for AI). It says to Tavily, "Scrape the internet for the last 7 days regarding these keywords and give me the raw, messy text."
3. **The Assembly (Augmented):** The agent takes all this messy, raw internet data and wraps it into a giant box. 
4. **The Brain (Generation):** Finally, the agent calls **Google Gemini** (the actual Artificial Intelligence). It gives Gemini the giant box of raw data and says: 
   > *"You are Specter, a covert intelligence operative. Do not make anything up. Read all the messy text in this box, stitch it together into a clean, strategic breakdown focused on engagement and monetization, stamp it with today's date, and format it perfectly."*
5. **The Output:** Gemini returns a beautifully written, perfectly categorized Markdown (text) report.

By forcing the AI to only look at the box of fresh internet data we just gathered, we prevent the AI from "hallucinating" or making things up, and guarantee it only analyzes the absolute newest information on the internet!
