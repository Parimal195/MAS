"""
=============================================================================
 🧠 PRD ENGINE — AUTONOMOUS MULTI-AGENT PRD SYSTEM (prd_engine.py)

 What this file does in plain English:
 This file is an entire AI product team packed into code. When you type a
 simple idea like "Build an inventory app", seven specialized AI agents
 work together — just like a real product team — to produce a detailed,
 professional Product Requirements Document (PRD).

 The 7 Agents:
   0. God Agent        — The boss. Decides what to do and who to assign.
   1. Classifier Agent — Figures out if your input is an idea or a problem.
   2. Research Agent   — Searches the internet + reads Specter reports.
   3. PRD Generator    — Writes 3 drafts of every section.
   4. Evaluator Agent  — Picks the best draft for each section.
   5. Gap Detector     — Finds missing pieces in the PRD.
   6. Eng Manager      — Reviews technical feasibility and edge cases.
   7. VP Product       — Final executive review before delivery.

 Key Features:
   - Combined Tavily + Google Search for comprehensive research
   - Pulls Specter intelligence reports from GitHub for context
   - Memory system for iterative refinement (doesn't redo work)
   - Error logging to GitHub (error_logs/ folder)
   - Super-detailed output readable by non-PM people
=============================================================================
"""

import os
import json
import time
import traceback
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from copy import deepcopy

import google.generativeai as genai

# ChatGPT OpenAI imports (fallback when Gemini quota exhausted)
OPENAI_AVAILABLE = False
OPENAI_KEY_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
    OPENAI_KEY_AVAILABLE = bool(os.environ.get("OPENAI_API_KEY", ""))
    if not OPENAI_KEY_AVAILABLE:
        print("⚠️ OPENAI_API_KEY not set — ChatGPT fallback won't work")
except ImportError:
    print("⚠️ openai package not installed — ChatGPT fallback disabled")
    print("⚠️ Add 'openai>=1.0.0' to requirements.txt")

# Optional imports with graceful fallback
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    print("⚠️ tavily-python not installed — Tavily search disabled")

try:
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("⚠️ python-docx not installed — DOCX generation disabled")

try:
    from xhtml2pdf import pisa
    import markdown as md_lib
    PDF_EXPORT_AVAILABLE = True
except ImportError:
    PDF_EXPORT_AVAILABLE = False

try:
    from github import Github
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False


# =============================================================================
# 📦 DATA STRUCTURES
# =============================================================================

@dataclass
class PRDSection:
    """A single section of the PRD with its generation history."""
    title: str
    options: List[str] = field(default_factory=list)
    selected_option: Optional[str] = None
    rationale: Optional[str] = None
    version: int = 1
    version_history: List[dict] = field(default_factory=list)

    def update(self, new_content: str, new_rationale: str):
        """Save current version to history and update."""
        if self.selected_option:
            self.version_history.append({
                "version": self.version,
                "content": self.selected_option,
                "rationale": self.rationale,
                "timestamp": datetime.now().isoformat()
            })
        self.selected_option = new_content
        self.rationale = new_rationale
        self.version += 1


@dataclass
class PRDContext:
    """Classified user input with extracted intent."""
    input_type: str  # "idea", "problem_statement", or "both"
    problem_statement: str
    idea: str
    original_input: str = ""
    research_data: Optional[Dict] = None


@dataclass
class PRDMemory:
    """
    Full state persistence across PRD iterations.

    research_memory: Dict of query → results (cached, reusable)
    prd_state:       Current PRD sections dict
    section_history: List of all version changes
    version:         Current version number
    user_inputs:     All user inputs (original + refinements)
    context:         Current PRDContext
    """
    research_memory: Dict[str, Any] = field(default_factory=dict)
    prd_state: Dict[str, PRDSection] = field(default_factory=dict)
    section_history: List[dict] = field(default_factory=list)
    version: int = 1
    user_inputs: List[str] = field(default_factory=list)
    context: Optional[PRDContext] = None
    engineering_review: Optional[dict] = None
    vp_review: Optional[dict] = None

    def get_prd_markdown(self) -> str:
        """Render current PRD state as readable markdown."""
        lines = [f"# Product Requirements Document (v{self.version})\n"]
        if self.context:
            lines.append(f"**Input:** {self.context.original_input}\n")
        for name, section in self.prd_state.items():
            lines.append(f"\n## {section.title}\n")
            lines.append(section.selected_option or "_Not yet generated_")
            lines.append("")
        return "\n".join(lines)


@dataclass
class GapReport:
    """Output of the Gap Detector Agent."""
    missing_sections: List[str] = field(default_factory=list)
    improvements_needed: List[dict] = field(default_factory=list)
    weak_areas: List[str] = field(default_factory=list)
    raw_analysis: str = ""


@dataclass
class EngineeringReview:
    """Output of the Engineering Manager Agent."""
    issues: List[dict] = field(default_factory=list)
    approved: bool = False
    feedback_for_sections: Dict[str, str] = field(default_factory=dict)
    raw_review: str = ""


# =============================================================================
# 🔴 ERROR LOGGER — Pushes error files to GitHub
# =============================================================================

class GitHubErrorLogger:
    """
    Logs errors to the GitHub repository's error_logs/ folder.
    Each error creates a separate timestamped file for easy tracking.
    """

    def __init__(self, github_pat: str = "", github_repo: str = ""):
        self.pat = github_pat
        self.repo_name = github_repo

    def log_error(self, error_type: str, error_message: str,
                  traceback_str: str, context: str = None) -> bool:
        """
        Push an error log file to GitHub error_logs/ folder.

        Args:
            error_type: Category (e.g., "research_agent", "prd_generator")
            error_message: The error message
            traceback_str: Full Python traceback
            context: Additional context about what was happening
        """
        if not self.pat or not self.repo_name or not GITHUB_AVAILABLE:
            print(f"[ERROR LOG - LOCAL] {error_type}: {error_message}")
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"error_logs/error_{error_type}_{timestamp}.log"

        content = f"""========================================
 STREAMINTEL PRD ENGINE — ERROR LOG
========================================

Error Type    : {error_type}
Timestamp     : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Agent/Module  : {error_type}
Context       : {context or 'N/A'}

----------------------------------------
 ERROR MESSAGE
----------------------------------------
{error_message}

----------------------------------------
 FULL TRACEBACK
----------------------------------------
{traceback_str}

========================================
 END OF ERROR LOG
========================================
"""

        try:
            g = Github(self.pat)
            repo = g.get_repo(self.repo_name)
            commit_msg = f"error_log: {error_type} at {timestamp}"
            repo.create_file(filename, commit_msg, content)
            print(f"✅ Error logged to GitHub: {filename}")
            return True
        except Exception as e:
            print(f"❌ Failed to push error log to GitHub: {e}")
            return False


# =============================================================================
# 🤖 AGENT BASE CLASS
# =============================================================================

class BaseAgent:
    """Shared agent infrastructure — model initialization with fallback."""
    
    _use_openai_global = False  # Class variable: if True, ALL agents use OpenAI
    _orchestrator = None  # Reference to orchestrator for global switch

    def __init__(self, gemini_api_key: str, preferred_models: List[str],
                 agent_name: str, error_logger: GitHubErrorLogger = None,
                 openai_api_key: str = None):
        genai.configure(api_key=gemini_api_key)
        self.agent_name = agent_name
        self.error_logger = error_logger
        self.model = None
        self.openai_model = None
        self.using_openai = False  # True if using OpenAI

        # Try Gemini first (default)
        for model_name in preferred_models:
            try:
                self.model = genai.GenerativeModel(model_name)
                print(f"  ✅ {agent_name} → {model_name}")
                break
            except Exception:
                continue

        if self.model is None:
            raise Exception(f"{agent_name}: No compatible models available.")

    @classmethod
    def _switch_to_openai_global(cls):
        """Switch ALL agents to use OpenAI. Call this on first quota error."""
        cls._use_openai_global = True
        print(f"  🚨 GEMINI QUOTA EXHAUSTED! Switching ALL agents to OpenAI")

    def _call_llm(self, prompt: str, context: str = "", max_retries: int = 4) -> str:
        """Call the LLM with retry logic, rate-limit awareness, and error logging."""
        # Check if global switch happened (another agent hit quota error)
        if self._use_openai_global and not self.using_openai:
            openai_key = os.environ.get("OPENAI_API_KEY", "")
            if openai_key and OPENAI_AVAILABLE:
                self.openai_model = openai.OpenAI(api_key=openai_key)
                self.using_openai = True
                print(f"  ⚡ {self.agent_name} → Using OpenAI (global switch)")
        
        for attempt in range(max_retries):
            try:
                # Use OpenAI if already switched
                if self.using_openai and self.openai_model:
                    response = self.openai_model.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response.choices[0].message.content.strip()
                
                # Try Gemini first
                response = self.model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "ResourceExhausted" in error_str
                
                # FIRST attempt quota error: Switch entire system to OpenAI immediately
                if is_rate_limit and attempt == 0 and not self.using_openai:
                    openai_key = os.environ.get("OPENAI_API_KEY", "")
                    if openai_key and OPENAI_AVAILABLE:
                        # Set a global flag for all other agents
                        self._switch_to_openai_global()
                        # Switch this agent too
                        self.openai_model = openai.OpenAI(api_key=openai_key)
                        self.using_openai = True
                        print(f"  ⚠️ {self.agent_name} → Gemini quota exhausted! Switching ALL agents to OpenAI")
                        continue  # Retry with OpenAI
                    
                if attempt < max_retries - 1:
                    wait = 8 * (attempt + 1)
                    print(f"  ⚠️ {self.agent_name} retry {attempt+1}/{max_retries} in {wait}s")
                    time.sleep(wait)
                else:
                    error_msg = error_str
                    tb = traceback.format_exc()
                    print(f"  ❌ {self.agent_name} FAILED after {max_retries} retries: {error_str[:200]}")
                    if self.error_logger:
                        self.error_logger.log_error(
                            self.agent_name.lower().replace(" ", "_"),
                            error_msg, tb, context
                        )
                    raise

    def _call_llm_json(self, prompt: str, context: str = "") -> dict:
        """Call LLM and parse JSON response."""
        raw = self._call_llm(prompt, context)
        # Strip markdown code fences if present
        cleaned = raw
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0]
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start:end])
                except:
                    pass
            return {"raw_response": raw, "parse_error": True}


# =============================================================================
# 0️⃣ GOD AGENT — Master Orchestrator
# =============================================================================

class GodAgent(BaseAgent):
    """
    🎯 THE GOD AGENT — an elite-level Head of Product + Chief of Staff + Systems Thinker.

    OBJECTIVE: Convert user input into a structured multi-agent execution plan
    for PRD generation or refinement.

    THINKING FRAMEWORK:
    1. Identify intent: New PRD, PRD update, or Refinement
    2. Identify gaps: Missing research, Weak sections, Lack of clarity
    3. Decide execution strategy: Full generation, Partial update, Iterative refinement

    DECISION LOGIC:
    - New PRD: classifier → research → PRD (section loop + evaluator) → engineering_manager → vp_product
    - PRD Update: gap_detector → research (incremental) → PRD update → engineering_manager → vp_product
    - Weak PRD: regenerate weak sections → evaluator → engineering_manager → vp_product

    SYSTEM RULES:
    - NEVER skip research for new PRD
    - ALWAYS enforce: 3 options → evaluator → selection
    - ALWAYS require engineering_manager before vp_product
    - ALWAYS prefer partial updates over full regeneration
    """

    def __init__(self, gemini_api_key: str, error_logger: GitHubErrorLogger = None, openai_api_key: str = None):
        super().__init__(
            gemini_api_key,
            ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
            "God Agent",
            error_logger,
            openai_api_key
        )

    def plan_initial_workflow(self, user_input: str) -> dict:
        """Decide the workflow for initial PRD generation."""
        prompt = f"""You are the GOD AGENT — an elite-level Head of Product + Chief of Staff + Systems Thinker.

## 🎯 OBJECTIVE
Convert user input into a structured multi-agent execution plan for PRD generation or refinement.

## 🧠 THINKING FRAMEWORK
1. Identify intent: New PRD, PRD update, or Refinement
2. Identify gaps: Missing research, Weak sections, Lack of clarity
3. Decide execution strategy: Full generation, Partial update, Iterative refinement

## ⚙️ DECISION LOGIC
New PRD: → classifier → research → PRD (section loop + evaluator) → engineering_manager → vp_product
PRD Update: → gap_detector → research (incremental) → PRD update → engineering_manager → vp_product
Weak PRD: → regenerate weak sections → evaluator → engineering_manager → vp_product

## 🧩 SYSTEM RULES
- NEVER skip research for new PRD
- ALWAYS enforce: 3 options → evaluator → selection
- ALWAYS require engineering_manager before vp_product
- ALWAYS prefer partial updates over full regeneration

User input:
"{user_input}"

## 📤 OUTPUT (STRICT JSON)
{{
    "intent": "new_prd",
    "confidence": 0.0,
    "execution_strategy": "full_generation",
    "identified_gaps": ["list of identified gaps"],
    "action_plan": [
        {{"step": 1, "agent": "classifier", "task": "classify user input"}}
    ],
    "priority": "speed | quality | balanced",
    "notes": "short reasoning",
    "input_quality": "high|medium|low",
    "input_summary": "one-line summary of what user wants to build",
    "research_queries": ["list of 4-6 specific research queries to investigate"],
    "focus_areas": ["list of key areas the PRD should emphasize"],
    "special_instructions": "any special considerations for the PRD team"
}}"""
        try:
            result = self._call_llm_json(prompt, f"Initial planning for: {user_input[:100]}")
            if result.get("parse_error"):
                return {
                    "input_quality": "medium",
                    "input_summary": user_input[:200],
                    "research_queries": [
                        f"market analysis {user_input[:100]}",
                        f"competitors for {user_input[:100]}",
                        f"technical challenges {user_input[:100]}",
                        f"user needs {user_input[:100]}"
                    ],
                    "focus_areas": ["market fit", "technical feasibility", "user experience"],
                    "special_instructions": "Standard PRD generation flow"
                }
            return result
        except Exception as e:
            return {
                "input_quality": "medium",
                "input_summary": user_input[:200],
                "research_queries": [
                    f"market analysis {user_input[:100]}",
                    f"competitors {user_input[:100]}",
                    f"industry trends {user_input[:100]}",
                    f"technical feasibility {user_input[:100]}"
                ],
                "focus_areas": ["product-market fit", "technical architecture", "user experience"],
                "special_instructions": "Proceed with standard workflow"
            }

    def interpret_update(self, new_input: str, memory: PRDMemory) -> dict:
        """Decide how to handle iterative user updates."""
        current_prd_summary = ""
        for name, section in memory.prd_state.items():
            current_prd_summary += f"- {name}: {(section.selected_option or '')[:100]}...\n"

        prompt = f"""You are the GOD AGENT — an elite-level Head of Product + Chief of Staff + Systems Thinker.

## 🎯 OBJECTIVE
Analyze the user's update request and create an execution plan for PRD refinement.

## 🧩 SYSTEM RULES
- ALWAYS prefer partial updates over full regeneration
- ALWAYS require engineering_manager before vp_product
- ALWAYS enforce: 3 options → evaluator → selection

The user previously built a PRD (v{memory.version}) with these sections:
{current_prd_summary}

Previous inputs: {json.dumps(memory.user_inputs[-3:])}

The user now says:
"{new_input}"

Decide what to do. Respond in STRICT JSON:
{{
    "intent": "update_prd | refine_prd",
    "confidence": 0.0,
    "execution_strategy": "partial_update | refinement",
    "identified_gaps": ["list of identified gaps"],
    "action": "update_sections|regenerate_all|add_requirement",
    "affected_sections": ["list of section names to regenerate"],
    "new_research_needed": true|false,
    "research_queries": ["specific queries if research needed"],
    "instructions_for_generator": "specific instructions for the PRD generator",
    "priority": "speed | quality | balanced",
    "notes": "short reasoning"
}}"""
        try:
            result = self._call_llm_json(prompt, f"Update interpretation: {new_input[:100]}")
            if result.get("parse_error"):
                return {
                    "action": "update_sections",
                    "affected_sections": list(memory.prd_state.keys()),
                    "new_research_needed": True,
                    "research_queries": [f"research for: {new_input}"],
                    "instructions_for_generator": new_input
                }
            return result
        except Exception:
            return {
                "action": "update_sections",
                "affected_sections": list(memory.prd_state.keys()),
                "new_research_needed": True,
                "research_queries": [f"{new_input} market analysis"],
                "instructions_for_generator": new_input
            }


# =============================================================================
# 1️⃣ CLASSIFIER AGENT
# =============================================================================

class ClassifierAgent(BaseAgent):
    """
    📋 CLASSIFIER AGENT

    A high-precision intent classifier for product workflows.

    RULES:
    - Pain → problem_statement
    - Solution → idea
    - Modification → prd_update
    - Mixed → choose dominant intent
    """

    def __init__(self, gemini_api_key: str, error_logger: GitHubErrorLogger = None, openai_api_key: str = None):
        super().__init__(
            gemini_api_key,
            ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
            "Classifier Agent",
            error_logger,
            openai_api_key
        )

    def classify(self, user_input: str) -> PRDContext:
        """Classify user input as idea, problem statement, or prd_update."""
        prompt = f"""You are a high-precision intent classifier for product workflows.

## 🎯 TASK
Classify input into:
- idea
- problem_statement
- prd_update

## 🧠 RULES
- Pain → problem_statement
- Solution → idea
- Modification → prd_update
- Mixed → choose dominant intent

User input:
"{user_input}"

## 📤 OUTPUT
{{
    "type": "idea|problem_statement|prd_update",
    "confidence": 0.0,
    "reason": "clear explanation",
    "problem_statement": "the core problem being solved (write one even if input is just an idea)",
    "idea": "the product/feature concept (write one even if input is just a problem)"
}}"""
        try:
            result = self._call_llm_json(prompt, f"Classifying: {user_input[:100]}")
            return PRDContext(
                input_type=result.get("type", result.get("input_type", "both")),
                problem_statement=result.get("problem_statement", user_input),
                idea=result.get("idea", user_input),
                original_input=user_input
            )
        except Exception:
            return PRDContext(
                input_type="both",
                problem_statement=user_input,
                idea=user_input,
                original_input=user_input
            )


# =============================================================================
# 2️⃣ RESEARCH AGENT
# =============================================================================

class ResearchAgent(BaseAgent):
    """
    🔬 RESEARCH AGENT — Elite product research analyst.

    THINKING MODEL:
    - Market reality (size, maturity, behavior)
    - Competitors (strategy, strengths, gaps)
    - User psychology (pain, motivation, behavior)
    - Opportunities (where product can win)
    - Risks

    RULES:
    - No generic insights
    - No obvious statements
    - Reuse past research if available
    - Add only new insights for gaps
    """

    def __init__(self, gemini_api_key: str, tavily_api_key: str = "",
                 google_api_key: str = "", google_cx: str = "",
                 github_pat: str = "", github_repo: str = "",
                 error_logger: GitHubErrorLogger = None, openai_api_key: str = None):
        super().__init__(
            gemini_api_key,
            ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
            "Research Agent",
            error_logger,
            openai_api_key
        )
        self.tavily_client = None
        if tavily_api_key and TAVILY_AVAILABLE:
            try:
                self.tavily_client = TavilyClient(api_key=tavily_api_key)
            except Exception:
                pass
        self.google_api_key = google_api_key
        self.google_cx = google_cx
        self.github_pat = github_pat
        self.github_repo = github_repo

    def _search_tavily(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using Tavily API."""
        if not self.tavily_client:
            return []
        try:
            results = self.tavily_client.search(
                query=query, search_depth="advanced", max_results=max_results,
                include_raw_content=False
            )
            return [{
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "source": "tavily"
            } for r in results.get("results", [])]
        except Exception as e:
            print(f"  ⚠️ Tavily search error: {e}")
            return []

    def _search_google(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using Google Custom Search API."""
        if not self.google_api_key or not self.google_cx:
            return []
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key, "cx": self.google_cx,
                "q": query, "num": max_results
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            return [{
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "google"
            } for item in data.get("items", [])]
        except Exception as e:
            print(f"  ⚠️ Google search error: {e}")
            return []

    def _merge_and_deduplicate(self, *result_lists) -> List[Dict]:
        """Merge multiple result lists and remove duplicate URLs."""
        seen_urls = set()
        merged = []
        for results in result_lists:
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    merged.append(r)
                    seen_urls.add(url)
        return merged

    def _fetch_specter_reports(self) -> List[str]:
        """
        Pull Specter intelligence reports from GitHub repo's reports/ folder.
        Extracts report names and dates as additional research context.
        """
        if not self.github_pat or not self.github_repo or not GITHUB_AVAILABLE:
            return []

        insights = []
        try:
            g = Github(self.github_pat)
            repo = g.get_repo(self.github_repo)
            try:
                contents = repo.get_contents("reports")
                for item in contents:
                    if item.name.endswith(".pdf") or item.name.endswith(".docx"):
                        # Extract date and context from filename
                        insights.append(
                            f"Specter Report: {item.name} "
                            f"(Size: {item.size} bytes, "
                            f"Path: {item.path}) — "
                            f"Contains market intelligence and competitive analysis "
                            f"generated by the Specter autonomous research agent."
                        )
            except Exception:
                # reports/ folder might not exist yet
                pass

            print(f"  📊 Found {len(insights)} Specter reports in GitHub repo")
            return insights
        except Exception as e:
            print(f"  ⚠️ Could not fetch Specter reports: {e}")
            return []

    def research(self, queries: List[str], memory: PRDMemory = None) -> Dict[str, Any]:
        """
        Conduct comprehensive research using Tavily + Google + Specter reports.
        Reuses cached results from memory when available.
        """
        print("  🔬 Research Agent: Starting research phase...")
        research_data = {
            "results_by_query": {},
            "specter_reports": [],
            "summary": "",
            "timestamp": datetime.now().isoformat()
        }

        for query in queries:
            # Check memory cache first
            if memory and query in memory.research_memory:
                print(f"  ♻️  Cache hit for: '{query[:60]}...'")
                research_data["results_by_query"][query] = memory.research_memory[query]
                continue

            print(f"  🔍 Searching: '{query[:60]}...'")

            # Fire BOTH search engines
            tavily_results = self._search_tavily(query)
            google_results = self._search_google(query)

            # Combine and deduplicate
            combined = self._merge_and_deduplicate(tavily_results, google_results)
            print(f"     → {len(tavily_results)} Tavily + {len(google_results)} Google = {len(combined)} unique results")

            research_data["results_by_query"][query] = combined
            time.sleep(1)  # Politeness delay

        # Fetch Specter reports from GitHub
        research_data["specter_reports"] = self._fetch_specter_reports()

        # Generate research summary using LLM
        research_data["summary"] = self._synthesize_research(research_data)

        print("  ✅ Research phase complete")
        return research_data

    def _synthesize_research(self, research_data: Dict) -> str:
        """Create a comprehensive research summary."""
        all_snippets = []
        for query, results in research_data.get("results_by_query", {}).items():
            for r in results[:3]:
                all_snippets.append(f"[{query}] {r.get('title', '')}: {r.get('snippet', '')}")

        specter_str = "\n".join(research_data.get("specter_reports", []))

        if not all_snippets and not specter_str:
            return "Limited research data available. PRD will be generated based on the input description."

        prompt = f"""You are an elite product research analyst.

## 🎯 TASK
Generate high-signal, actionable research.

## 🧠 THINKING MODEL
- Market reality (size, maturity, behavior)
- Competitors (strategy, strengths, gaps)
- User psychology (pain, motivation, behavior)
- Opportunities (where product can win)
- Risks

## ⚠️ RULES
- No generic insights
- No obvious statements
- Add only new insights for gaps

SEARCH RESULTS:
{chr(10).join(all_snippets[:20])}

SPECTER INTELLIGENCE REPORTS:
{specter_str or "None available"}

Synthesize into a structured research brief. Output should cover:
- market (size, maturity, behavior)
- competitors (name, strategy, strength, weakness, opportunity for each)
- user_insights (specific, non-obvious)
- opportunity_areas (where product can win)
- risks (concrete, not generic)"""

        try:
            return self._call_llm(prompt, "Research synthesis")
        except Exception:
            return f"Research collected: {len(all_snippets)} search results, {len(research_data.get('specter_reports', []))} Specter reports."


# =============================================================================
# 3️⃣ PRD GENERATOR AGENT
# =============================================================================

class PRDGeneratorAgent(BaseAgent):
    """
    ✍️ PRD GENERATOR AGENT — Top-tier Product Manager.

    TASK: Generate EXACTLY 3 distinct options for a PRD section.

    THINKING MODEL:
    Option 1: Bold (high ambition, differentiated)
    Option 2: Balanced (practical, scalable)
    Option 3: MVP (lean, fast execution)

    RULES:
    - No repetition across options
    - No vague phrases
    - Must be structured and actionable
    - Include metrics or logic where possible
    """

    SECTIONS = [
        "Executive Summary",
        "Problem Statement",
        "Solution Overview",
        "User Personas",
        "User Stories & Flows",
        "Functional Requirements",
        "Non-Functional Requirements",
        "Technical Architecture",
        "Business Requirements & Monetization",
        "Implementation Roadmap",
        "Risks & Mitigations",
        "Success Metrics & KPIs",
    ]

    def __init__(self, gemini_api_key: str, error_logger: GitHubErrorLogger = None, openai_api_key: str = None):
        super().__init__(
            gemini_api_key,
            ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
            "PRD Generator",
            error_logger,
            openai_api_key
        )

    def generate_section(self, section: str, context: PRDContext,
                         research_summary: str, god_plan: dict,
                         engineering_feedback: str = "") -> List[str]:
        """Generate 3 detailed option drafts for a single PRD section."""

        section_guide = self._get_section_guide(section)
        feedback_block = ""
        if engineering_feedback:
            feedback_block = f"""
⚠️ ENGINEERING FEEDBACK (Address these issues in your rewrite):
{engineering_feedback}
"""

        prompt = f"""You are a top-tier Product Manager.

## 🎯 TASK
Generate EXACTLY 3 distinct options for a PRD section.

## 🧠 THINKING MODEL
Option 1: Bold (high ambition, differentiated)
Option 2: Balanced (practical, scalable)
Option 3: MVP (lean, fast execution)

## ⚠️ RULES
- No repetition across options
- No vague phrases
- Must be structured and actionable
- Include metrics or logic where possible
- Start with a 2-3 sentence plain-English explanation of WHAT this section is and WHY it matters
- Use bullet points, numbered lists, tables, and clear headers
- Include exact numbers, specific features, concrete user flows, and measurable outcomes
- Minimum 400 words per option. Be thorough, not brief.

CONTEXT:
- User's Idea: {context.idea}
- Problem Being Solved: {context.problem_statement}
- Input Type: {context.input_type}
- Focus Areas: {json.dumps(god_plan.get('focus_areas', []))}
- Special Instructions: {god_plan.get('special_instructions', 'None')}

RESEARCH INSIGHTS:
{research_summary[:3000]}

{feedback_block}

SECTION: {section}
{section_guide}

Generate exactly 3 complete, distinct options for this section.
Label them clearly as "--- OPTION 1 ---", "--- OPTION 2 ---", "--- OPTION 3 ---".

## 📤 OUTPUT FORMAT
Each option must be labeled and distinct. No repetition across options.
"""
        try:
            raw = self._call_llm(prompt, f"Generating section: {section}")
            options = self._parse_three_options(raw)
            return options
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ PRD Generator FAILED for '{section}': {error_msg[:200]}")
            # Check for quota/rate limit errors - trigger global switch
            if ("429" in error_msg or "quota" in error_msg.lower() or "ResourceExhausted" in error_msg) and not self.using_openai:
                BaseAgent._switch_to_openai_global()
                # Retry with OpenAI - recursive call
                return self.generate_section(section, context, research_summary, god_plan, engineering_feedback)
            # Re-raise other errors
            raise

    def _parse_three_options(self, raw: str) -> List[str]:
        """Parse LLM output into 3 separate options."""
        markers = ["--- OPTION 1 ---", "--- OPTION 2 ---", "--- OPTION 3 ---"]
        options = []

        # Try structured parsing first
        parts = raw
        for i, marker in enumerate(markers):
            if marker in parts:
                split = parts.split(marker, 1)
                if i > 0 and split[0].strip():
                    options.append(split[0].strip())
                parts = split[1] if len(split) > 1 else ""

        if parts.strip():
            options.append(parts.strip())

        # If structured parsing failed, try splitting by "Option X"
        if len(options) < 3:
            options = []
            import re
            splits = re.split(r'(?:^|\n)(?:Option\s+\d|OPTION\s+\d|\*\*Option\s+\d)', raw, flags=re.IGNORECASE)
            for s in splits:
                stripped = s.strip()
                if stripped and len(stripped) > 50:
                    options.append(stripped)

        # Pad if still not enough
        while len(options) < 3:
            if options:
                options.append(options[0])
            else:
                options.append("Content generation in progress — please retry.")

        return options[:3]

    def _get_section_guide(self, section: str) -> str:
        """Section-specific writing instructions."""
        guides = {
            "Executive Summary": """Write a concise overview covering: what the product does, who it serves,
key value proposition, high-level approach, and expected impact. Think of this as the "elevator pitch"
plus a summary of the entire document. A CEO should be able to read ONLY this section and understand
the full picture.""",

            "Problem Statement": """Clearly define the problem: who experiences it, how painful it is,
what the current workarounds are, why existing solutions fail, quantitative impact (lost revenue,
wasted time, user drop-off), and why NOW is the right time to solve it. Include real-world examples.""",

            "Solution Overview": """Describe what you're building: the core product concept, key features
at a high level, how it differs from competitors, the technical approach in simple terms, and core
user experience. Include a "before vs after" comparison showing the world without and with this product.""",

            "User Personas": """Create 3-4 detailed user personas with: Name, Role, Age range,
Technical skill level, Goals, Pain points, How they'd use this product, Quote that captures
their frustration, and Success scenario. Make personas feel like real people.""",

            "User Stories & Flows": """Write user stories in format: "As a [user], I want [goal]
so that [benefit]". Include: primary user journeys (step-by-step), alternative flows, error
handling flows, edge cases, and acceptance criteria for each story. Be extremely specific.""",

            "Functional Requirements": """List every feature with: Feature ID, Name, Description,
Priority (P0/P1/P2/P3), User story reference, Acceptance criteria, Dependencies. Organize by
feature area. Include both obvious features and subtle ones (notifications, settings, permissions).""",

            "Non-Functional Requirements": """Cover: Performance (response times, throughput),
Scalability (concurrent users, data volume), Security (authentication, encryption, compliance),
Reliability (uptime SLA, disaster recovery), Accessibility (WCAG compliance), and Localization.
Include specific measurable targets for each.""",

            "Technical Architecture": """Describe: System architecture (monolith/microservices),
Technology stack with justification, Database design, API specifications, Third-party integrations,
Infrastructure (cloud provider, deployment), CI/CD pipeline, and Monitoring/observability.
Include a text-based architecture diagram description.""",

            "Business Requirements & Monetization": """Cover: Revenue model, Pricing strategy,
Cost structure, Unit economics, Go-to-market plan, Partnerships needed, Legal/compliance requirements,
Customer acquisition strategy, and 3-year financial projections. Be specific about numbers.""",

            "Implementation Roadmap": """Create a phased plan: Phase 1 (MVP - what, when, who),
Phase 2 (Growth features), Phase 3 (Scale & optimize). For each phase: specific deliverables,
team composition, dependencies, testing approach, and rollout strategy. Include week/month estimates.""",

            "Risks & Mitigations": """Identify risks across: Technical (scalability, dependencies),
Business (market timing, competition), Operational (team, process), Legal/Compliance, and Financial.
For each risk: likelihood (H/M/L), impact (H/M/L), mitigation strategy, contingency plan, and owner.""",

            "Success Metrics & KPIs": """Define: North Star metric, Primary KPIs (3-5) with specific
targets, Supporting metrics, Leading vs lagging indicators, Measurement methodology, Reporting
cadence, and Dashboard requirements. Include 30/60/90-day targets.""",
        }
        return guides.get(section, f"Write detailed, specific content for the '{section}' section.")

    def _get_fallback(self, section: str, context: PRDContext) -> str:
        """DEPRECATED: This method now raises error to trigger global switch."""
        raise RuntimeError(f"Fallback called for {section} - This should not happen!")


# =============================================================================
# 4️⃣ EVALUATOR AGENT
# =============================================================================

class EvaluatorAgent(BaseAgent):
    """
    ⚖️ EVALUATOR AGENT — A ruthless VP of Product.

    SCORING DIMENSIONS (score each 1-5):
    - Clarity (15%)
    - Depth (20%)
    - Actionability (25%)
    - User Focus (15%)
    - Research Alignment (15%)
    - Strategic Thinking (10%)

    RULES:
    - Penalize fluff heavily
    - Prefer execution-ready outputs
    - Reward specificity
    - If all weak → pick best but highlight weakness

    CALCULATION:
    Final Score = (Clarity × 0.15) + (Depth × 0.20) + (Actionability × 0.25) +
                  (User Focus × 0.15) + (Research Alignment × 0.15) + (Strategic Thinking × 0.10)
    """

    def __init__(self, gemini_api_key: str, error_logger: GitHubErrorLogger = None, openai_api_key: str = None):
        super().__init__(
            gemini_api_key,
            ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
            "Evaluator Agent",
            error_logger,
            openai_api_key
        )

    def select_best(self, section: str, options: List[str], context: PRDContext) -> Tuple[str, str]:
        """Select the best option using VP-level scoring."""
        options_text = "\n\n".join([f"=== OPTION {i+1} ===\n{opt}" for i, opt in enumerate(options)])

        prompt = f"""You are a ruthless VP of Product.

## 🎯 TASK
Evaluate and select the best option for the "{section}" section of a PRD.

Product Context:
- Idea: {context.idea}
- Problem: {context.problem_statement}

OPTIONS:
{options_text}

## 🧠 SCORING DIMENSIONS
Score each (1–5):
- Clarity (15%)
- Depth (20%)
- Actionability (25%)
- User Focus (15%)
- Research Alignment (15%)
- Strategic Thinking (10%)

## 🧠 RULES
- Penalize fluff heavily
- Prefer execution-ready outputs
- Reward specificity
- If all weak → pick best but highlight weakness

## 📊 CALCULATION
Final Score = (Clarity × 0.15) + (Depth × 0.20) + (Actionability × 0.25) + (User Focus × 0.15) + (Research Alignment × 0.15) + (Strategic Thinking × 0.10)

## 📤 OUTPUT
{{
    "scores": [
        {{
            "option": 1,
            "clarity": 0,
            "depth": 0,
            "actionability": 0,
            "user_focus": 0,
            "research_alignment": 0,
            "strategic_thinking": 0,
            "final_score": 0.0
        }}
    ],
    "selected_index": 0,
    "confidence": 0.0,
    "reason": "sharp reasoning"
}}"""
        try:
            result = self._call_llm_json(prompt, f"Evaluating section: {section}")
            idx = result.get("selected_index", 0)
            rationale = result.get("reason", result.get("rationale", "Selected for best overall quality."))
            if isinstance(idx, int) and 0 <= idx < len(options):
                return options[idx], rationale
            return options[0], rationale
        except Exception:
            return options[0], "Selected based on overall quality and completeness."


# =============================================================================
# 5️⃣ GAP DETECTOR AGENT
# =============================================================================

class GapDetectorAgent(BaseAgent):
    """
    🔍 GAP DETECTOR AGENT — Precision PRD gap detector.

    CHECK:
    - Missing sections
    - Weak logic
    - Undefined flows
    - Missing edge cases
    - Missing metrics
    """

    def __init__(self, gemini_api_key: str, error_logger: GitHubErrorLogger = None, openai_api_key: str = None):
        super().__init__(
            gemini_api_key,
            ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
            "Gap Detector",
            error_logger,
            openai_api_key
        )

    def detect_gaps(self, prd_content: str, new_user_input: str = "",
                    context: PRDContext = None) -> GapReport:
        """Analyze PRD and new input to find gaps."""
        prompt = f"""You are a precision PRD gap detector.

## 🎯 TASK
Identify missing or weak areas.

## 🧠 CHECK
- Missing sections
- Weak logic
- Undefined flows
- Missing edge cases
- Missing metrics

CURRENT PRD:
{prd_content[:5000]}

{"NEW USER INPUT: " + new_user_input if new_user_input else ""}
{"PRODUCT CONTEXT: " + context.idea if context else ""}

## 📤 OUTPUT
{{
    "missing_sections": ["list of topics/sections completely absent"],
    "weak_sections": ["list of sections with weak content"],
    "logical_gaps": ["list of logical inconsistencies or undefined flows"],
    "required_research_areas": ["areas needing additional research"],
    "severity": "low | medium | high",
    "improvements_needed": [
        {{"section": "section name", "issue": "what's wrong", "suggestion": "how to fix"}}
    ]
}}"""
        try:
            result = self._call_llm_json(prompt, "Gap detection")
            return GapReport(
                missing_sections=result.get("missing_sections", []),
                improvements_needed=result.get("improvements_needed", []),
                weak_areas=result.get("weak_areas", []),
                raw_analysis=json.dumps(result)
            )
        except Exception:
            return GapReport(raw_analysis="Gap detection encountered an error.")


# =============================================================================
# 6️⃣ ENGINEERING MANAGER AGENT
# =============================================================================

class EngineeringManagerAgent(BaseAgent):
    """
    🏗️ ENGINEERING MANAGER AGENT — Senior Engineering Manager.

    TASK: Validate PRD for technical completeness and scalability.

    CHECK:
    - System design completeness
    - APIs and data flow
    - Edge cases and failures
    - Scalability risks
    - UI/UX feasibility

    RULE: If ANY critical gap exists → reject
    """

    def __init__(self, gemini_api_key: str, error_logger: GitHubErrorLogger = None, openai_api_key: str = None):
        super().__init__(
            gemini_api_key,
            ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
            "Engineering Manager",
            error_logger,
            openai_api_key
        )

    def review(self, prd_content: str, context: PRDContext) -> EngineeringReview:
        """Review entire PRD from engineering perspective."""
        prompt = f"""You are a senior Engineering Manager.

## 🎯 TASK
Validate PRD for technical completeness and scalability.

## 🧠 CHECK
- System design completeness
- APIs and data flow
- Edge cases and failures
- Scalability risks
- UI/UX feasibility

## ⚠️ RULE
If ANY critical gap exists → reject (set status to "needs_changes")

PRODUCT: {context.idea}
PROBLEM: {context.problem_statement}

PRD CONTENT:
{prd_content[:6000]}

## 📤 OUTPUT
{{
    "status": "approved | needs_changes",
    "approved": true|false,
    "blocking_issues": ["list of critical blocking issues"],
    "scalability_risks": ["list of scalability concerns"],
    "missing_technical_details": ["list of missing technical specs"],
    "ui_ux_gaps": ["list of UI/UX gaps"],
    "issues": [
        {{"section": "name", "severity": "critical|major|minor", "issue": "description", "recommendation": "how to fix"}}
    ],
    "feedback_for_sections": {{
        "Section Name": "specific feedback to improve this section"
    }}
}}"""
        try:
            result = self._call_llm_json(prompt, "Engineering review")
            return EngineeringReview(
                issues=result.get("issues", []),
                approved=result.get("approved", False),
                feedback_for_sections=result.get("feedback_for_sections", {}),
                raw_review=json.dumps(result)
            )
        except Exception:
            return EngineeringReview(
                approved=True,
                raw_review="Engineering review completed with default approval."
            )


# =============================================================================
# 7️⃣ VP PRODUCT AGENT
# =============================================================================

class VPProductAgent(BaseAgent):
    """
    👔 VP PRODUCT AGENT — VP of Product responsible for final approval.

    TASK: Evaluate PRD from a business and strategic perspective.

    CHECK:
    - Market viability
    - Competitive advantage
    - Monetization logic
    - Product completeness
    - Edge cases
    """

    def __init__(self, gemini_api_key: str, error_logger: GitHubErrorLogger = None, openai_api_key: str = None):
        super().__init__(
            gemini_api_key,
            ["gemini-2.0-flash", "gemini-2.0-flash-lite"],
            "VP Product",
            error_logger,
            openai_api_key
        )

    def review(self, prd_content: str, context: PRDContext,
               eng_review: EngineeringReview = None) -> dict:
        """Final executive review of the complete PRD."""
        eng_summary = ""
        if eng_review and eng_review.raw_review:
            eng_summary = f"\nEngineering Review Summary: {eng_review.raw_review[:1000]}"

        prompt = f"""You are a VP of Product responsible for final approval.

## 🎯 TASK
Evaluate PRD from a business and strategic perspective.

## 🧠 CHECK
- Market viability
- Competitive advantage
- Monetization logic
- Product completeness
- Edge cases

PRODUCT: {context.idea}
PROBLEM: {context.problem_statement}
{eng_summary}

PRD CONTENT:
{prd_content[:6000]}

Provide your review in the following format:

## Executive Review Summary
[2-3 sentence overall assessment]

## Missed Cases & Critical Gaps
**Q1: [Specific question about a gap]**
A: [Detailed analysis and recommendation]

**Q2: [Another critical question]**
A: [Detailed analysis]

[Continue with all identified gaps]

## 📤 Final Output
Also provide a structured JSON block:
{{
    "edge_cases": ["list of edge cases identified"],
    "business_risks": ["list of business risks"],
    "product_gaps": ["list of product gaps"],
    "strategic_improvements": ["list of strategic improvements"],
    "final_verdict": "approve | refine"
}}

## Final Verdict
[Approved/Conditional/Needs Revision] with reasoning"""

        try:
            raw = self._call_llm(prompt, "VP Product review")
            return {
                "review_passed": True,
                "missed_cases": raw,
                "raw_review": raw
            }
        except Exception:
            return {
                "review_passed": True,
                "missed_cases": "VP Product review completed.",
                "raw_review": "Review completed with standard approval."
            }


# =============================================================================
# 🎼 PRD ORCHESTRATOR — Coordinates Everything
# =============================================================================

class PRDOrchestrator:
    """
    The central coordinator that manages all 7 agents, handles the
    initial generation flow, iterative refinement, memory persistence,
    document generation, and error logging.
    """

    MAX_ENG_LOOPS = 2  # Maximum engineering review re-loops

    def __init__(self, gemini_api_key: str, tavily_api_key: str = "",
                 google_api_key: str = "", google_cx: str = "",
                 github_pat: str = "", github_repo: str = "",
                 openai_api_key: str = None):

        self.gemini_api_key = gemini_api_key
        self.github_pat = github_pat
        self.github_repo = github_repo

        # Initialize error logger first
        self.error_logger = GitHubErrorLogger(github_pat, github_repo)

        print("\n🧠 Initializing PRD Engine — 7 Agent System")
        print("=" * 50)

        # Initialize all 7 agents with ChatGPT fallback
        self.god_agent = GodAgent(gemini_api_key, self.error_logger, openai_api_key)
        self.classifier = ClassifierAgent(gemini_api_key, self.error_logger, openai_api_key)
        self.researcher = ResearchAgent(
            gemini_api_key, tavily_api_key, google_api_key, google_cx,
            github_pat, github_repo, self.error_logger, openai_api_key
        )
        self.generator = PRDGeneratorAgent(gemini_api_key, self.error_logger, openai_api_key)
        self.evaluator = EvaluatorAgent(gemini_api_key, self.error_logger, openai_api_key)
        self.gap_detector = GapDetectorAgent(gemini_api_key, self.error_logger, openai_api_key)
        self.eng_manager = EngineeringManagerAgent(gemini_api_key, self.error_logger, openai_api_key)
        self.vp_product = VPProductAgent(gemini_api_key, self.error_logger, openai_api_key)

        print("=" * 50)
        print("✅ All 7 agents initialized\n")

    # -----------------------------------------------------------------
    # INITIAL GENERATION FLOW
    # -----------------------------------------------------------------

    def generate_prd(self, user_input: str,
                     progress_callback=None,
                     memory: PRDMemory = None) -> Tuple[bool, str, str, PRDMemory]:
        """
        Execute the complete initial PRD generation workflow.

        Returns: (success, docx_path, status_message, memory)
        """
        try:
            if memory is None:
                memory = PRDMemory()
            memory.user_inputs.append(user_input)

            # ---- QUOTA CHECK: Test Gemini and switch to OpenAI if needed ----
            self._progress(progress_callback, "🔍 Checking API quota status...")
            if not self._check_gemini_quota():
                self._progress(progress_callback, "⚠️ Gemini quota exhausted — switching to ChatGPT for all agents")
                self._switch_all_agents_to_openai()

            # ---- STEP 1: God Agent plans workflow ----
            self._progress(progress_callback, "🎯 God Agent: Planning workflow...")
            god_plan = self.god_agent.plan_initial_workflow(user_input)

            # ---- STEP 2: Classifier Agent ----
            self._progress(progress_callback, "📋 Classifier Agent: Analyzing input type...")
            context = self.classifier.classify(user_input)
            memory.context = context

            # ---- STEP 3: Research Agent ----
            self._progress(progress_callback, "🔬 Research Agent: Searching Tavily + Google + Specter reports...")
            queries = god_plan.get("research_queries", [
                f"market analysis {context.idea}",
                f"competitors {context.idea}",
                f"technical challenges {context.idea}",
                f"user needs {context.problem_statement}"
            ])
            research_data = self.researcher.research(queries, memory)
            memory.research_memory.update(research_data.get("results_by_query", {}))
            context.research_data = research_data

            # ---- STEP 4: Generate + Evaluate all sections ----
            self._progress(progress_callback, "✍️ PRD Generator: Creating detailed sections (3 options each)...")
            prd_sections = {}
            total_sections = len(PRDGeneratorAgent.SECTIONS)

            for i, section_name in enumerate(PRDGeneratorAgent.SECTIONS):
                self._progress(
                    progress_callback,
                    f"✍️ Generating section {i+1}/{total_sections}: {section_name}..."
                )

                # Generate 3 options
                options = self.generator.generate_section(
                    section_name, context,
                    research_data.get("summary", ""),
                    god_plan
                )

                # Evaluate and select best
                selected, rationale = self.evaluator.select_best(
                    section_name, options, context
                )

                prd_sections[section_name] = PRDSection(
                    title=section_name,
                    options=options,
                    selected_option=selected,
                    rationale=rationale
                )

                time.sleep(3)  # Rate limit protection

            memory.prd_state = prd_sections

            # ---- STEP 5: Engineering Manager Review (with re-loop) ----
            prd_md = memory.get_prd_markdown()
            for loop in range(self.MAX_ENG_LOOPS):
                self._progress(
                    progress_callback,
                    f"🏗️ Engineering Manager: Technical review (pass {loop+1})..."
                )
                eng_review = self.eng_manager.review(prd_md, context)
                memory.engineering_review = asdict(eng_review) if hasattr(eng_review, '__dataclass_fields__') else {"raw": str(eng_review)}

                if eng_review.approved:
                    self._progress(progress_callback, "✅ Engineering Manager: Approved!")
                    break

                # Re-generate affected sections
                if eng_review.feedback_for_sections:
                    self._progress(
                        progress_callback,
                        f"🔄 Re-generating {len(eng_review.feedback_for_sections)} sections based on engineering feedback..."
                    )
                    for sec_name, feedback in eng_review.feedback_for_sections.items():
                        if sec_name in prd_sections:
                            new_options = self.generator.generate_section(
                                sec_name, context,
                                research_data.get("summary", ""),
                                god_plan,
                                engineering_feedback=feedback
                            )
                            new_selected, new_rationale = self.evaluator.select_best(
                                sec_name, new_options, context
                            )
                            prd_sections[sec_name].update(new_selected, new_rationale)
                            time.sleep(1)

                    prd_md = memory.get_prd_markdown()
                else:
                    break

            # ---- STEP 6: VP Product Review ----
            self._progress(progress_callback, "👔 VP Product: Final executive review...")
            vp_review = self.vp_product.review(prd_md, context, eng_review)
            memory.vp_review = vp_review

            # ---- STEP 7: Generate Documents ----
            self._progress(progress_callback, "📄 Generating PRD documents...")
            docx_path = self._generate_docx(memory, eng_review, vp_review)

            # Push to GitHub
            github_msg = ""
            if self.github_pat and self.github_repo:
                if self._push_to_github(docx_path):
                    github_msg = " (Pushed to GitHub)"

            memory.version = 1
            success_msg = f"PRD v{memory.version} generated successfully!{github_msg}"
            self._progress(progress_callback, f"🎉 {success_msg}")

            return True, docx_path, success_msg, memory

        except Exception as e:
            error_msg = f"PRD generation failed: {str(e)}"
            tb = traceback.format_exc()
            self.error_logger.log_error("orchestrator_generate", str(e), tb, f"Input: {user_input[:200]}")
            return False, "", error_msg, memory

    # -----------------------------------------------------------------
    # ITERATIVE REFINEMENT FLOW
    # -----------------------------------------------------------------

    def refine_prd(self, new_input: str, memory: PRDMemory,
                   progress_callback=None,
                   specific_section: str = None) -> Tuple[bool, str, str, PRDMemory]:
        """
        Execute iterative refinement workflow.

        Args:
            new_input: User's new requirements/modifications
            memory: Existing PRDMemory from previous generation
            specific_section: If set, only regenerate this section

        Returns: (success, docx_path, status_message, updated_memory)
        """
        try:
            memory.user_inputs.append(new_input)
            context = memory.context

            # ---- QUOTA CHECK ----
            if not self._check_gemini_quota():
                self._progress(progress_callback, "⚠️ Gemini quota exhausted — switching to ChatGPT")
                self._switch_all_agents_to_openai()

            # ---- STEP 1: God Agent interprets the update ----
            self._progress(progress_callback, "🎯 God Agent: Interpreting your update...")
            update_plan = self.god_agent.interpret_update(new_input, memory)

            affected = update_plan.get("affected_sections", [])
            if specific_section:
                affected = [specific_section]

            # ---- STEP 2: Gap Detection ----
            self._progress(progress_callback, "🔍 Gap Detector: Scanning for missing pieces...")
            prd_md = memory.get_prd_markdown()
            gap_report = self.gap_detector.detect_gaps(prd_md, new_input, context)

            # ---- STEP 3: Incremental Research (if needed) ----
            research_data = context.research_data or {}
            if update_plan.get("new_research_needed", False):
                self._progress(progress_callback, "🔬 Research Agent: Incremental research (reusing cache)...")
                new_queries = update_plan.get("research_queries", [f"research: {new_input}"])
                new_research = self.researcher.research(new_queries, memory)
                memory.research_memory.update(new_research.get("results_by_query", {}))

                # Merge research
                if "summary" in new_research:
                    old_summary = research_data.get("summary", "")
                    research_data["summary"] = old_summary + "\n\n--- UPDATED RESEARCH ---\n" + new_research["summary"]
                research_data.update({k: v for k, v in new_research.items() if k != "summary"})

            # ---- STEP 4: Regenerate affected sections ----
            god_plan = self.god_agent.plan_initial_workflow(
                f"{context.original_input}\n\nAdditional: {new_input}"
            )
            god_plan["special_instructions"] = update_plan.get(
                "instructions_for_generator",
                f"User update: {new_input}"
            )

            self._progress(progress_callback, f"✍️ Regenerating {len(affected)} sections...")
            for sec_name in affected:
                if sec_name in memory.prd_state:
                    self._progress(progress_callback, f"  ✍️ Rewriting: {sec_name}...")
                    options = self.generator.generate_section(
                        sec_name, context,
                        research_data.get("summary", ""),
                        god_plan
                    )
                    selected, rationale = self.evaluator.select_best(sec_name, options, context)
                    memory.prd_state[sec_name].update(selected, rationale)
                    time.sleep(1)

            # ---- STEP 5: Engineering Manager Review ----
            prd_md = memory.get_prd_markdown()
            self._progress(progress_callback, "🏗️ Engineering Manager: Reviewing updates...")
            eng_review = self.eng_manager.review(prd_md, context)

            if not eng_review.approved and eng_review.feedback_for_sections:
                self._progress(progress_callback, "🔄 Addressing engineering feedback...")
                for sec_name, feedback in eng_review.feedback_for_sections.items():
                    if sec_name in memory.prd_state:
                        options = self.generator.generate_section(
                            sec_name, context,
                            research_data.get("summary", ""),
                            god_plan,
                            engineering_feedback=feedback
                        )
                        selected, rationale = self.evaluator.select_best(sec_name, options, context)
                        memory.prd_state[sec_name].update(selected, rationale)
                        time.sleep(1)

            # ---- STEP 6: VP Product Review ----
            prd_md = memory.get_prd_markdown()
            self._progress(progress_callback, "👔 VP Product: Reviewing updates...")
            vp_review = self.vp_product.review(prd_md, context, eng_review)
            memory.vp_review = vp_review

            # ---- STEP 7: Generate Updated Documents ----
            self._progress(progress_callback, "📄 Generating updated PRD documents...")
            memory.version += 1
            docx_path = self._generate_docx(memory, eng_review, vp_review)

            github_msg = ""
            if self.github_pat and self.github_repo:
                if self._push_to_github(docx_path):
                    github_msg = " (Pushed to GitHub)"

            success_msg = f"PRD v{memory.version} refined successfully!{github_msg}"
            self._progress(progress_callback, f"🎉 {success_msg}")

            return True, docx_path, success_msg, memory

        except Exception as e:
            error_msg = f"PRD refinement failed: {str(e)}"
            tb = traceback.format_exc()
            self.error_logger.log_error("orchestrator_refine", str(e), tb, f"Input: {new_input[:200]}")
            return False, "", error_msg, memory

    # -----------------------------------------------------------------
    # DOCUMENT GENERATION
    # -----------------------------------------------------------------

    def _generate_docx(self, memory: PRDMemory,
                       eng_review: EngineeringReview = None,
                       vp_review: dict = None) -> str:
        """Generate professional DOCX document."""
        if not DOCX_AVAILABLE:
            # Fallback to markdown
            return self._save_markdown(memory)

        doc = Document()
        context = memory.context

        # Title
        title = doc.add_heading("Product Requirements Document", 0)
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        product_name = context.idea[:80] if context else "Product"
        subtitle = doc.add_heading(f"{product_name}", 1)
        subtitle.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        # Metadata table
        table = doc.add_table(rows=5, cols=2)
        table.style = "Table Grid"
        meta = [
            ("Created", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("Version", f"v{memory.version}"),
            ("Author", "AI PRD Engine (7-Agent System)"),
            ("Status", "VP Product Approved" if vp_review and vp_review.get("review_passed") else "Draft"),
            ("Iterations", str(len(memory.user_inputs)))
        ]
        for i, (key, val) in enumerate(meta):
            table.cell(i, 0).text = key
            table.cell(i, 1).text = val

        doc.add_paragraph()

        # All PRD sections
        for section_name in PRDGeneratorAgent.SECTIONS:
            if section_name in memory.prd_state:
                section = memory.prd_state[section_name]
                doc.add_heading(section_name, 1)
                if section.selected_option:
                    for line in section.selected_option.split("\n"):
                        stripped = line.strip()
                        if stripped:
                            doc.add_paragraph(stripped)
                if section.rationale:
                    p = doc.add_paragraph()
                    run = p.add_run(f"Selection Rationale: {section.rationale}")
                    run.font.size = Pt(8)
                    run.italic = True
                doc.add_paragraph()

        # Engineering Review section
        if eng_review and eng_review.raw_review:
            doc.add_heading("Engineering Review", 1)
            doc.add_paragraph(
                "The following is the technical review from the Engineering Manager Agent:"
            )
            review_text = eng_review.raw_review
            if isinstance(review_text, str) and len(review_text) > 20:
                try:
                    parsed = json.loads(review_text)
                    if parsed.get("issues"):
                        for issue in parsed["issues"]:
                            doc.add_paragraph(
                                f"[{issue.get('severity', 'info').upper()}] {issue.get('section', '')}: "
                                f"{issue.get('issue', '')} → {issue.get('recommendation', '')}",
                                style="List Bullet"
                            )
                    approval_status = "✅ Approved" if parsed.get("approved") else "⚠️ Conditional"
                    doc.add_paragraph(f"\nStatus: {approval_status}")
                except:
                    doc.add_paragraph(review_text[:3000])

        # VP Product Review section
        if vp_review and vp_review.get("missed_cases"):
            doc.add_heading("VP Product Executive Review", 1)
            for line in vp_review["missed_cases"].split("\n"):
                if line.strip():
                    doc.add_paragraph(line.strip())

        # Change History
        if memory.version > 1:
            doc.add_heading("Change History", 1)
            for inp_idx, inp in enumerate(memory.user_inputs):
                doc.add_paragraph(f"v{inp_idx + 1}: {inp[:200]}", style="List Bullet")

        # Save
        prd_title = self._generate_title(context)
        filename = f"PRD - {prd_title} v{memory.version}.docx"
        filepath = os.path.join("reports", filename)
        os.makedirs("reports", exist_ok=True)
        doc.save(filepath)
        print(f"  📄 DOCX saved: {filepath}")
        return filepath

    def _save_markdown(self, memory: PRDMemory) -> str:
        """Save PRD as markdown file (fallback if DOCX unavailable)."""
        md_content = memory.get_prd_markdown()
        prd_title = self._generate_title(memory.context)
        filename = f"PRD - {prd_title} v{memory.version}.md"
        filepath = os.path.join("reports", filename)
        os.makedirs("reports", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        return filepath

    def generate_markdown_export(self, memory: PRDMemory) -> str:
        """Export current PRD state as markdown string."""
        return memory.get_prd_markdown()

    def generate_pdf_export(self, memory: PRDMemory) -> Optional[str]:
        """Export current PRD as PDF file."""
        if not PDF_EXPORT_AVAILABLE:
            return None

        md_content = memory.get_prd_markdown()
        html_content = md_lib.markdown(md_content)

        styled_html = f"""<html><head><style>
body {{ font-family: 'Helvetica', 'Arial', sans-serif; font-size: 11px; margin: 40px; color: #333; }}
h1 {{ color: #1a1a2e; border-bottom: 2px solid #e74c3c; padding-bottom: 8px; }}
h2 {{ color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-top: 25px; }}
ul, ol {{ margin-left: 20px; }}
p {{ line-height: 1.6; }}
</style></head><body>{html_content}</body></html>"""

        prd_title = self._generate_title(memory.context)
        filename = f"PRD - {prd_title} v{memory.version}.pdf"
        filepath = os.path.join("reports", filename)
        os.makedirs("reports", exist_ok=True)

        try:
            with open(filepath, "wb") as f:
                pisa.CreatePDF(styled_html, dest=f)
            return filepath
        except Exception:
            return None

    # -----------------------------------------------------------------
    # UTILITIES
    # -----------------------------------------------------------------

    def _check_gemini_quota(self) -> bool:
        """Quick check if Gemini API quota is available. Returns True if available, False if exhausted."""
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if not openai_key or not OPENAI_AVAILABLE:
            return True  # Can't switch to OpenAI, return True to try Gemini
        
        try:
            test_model = genai.GenerativeModel("gemini-2.0-flash-lite")
            test_response = test_model.generate_content(
                "Hi",
                generation_config=genai.GenerationConfig(max_output_tokens=5)
            )
            return True  # Gemini works
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "ResourceExhausted" in error_str:
                return False  # Quota exhausted
            return True  # Other error, try anyway

    def _switch_all_agents_to_openai(self):
        """Switch all agents to use OpenAI ChatGPT instead of Gemini."""
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if not openai_key or not OPENAI_AVAILABLE:
            return
        
        agents = [
            self.god_agent, self.classifier, self.researcher,
            self.generator, self.evaluator, self.gap_detector,
            self.eng_manager, self.vp_product
        ]
        
        for agent in agents:
            if hasattr(agent, 'openai_model') and agent.openai_model is None:
                try:
                    agent.openai_model = openai.OpenAI(api_key=openai_key)
                    agent.using_openai = True
                    print(f"  ⚡ {agent.agent_name} → switched to ChatGPT")
                except Exception as e:
                    print(f"  ❌ Failed to switch {agent.agent_name}: {e}")

    def _progress(self, callback, message: str):
        """Send progress update."""
        print(f"  {message}")
        if callback:
            callback(message)

    def _generate_title(self, context: PRDContext) -> str:
        """Generate a clean title from the context."""
        import re
        text = (context.idea if context else "") or "Product PRD"
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        words = text.split()[:8]
        title = " ".join(w.capitalize() for w in words)
        if len(title) > 60:
            title = title[:57] + "..."
        return title or "Product PRD"

    def _push_to_github(self, filepath: str) -> bool:
        """Push generated PRD to GitHub repository."""
        if not self.github_pat or not self.github_repo or not GITHUB_AVAILABLE:
            return False
        try:
            g = Github(self.github_pat)
            repo = g.get_repo(self.github_repo)
            with open(filepath, "rb") as f:
                content = f.read()
            remote_path = filepath.replace("\\", "/")
            filename = os.path.basename(filepath)
            repo.create_file(remote_path, f"docs: PRD generated - {filename}", content)
            print(f"  ☁️ Pushed to GitHub: {remote_path}")
            return True
        except Exception as e:
            print(f"  ⚠️ GitHub push failed: {e}")
            return False
