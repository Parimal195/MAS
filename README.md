<![CDATA[# 👁️ MAS — Multi-Agent System for Streaming Intelligence & PRD Generation

> **MAS** (Multi-Agent System) is an autonomous AI-powered toolkit designed for a Senior Product Manager working in the live-streaming industry. It combines two major capabilities into a single deployable platform:
>
> 1. **StreamIntel (Specter)** — A daily intelligence agent that scans the web, generates PDF market research briefs, emails them to your team, and posts summaries to Slack.
> 2. **PRD Maker** — A 7-agent AI product team that collaboratively researches, writes, reviews, and refines professional Product Requirements Documents.

---

## 📑 Table of Contents

- [System Overview](#-system-overview)
- [Architecture](#-architecture)
- [File-by-File Breakdown](#-file-by-file-breakdown)
  - [Core Application](#1-apppy--streamlit-dashboard)
  - [Intelligence Engine](#2-streamintel_agentpy--ai-research-agent)
  - [PRD Engine](#3-prd_enginepy--multi-agent-prd-system)
  - [Utilities](#4-pdf_utilspy--pdf-compiler)
  - [Email Module](#5-email_utilspy--email-dispatcher)
  - [Logging](#6-logger_configpy--logging-configuration)
  - [CLI Runners](#7-run_agentpy--headless-specter-runner)
  - [Slack Integration](#9-slack_agentpy--slack-reporter)
- [GitHub Actions Workflows](#-github-actions-workflows)
- [Configuration Files](#-configuration-files)
- [Environment Variables](#-environment-variables)
- [Setup & Installation](#-setup--installation)
- [Tech Stack](#-tech-stack)

---

## 🧠 System Overview

### Problem Statement

Product Managers in the streaming industry need to:
1. **Stay informed daily** about competitive moves, feature launches, and market trends across Twitch, YouTube Live, Kick, Facebook Gaming, and emerging platforms.
2. **Create professional PRDs quickly** with research-backed, engineering-ready sections — a process that typically takes days of manual work.

### Solution

MAS automates both problems through specialized AI agents:

| Capability | What It Does | Delivery |
|---|---|---|
| **StreamIntel (Specter)** | Scans the web daily via Tavily/DuckDuckGo → synthesizes via Gemini → generates a styled PDF → emails to team → posts summary to Slack | Automated via GitHub Actions |
| **PRD Maker** | 7 AI agents collaborate to research, write, evaluate, and review a full PRD from a single sentence input | Interactive via Streamlit UI |

### Key Features

- 🔄 **Fully Automated Daily Reports** — GitHub Actions runs the scan every day at a configurable time
- 📊 **Dual Search Engines** — Tavily (AI-optimized deep search) + DuckDuckGo (fast/free fallback)
- 🤖 **7-Agent PRD System** — Classifier → Research → Generator → Evaluator → Gap Detector → Engineering Manager → VP Product
- 💬 **Slack Integration** — AI-summarized reports posted to your team's Slack channel
- 📧 **Email Distribution** — PDF briefs automatically emailed to configurable recipients
- 🔁 **Iterative Refinement** — PRDs support "Head of Product mode" — refine, add requirements, regenerate sections
- ☁️ **Cloud Persistence** — Config and schedules pushed directly to GitHub from the dashboard
- 🛡️ **Multi-Model Fallback** — Gemini → Claude → Groq → OpenAI (automatic quota-aware switching)
- 📄 **Multi-Format Export** — DOCX, PDF, and Markdown output for PRDs

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        STREAMLIT DASHBOARD (app.py)                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  Tab 1: Config   │  │  Tab 2: Manual   │  │  Tab 3: PRD Maker   │  │
│  │  (GitHub Push)   │  │  Sweep (Specter) │  │  (7-Agent System)   │  │
│  └────────┬─────────┘  └────────┬─────────┘  └─────────┬───────────┘  │
└───────────┼──────────────────────┼──────────────────────┼──────────────┘
            │                      │                      │
   ┌────────▼────────┐   ┌────────▼────────┐    ┌────────▼────────────┐
   │   GitHub API    │   │ StreamIntel     │    │   PRD Engine        │
   │   (PyGithub)    │   │ Agent           │    │   (prd_engine.py)   │
   │                 │   │ (streamintel_   │    │                     │
   │ • Push config   │   │  agent.py)      │    │  ┌───────────────┐  │
   │ • Push reports  │   │                 │    │  │ God Agent     │  │
   │ • Push errors   │   │ • Tavily Search │    │  │ Classifier    │  │
   │ • Update cron   │   │ • DDG Search    │    │  │ Research      │  │
   └─────────────────┘   │ • Gemini LLM    │    │  │ Generator     │  │
                         └────────┬────────┘    │  │ Evaluator     │  │
                                  │             │  │ Gap Detector  │  │
                    ┌─────────────┼──────┐      │  │ Eng Manager   │  │
                    │             │      │      │  │ VP Product    │  │
              ┌─────▼───┐  ┌─────▼──┐   │      │  └───────────────┘  │
              │pdf_utils │  │email_  │   │      └─────────────────────┘
              │  .py     │  │utils.py│   │
              │          │  │        │   │
              │ MD → PDF │  │ SMTP   │   │
              └──────────┘  └────────┘   │
                                         │
          ┌──────────────────────────────┘
          │
  ┌───────▼──────────────────────────────────────────────┐
  │              GITHUB ACTIONS (Automated)               │
  │  ┌─────────────────────┐  ┌─────────────────────┐    │
  │  │ specter_daily.yml   │  │  slack_daily.yml     │    │
  │  │ run_agent.py        │  │  run_slack_agent.py  │    │
  │  │ (Scan→PDF→Email→    │  │  (Summarize→Slack)   │    │
  │  │  Commit to repo)    │  │                      │    │
  │  └─────────────────────┘  └──────────────────────┘    │
  └───────────────────────────────────────────────────────┘
```

---

## 📂 File-by-File Breakdown

### 1. `app.py` — Streamlit Dashboard
> **Lines:** 825 | **Role:** Main entry point — the web-based UI

This is the **control center** of the entire system, built with [Streamlit](https://streamlit.io/). It provides three tabs:

| Tab | Purpose |
|-----|---------|
| **🎛️ Online Configuration** | Configure target search keywords, email recipients, and schedule time. Changes are pushed directly to the GitHub repository via the GitHub API so the automated Actions workflow picks them up. |
| **⚡ Manual Sweep** | Run an on-demand Specter intelligence scan. Choose between Tavily or DuckDuckGo as the search engine. Optionally email the resulting PDF to ad-hoc recipients. Reports are auto-committed to GitHub. |
| **📋 PRD Maker** | Enter a product idea → the 7-agent system researches, generates, evaluates, and reviews a full PRD. Supports iterative refinement ("Head of Product" mode), section-level regeneration, and multi-format download (DOCX/PDF/Markdown). |

**Key Functions:**
- `update_github_online()` — Pushes config + schedule changes to GitHub
- `push_codebase_to_github()` — Full codebase sync to GitHub
- `push_report_to_github()` — Uploads generated PDF reports
- `get_utc_cron_string()` — Converts local time → UTC cron format

---

### 2. `streamintel_agent.py` — AI Research Agent
> **Lines:** 209 | **Role:** The "Specter" intelligence agent — web scanning + report synthesis

This file contains the `StreamIntelAgent` class — the core AI researcher. It operates in three steps:

1. **Search Phase** — For each keyword/topic, queries Tavily (deep AI search) or DuckDuckGo (free fallback) for recent results
2. **Synthesis Phase** — Sends all raw search results to Google Gemini with a detailed persona prompt ("You are Specter, a covert intelligence entity...")
3. **Output** — Returns a structured markdown intelligence report

**Key Features:**
- Dual search engine support (Tavily + DuckDuckGo)
- Automatic model fallback chain: `gemini-2.5-flash` → `gemini-2.5-pro` → `gemini-flash-latest` → `gemini-pro-latest`
- Up to 10 retries with 20-second delays per model
- Elaborate "Specter" persona prompt that produces structured, insight-first reports organized by platform (Twitch, YouTube, Kick, etc.)

---

### 3. `prd_engine.py` — Multi-Agent PRD System
> **Lines:** 2293 | **Role:** The entire 7-agent AI product team

This is the **largest and most complex file** in the project. It implements a complete multi-agent system where 7 specialized AI agents collaborate to produce professional PRDs.

#### The 7 Agents

| # | Agent | Class | Role |
|---|-------|-------|------|
| 0 | **God Agent** | `GodAgent` | Master orchestrator — analyzes user input, decides which agents to activate, determines which PRD sections are needed based on product type (streaming, e-commerce, fintech, etc.) |
| 1 | **Classifier Agent** | `ClassifierAgent` | Determines if user input is an idea, problem statement, or PRD update request |
| 2 | **Research Agent** | `ResearchAgent` | Conducts web research via Tavily + Google Custom Search. Also pulls existing Specter intelligence reports from GitHub for context. Caches results to avoid redundant API calls. |
| 3 | **PRD Generator** | `PRDGeneratorAgent` | The workhorse writer. Generates comprehensive PRD sections with detailed section-specific writing guides (Problem Statement, Objectives, Technical Architecture, etc.). Supports 15+ core sections and dynamic product-specific sections. |
| 4 | **Evaluator Agent** | `EvaluatorAgent` | Scores and selects the best draft using weighted scoring: Clarity (15%) + Depth (20%) + Actionability (25%) + User Focus (15%) + Research Alignment (15%) + Strategic Thinking (10%) |
| 5 | **Gap Detector** | `GapDetectorAgent` | Scans the assembled PRD for missing sections, weak logic, undefined flows, missing edge cases, and missing metrics |
| 6 | **Engineering Manager** | `EngineeringManagerAgent` | Reviews PRD for technical completeness — system design, API specs, edge cases, scalability risks, UI/UX feasibility. Rejects if critical gaps exist. |
| 7 | **VP Product** | `VPProductAgent` | Final executive gate — evaluates business strategy, go-to-market risks, competitive gaps, monetization logic. Nothing ships without VP approval. |

#### Supporting Infrastructure

| Component | Purpose |
|-----------|---------|
| `BaseAgent` | Shared LLM calling infrastructure with automatic provider switching (Gemini → Claude → Groq) based on quota availability |
| `PRDOrchestrator` | Central coordinator — manages the full generation flow, iterative refinement, document generation (DOCX/PDF/MD), and GitHub push |
| `GitHubErrorLogger` | Pushes structured error logs to `error_logs/` folder in the GitHub repo for remote debugging |
| `PRDMemory` | State persistence across iterations — caches research, tracks PRD versions, stores section history |
| Data Classes | `PRDSection`, `PRDContext`, `PRDMemory`, `GapReport`, `EngineeringReview` |

#### Generation Flow

```
User Input
    │
    ▼
God Agent (plan workflow, select sections)
    │
    ▼
Classifier Agent (idea / problem / update)
    │
    ▼
Research Agent (Tavily + Google + Specter reports)
    │
    ▼
PRD Generator (generate each section)
    │
    ▼
[Sections assembled into PRD]
    │
    ▼
Generate DOCX/PDF/MD → Push to GitHub
```

---

### 4. `pdf_utils.py` — PDF Compiler
> **Lines:** 78 | **Role:** Converts markdown → styled PDF

Takes raw markdown output from the Specter agent and converts it into a professionally styled PDF using `xhtml2pdf`. Handles:
- A4 portrait format with 2cm margins
- Styled typography (Helvetica, color-coded headings)
- Separate naming for manual scans (`instant-report-DD-MM-YY-HHMMSS.pdf`) vs automated daily reports (`report-DD-MM-YY.pdf`)
- Auto-creates the `reports/` folder

---

### 5. `email_utils.py` — Email Dispatcher
> **Lines:** 130 | **Role:** Sends PDF reports via Gmail SMTP

The "post office" of the system. After a report is generated:
1. Retrieves sender credentials from environment variables (or Streamlit Secrets as fallback)
2. Constructs a multi-part email with a friendly body + rotating daily fitness quote
3. Attaches the PDF report
4. Sends via Gmail SMTP (port 587 with TLS)

---

### 6. `logger_config.py` — Logging Configuration
> **Lines:** 73 | **Role:** Structured logging for the PRD engine

Sets up dual-output logging:
- **Console:** INFO level to stdout
- **File:** DEBUG level to `logs/prd_engine.log`

Provides helper functions for standardized log entries:
- `log_api_check()` — API availability status
- `log_agent_start()` / `log_agent_end()` — Agent lifecycle tracking
- `log_error()` — Error with context
- `log_api_call()` — API call details
- `log_section_generated()` — PRD section generation stats

---

### 7. `run_agent.py` — Headless Specter Runner
> **Lines:** 65 | **Role:** CLI script for automated GitHub Actions execution

This is the **headless (no UI) entry point** triggered by the `specter_daily.yml` GitHub Actions workflow. It:
1. Loads `config.json` for keywords and email targets
2. Initializes `StreamIntelAgent` with API keys
3. Runs the intelligence scan (always uses Tavily)
4. Generates a PDF via `pdf_utils`
5. Emails the PDF to configured recipients via `email_utils`

The GitHub Actions workflow then commits the PDF to the `reports/` folder.

---

### 8. `run_slack_agent.py` — Headless Slack Runner
> **Lines:** 32 | **Role:** CLI script for Slack delivery via GitHub Actions

The **headless entry point** triggered by the `slack_daily.yml` workflow. It:
1. Loads environment variables (`SLACK_WEBHOOK_URL`, `GEMINI_API_KEY`)
2. Initializes `SlackReporterAgent`
3. Calls `agent.run()`

---

### 9. `slack_agent.py` — Slack Reporter
> **Lines:** 190 | **Role:** Summarizes PDF reports and posts to Slack

The `SlackReporterAgent` class handles the Slack delivery pipeline:

1. **Check** — Looks for today's report file (`report-DD-MM-YY.pdf`) in `reports/`
2. **Deduplicate** — Checks `reports/slack_state.json` to avoid sending the same report twice
3. **Summarize** — Uploads the PDF to Gemini's Files API, waits for processing, then asks Gemini to generate a 3-5 line summary
4. **Post** — Sends a rich Block Kit message to Slack via Incoming Webhook with the summary + link to the full report on GitHub
5. **Persist** — Updates `slack_state.json` to record the sent report

---

## ⚙️ GitHub Actions Workflows

### `specter_daily.yml` — Daily Intelligence Sweep
| Field | Value |
|-------|-------|
| **Schedule** | Configurable via dashboard (default: `32 1 * * *` UTC) |
| **Runner** | `ubuntu-latest`, Python 3.11 |
| **Script** | `python run_agent.py` |
| **Secrets** | `GEMINI_API_KEY`, `TAVILY_API_KEY`, `SENDER_EMAIL`, `SENDER_PASSWORD` |
| **Output** | Commits PDF to `reports/` folder |

### `slack_daily.yml` — Daily Slack Reporter
| Field | Value |
|-------|-------|
| **Schedule** | `30 5 * * *` UTC (11:00 AM IST) |
| **Runner** | `ubuntu-latest`, Python 3.11 |
| **Script** | `python run_slack_agent.py` |
| **Secrets** | `GEMINI_API_KEY`, `SLACK_WEBHOOK_URL` |
| **Output** | Posts summary to Slack, commits `slack_state.json` |

---

## 📁 Configuration Files

| File | Purpose |
|------|---------|
| `config.json` | Runtime configuration — target search keywords, email recipients, schedule time. Updated from the dashboard UI. |
| `.env` | Local API keys and secrets (not committed to Git) |
| `.env.example` | Template showing all required/optional environment variables |
| `requirements.txt` | Python package dependencies |
| `packages.txt` | System-level dependencies for Streamlit Cloud (`libcairo2-dev`) |

---

## 🔑 Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key — primary LLM for all agents |
| `TAVILY_API_KEY` | ⬜ Recommended | Tavily API key for deep AI-powered web search |
| `OPENAI_API_KEY` | ⬜ Optional | OpenAI fallback when Gemini quota exhausted |
| `GROQ_API_KEY` | ⬜ Optional | Groq fallback (Llama 3.3 70B) |
| `ANTHROPIC_API_KEY` | ⬜ Optional | Claude fallback (Claude 3 Haiku) |
| `GOOGLE_SEARCH_API_KEY` | ⬜ Optional | Google Custom Search API for additional research |
| `GOOGLE_SEARCH_CX` | ⬜ Optional | Google Custom Search Engine ID |
| `GITHUB_PAT` | ⬜ Optional | GitHub Personal Access Token for repo operations |
| `GITHUB_REPO` | ⬜ Optional | GitHub repo name (e.g., `Parimal195/MAS`) |
| `SENDER_EMAIL` | ⬜ For email | Gmail address for sending reports |
| `SENDER_PASSWORD` | ⬜ For email | Gmail App Password |
| `SLACK_WEBHOOK_URL` | ⬜ For Slack | Slack Incoming Webhook URL |
| `APP_PASSWORD` | ⬜ Optional | Dashboard admin password (default: `specter`) |

---

## 🚀 Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/Parimal195/MAS.git
cd MAS
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 4. Run the Dashboard
```bash
streamlit run app.py
```

### 5. Run Headless (CLI)
```bash
# Intelligence scan
python run_agent.py

# Slack reporter
python run_slack_agent.py
```

---

## 🛠 Tech Stack

| Category | Technologies |
|----------|-------------|
| **LLM Providers** | Google Gemini (primary), Anthropic Claude, Groq (Llama 3.3), OpenAI |
| **Web Search** | Tavily (deep AI search), DuckDuckGo, Google Custom Search |
| **Frontend** | Streamlit |
| **PDF Generation** | xhtml2pdf, python-markdown |
| **Document Export** | python-docx (DOCX), xhtml2pdf (PDF), Markdown |
| **Email** | smtplib (Gmail SMTP) |
| **Version Control** | PyGithub (GitHub API) |
| **Automation** | GitHub Actions (cron-based workflows) |
| **Messaging** | Slack Incoming Webhooks |
| **Logging** | Python `logging` module |
| **Language** | Python 3.11 |

---

## 📂 Directory Structure

```
MAS/
├── .devcontainer/          # Dev container configuration
├── .github/
│   └── workflows/
│       ├── specter_daily.yml    # Daily intelligence scan workflow
│       └── slack_daily.yml      # Daily Slack reporter workflow
├── .vscode/                # VS Code settings
├── documentation/          # Additional documentation files
├── error_logs/             # Auto-generated error logs (pushed to GitHub)
├── reports/                # Generated PDF/DOCX reports
├── logs/                   # Local log files (prd_engine.log)
│
├── app.py                  # 🎛️  Streamlit Dashboard (main entry point)
├── streamintel_agent.py    # 🧠  Specter AI Research Agent
├── prd_engine.py           # 📋  7-Agent PRD System (2293 lines)
├── pdf_utils.py            # 📄  Markdown → PDF converter
├── email_utils.py          # ✉️  Gmail SMTP email dispatcher
├── logger_config.py        # 📊  Logging configuration
├── run_agent.py            # ▶️  Headless Specter runner (GitHub Actions)
├── run_slack_agent.py      # ▶️  Headless Slack runner (GitHub Actions)
├── slack_agent.py          # 💬  Slack reporter agent
│
├── config.json             # ⚙️  Runtime config (keywords, emails, schedule)
├── .env.example            # 🔑  Environment variable template
├── requirements.txt        # 📦  Python dependencies
├── packages.txt            # 📦  System dependencies (for Streamlit Cloud)
├── .gitignore              # 🚫  Git ignore rules
└── README.md               # 📖  This file
```

---

<p align="center">
  <b>Built with ❤️ by Parimal</b><br>
  <i>Powered by Google Gemini · Streamlit · GitHub Actions</i>
</p>
]]>
