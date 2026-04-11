This document provides a highly granular, file-by-file breakdown of every core component in the **STREAMINTEL (Specter)** and **PRD Engine** systems. For each file, we define its Product Requirements (What it does) and Entity Relationships (How it connects).

---

## streamintel_agent.py — The Specter Research Agent

### Product Requirement Document (PRD)
**Goal:** Serve as the core cognitive engine for daily intelligence research.
**Details:** This file must masquerade as an elite human researcher. It takes an array of keywords (Target Vectors), queries specialized search engines (Tavily/DuckDuckGo), compiles raw webpage snippets, feeds them into Google Gemini with a massive "System Prompt" dictating tone and rules, and returns a clean markdown report.
**Constraints:** Must enforce "No Hallucination" — answers grounded strictly on search results.

### Entity Relationship Diagram (ERD)
- **Inputs Received:** Commands from `app.py` or `run_agent.py`. Raw internet data from **Tavily**.
- **Outputs Sent:** Formatted Markdown → `pdf_utils.py`. Depends on `google.genai`.

---

## app.py — The Dashboard Website

### Product Requirement Document (PRD)
**Goal:** Provide the "Universal Remote Control" UI for non-technical users.
**Details:** This is the interactive website with three tabs:
- *Tab 1* allows tweaking scheduling times and target keywords, authenticating via password, and writing changes to the GitHub repository.
- *Tab 2* allows forcing an immediate manual sweep with a stop button.
- *Tab 3* houses the PRD Maker — the 7-agent PRD generation system.
**Constraints:** Passwords and keys must never be exposed on the frontend.

### Entity Relationship Diagram (ERD)
- **Inputs:** User clicks and text. Streamlit Cloud Environment Variables.
- **Outputs:** Commands to `streamintel_agent.py`. JSON to **GitHub**. Email triggers to `email_utils.py`. PRD commands to `prd_engine.py`.

---

## run_agent.py — The Headless Automation Script

### Product Requirement Document (PRD)
**Goal:** Automate the entire research process without human intervention.
**Details:** Runs in a "Headless" environment (no screen). Acts as glue for the pipeline. Boots up on schedule, reads `config.json`, triggers the agent, generates PDF, sends email.
**Constraints:** Must read `config.json` dynamically. Must catch and log fatal errors automatically.

### Entity Relationship Diagram (ERD)
- **Inputs:** Triggered by **GitHub Action YAML**. Reads `config.json`.
- **Outputs:** Triggers `streamintel_agent.py` → `pdf_utils.py` → `email_utils.py`.

---

## email_utils.py — Email Distribution

### Product Requirement Document (PRD)
**Goal:** Dispatch intelligence reports and PRDs to stakeholders.
**Details:** Handles SMTP mailing: logs into Gmail, crafts multi-part emails (Subject, Body, Attachment), includes rotating motivational quotes, attaches PDFs, dispatches to email lists.
**Constraints:** Must handle empty email lists, catch SMTP failures, search both local and Streamlit Cloud environments for credentials.

### Entity Relationship Diagram (ERD)
- **Inputs:** Triggered by `app.py` or `run_agent.py`. Receives PDF file path from `pdf_utils.py`.
- **Outputs:** Outbound SMTP transfer to **smtp.gmail.com**.

---

## pdf_utils.py — PDF Generation

### Product Requirement Document (PRD)
**Goal:** Format text into enterprise-quality PDF documents.
**Details:** Converts Markdown to HTML, styles with CSS, and renders onto A4 PDF format.
**Constraints:** Must timestamp files exactly to prevent overwrites.

### Entity Relationship Diagram (ERD)
- **Inputs:** Raw text from `streamintel_agent.py`.
- **Outputs:** `.pdf` file to local storage. Filename to `email_utils.py`.

---

## prd_engine.py — The 7-Agent PRD System

### Product Requirement Document (PRD)
**Goal:** Generate enterprise-grade Product Requirements Documents using a 7-agent AI orchestration system.
**Details:** This file implements the complete autonomous PRD pipeline:
- **God Agent** — Master orchestrator that interprets user intent and manages workflow
- **Classifier Agent** — Detects idea vs problem statement
- **Research Agent** — Combined Tavily + Google Search + Specter reports
- **PRD Generator Agent** — Generates 3 super-detailed options per section
- **Evaluator Agent** — Selects best option per section
- **Gap Detector Agent** — Identifies missing pieces during refinement
- **Engineering Manager Agent** — Technical review with re-loop capability
- **VP Product Agent** — Final executive review and approval

Supports iterative refinement: users can add requirements and only affected sections regenerate.
Includes memory system for research caching and PRD state persistence.
Error logging pushes to `error_logs/` folder on GitHub.

**Constraints:** Never skip Engineering Manager review. Never finalize without VP Product approval. Always combine Tavily + Google results. Always reuse cached research before new searches. Maximum 2 engineering re-loops per iteration.

### Agent Architecture
#### 🎯 God Agent (Agent 0)
- **Role:** Head of Product + Chief of Staff
- **Functions:** Intent understanding, workflow planning, update interpretation
- **Model:** Gemini 2.0 Flash

#### 📋 Classifier Agent (Agent 1)
- **Role:** Input Analyst
- **Functions:** Idea vs problem classification
- **Model:** Gemini 2.0 Flash

#### 🔬 Research Agent (Agent 2)
- **Role:** Senior Market Researcher
- **Functions:** Tavily + Google combined search, Specter report fetching, incremental research
- **Model:** Gemini 1.5 Flash

#### ✍️ PRD Generator Agent (Agent 3)
- **Role:** Senior Product Manager & Technical Writer
- **Functions:** Generate 3 options per section, incorporate engineering feedback, super-detailed output
- **Model:** Gemini 1.5 Pro

#### ⚖️ Evaluator Agent (Agent 4)
- **Role:** Quality Selector
- **Functions:** Compare 3 options, select best, provide rationale
- **Model:** Gemini 2.0 Flash

#### 🔍 Gap Detector Agent (Agent 5)
- **Role:** Quality Inspector
- **Functions:** Missing section detection, weak area identification, completeness scoring
- **Model:** Gemini 2.0 Flash

#### 🏗️ Engineering Manager Agent (Agent 6)
- **Role:** Technical Reviewer
- **Functions:** Scalability review, security audit, edge case detection, API gap analysis
- **Model:** Gemini 1.5 Flash

#### 👔 VP Product Agent (Agent 7)
- **Role:** Vice President of Product Management
- **Functions:** Strategic review, GTM risk assessment, missed cases documentation
- **Model:** Gemini 1.5 Flash

### Entity Relationship Diagram (ERD)
- **Inputs:** User idea/problem from `app.py` PRD tab, API keys from environment, Specter reports from GitHub
- **Outputs:** Professional DOCX/PDF/Markdown to `reports/`, progress updates to Streamlit UI, error logs to `error_logs/` on GitHub
- **Dependencies:** `google.generativeai` (Gemini models), `tavily` (search), `docx` (document generation), `PyGithub` (report fetching + error logging), `xhtml2pdf` (PDF export)

---

## error_logs/ — Error Logging Directory

### Product Requirement Document (PRD)
**Goal:** Persistent, auditable error tracking on GitHub.
**Details:** When any agent encounters an error (API failure, model unavailable, network issue), the GitHubErrorLogger creates a timestamped file with full error details and pushes it to this folder via the GitHub API.
**Constraints:** Must never crash the main process — error logging failures are silently ignored.

### Entity Relationship Diagram (ERD)
- **Inputs:** Error data from any agent in `prd_engine.py`.
- **Outputs:** `.log` files pushed to `error_logs/` in GitHub repository.
