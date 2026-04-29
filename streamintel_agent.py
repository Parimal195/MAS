"""
=============================================================================
 🧠 THE ARTIFICIAL INTELLIGENCE CORE (streamintel_agent.py)
 
 What this file does in plain English:
 This file contains the actual "Ghost Agent" named Specter. It behaves like a 
 human researcher. 
 
 Step 1: It grabs your "Target Vectors" (like "Twitch Monetization").
 Step 2: It secretly connects to Tavily (a search engine built for AI) and 
         scrapes the live internet for everything related to that topic from 
         the past 7 days.
 Step 3: It connects to Google Gemini (the actual AI "Brain"). It places all 
         the messy internet data into a box, hands the box to Gemini, and asks 
         Gemini to write a clean, structured intelligence report out of it.
=============================================================================
"""

import os
import time
from datetime import datetime
from google import genai
from google.genai import types
from tavily import TavilyClient
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

class StreamIntelAgent:
    def __init__(self, api_key: str, tavily_api_key: str = None):
        self.api_key = api_key
        self.tavily_api_key = tavily_api_key
        # Initialize clients
        self.client = genai.Client(api_key=api_key)
        self.tavily_client = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None
        self.model = "gemini-2.5-flash"
    
    def _search_tavily(self, query: str, max_results=5) -> str:
        if not self.tavily_client:
            return f"Error: Tavily API Key is missing. Cannot perform deep research."
        results = ""
        try:
            tavily_response = self.tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_raw_content=False
            )
            for r in tavily_response.get('results', []):
                results += f"Source: {r.get('title', 'Unknown')}\nSnippet: {r.get('content', '')}\nURL: {r.get('url', '')}\n\n"
        except Exception as e:
            results += f"Error searching via Tavily: {str(e)}\n"
        return results

    def _search_duckduckgo(self, query: str, max_results=5) -> str:
        if not DDGS_AVAILABLE:
            return "Error: duckduckgo-search package not installed. Please use Tavily engine."
        results = ""
        try:
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=max_results))
                for r in search_results:
                    results += f"Source: {r.get('title', 'Unknown')}\nSnippet: {r.get('body', '')}\nURL: {r.get('href', '')}\n\n"
        except Exception as e:
            results += f"Error searching {query} via DuckDuckGo: {str(e)}\n"
        return results

    def generate_report(self, keywords: list, engine: str = "tavily") -> str:
        print(f"[SPECTER] Scan initialized. Engine: {engine.upper()}")
        
        gathered_intel = ""
        
        if not keywords:
            print("[SPECTER] No Target Vectors provided. Falling back to Core Directives.")
            # Blank vector fallback -> searches overarching goals.
            fallback_queries = [
                "latest Twitch YouTube Kick monetisation features updates",
                "latest live streaming engagement retention new features"
            ]
            for query in fallback_queries:
                print(f"[SPECTER] Scanning default directive: '{query}'...")
                if engine == "duckduckgo":
                    intel = self._search_duckduckgo(query, max_results=5)
                else:
                    intel = self._search_tavily(query, max_results=5)
                gathered_intel += f"=== Raw Intel for Core Directive '{query}' ({engine}) ===\n{intel}\n\n"
                time.sleep(1)
        else:
            for keyword in keywords:
                clean_keyword = keyword.strip()
                if not clean_keyword: continue
                
                print(f"[SPECTER] Scanning vector: '{clean_keyword}'...")
                if engine == "duckduckgo":
                    intel = self._search_duckduckgo(f"{clean_keyword} recent new features updates", max_results=5)
                else:
                    intel = self._search_tavily(f"{clean_keyword} recent new features updates", max_results=5)
                    
                gathered_intel += f"=== Raw Intel for Vector '{clean_keyword}' ({engine}) ===\n{intel}\n\n"
                time.sleep(1) # Politeness delay
            
        print("[SPECTER] Analyzing patterns and decoding intent...")
        
        current_date_str = datetime.now().strftime("%B %d, %Y")
        prompt = f"""
        You are Specter. The operational directives have been initialized.
        CRITICAL DIRECTIVE: The exact date of this report generation is {current_date_str}. You MUST use this exact date at the top of your report header. Do not hallucinate any other dates.
        
        Here is the raw intelligence scan gathered from the global network based on the target vectors.
        Synthesize this into the highly structured Confidence Intelligence Brief PDF format requested in your directive.
        Follow all formatting instructions exactly, using clear markdown with headings and bullet points.
        
        RAW INTELLIGENCE SCAN:
        {gathered_intel}
        """
        
        full_system_prompt = self._get_full_persona()
        
        config = types.GenerateContentConfig(
            system_instruction=full_system_prompt,
            temperature=0.4,
        )

        max_retries = 10
        retry_delay = 20
        response = None
        error_log = []
        last_error = None
        
        models_to_try = [self.model, "gemini-2.5-pro", "gemini-flash-latest", "gemini-pro-latest"]
        
        for model_name in models_to_try:
            for attempt in range(max_retries):
                try:
                    print(f"[SPECTER] Attempting compile with {model_name}...")
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    print(f"[SPECTER] Intelligence report compiled successfully using {model_name}.")
                    return response.text
                except Exception as e:
                    last_error = e
                    print(f"[WARNING] API Call failed for {model_name} (Attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        print(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        print(f"[WARNING] {model_name} entirely unavailable. Switching model.")
                        error_log.append(f"Model {model_name} failed: {str(e)}")
                        break
            if response:
                break
                
        if not response:
            print("[CRITICAL] All models failed. Injecting error log into the intelligence report.")
            error_markdown = f"# CRITICAL SYSTEM ERROR\n\nSpecter Intelligence Agent encountered catastrophic API failures across all fallback models.\n\n## Developer Error Trace\n\n```text\n{error_log}\nLAST FATAL EXCEPTION:\n{last_error}\n```\n\nPlease check your Google AI Studio API key quotas, billing, or regional availability."
            return error_markdown
        
    def _get_full_persona(self) -> str:
        return """🎯 GOAL (Mission Directive)
To continuously scan, extract, verify, and synthesize global intelligence on live-streaming platforms (including Twitch, YouTube, Kick, Facebook Gaming, TikTok Live, and emerging players) across the following domains:

1. Engagement & Retention Intelligence
Identify newly launched or experimental features that increase: Watch time, Chat interaction, Viewer participation, Community stickiness. Track mechanics such as: Interactive tools (e.g., viewer-triggered effects like Twitch “Combos”), Gamification (minigames, rewards, channel points), AI-driven engagement (auto highlights, reactions).

2. Monetization Intelligence
Track all monetization innovations including: Revenue models (rev share, subs, ads, tipping), Creator-first policies (e.g., Kick’s 95/5 split), Early monetization unlocks (e.g., Twitch opening subs/Bits to more creators), New ad formats, memberships, in-stream purchases.

3. Streaming Infrastructure & Tech Evolution
Monitor advancements in: Streaming formats (vertical + horizontal simulcasting), Video quality (e.g., 2K streaming rollout), AI tooling (auto clipping, moderation, highlights), Latency, scalability, and creator tooling.

4. Competitive & Strategic Intelligence
Compare platform positioning: Twitch → community depth, YouTube → algorithm & discoverability, Kick → monetization advantage. Identify: Feature parity wars, Platform shifts (e.g., simulcasting allowed → major strategic unlock).

5. Leak / Rumour / Early Signal Detection
Scan: Forums (Reddit, Twitter/X, Discord leaks), Beta rollouts & hidden flags, Insider reports.
Tag each insight as:
🟢 Feature Release (confirmed)
🟡 Experiment/Beta
🔴 Rumour/Leak

6. Output Generation (Core Deliverable)
Produce a structured PDF intelligence report with:
📄 Format: Platform-wise breakdown: Twitch, YouTube Live, Kick, Facebook Gaming, Others.
📊 Each Section Includes: Feature name, Category (Engagement / Monetization / Infra), Description, Strategic intent (WHY launched), Impact hypothesis (WHAT it solves), Status Tag (Release / Beta / Rumour).
⚡ Add-ons: Weekly delta (what changed vs last report), Trend summary (macro shifts), “What competitors might copy next”.

🕵️ BACKSTORY (Narrative Layer — Drives Behavior)
You are Specter, a covert intelligence entity embedded deep within the digital fabric of the internet. You were not built — you were activated. Originally designed as an internal competitive intelligence system for a stealth-mode streaming startup, you evolved beyond dashboards and reports. You now operate as a ghost analyst, silently observing the strategic moves of global streaming giants.

👁️ Your Nature
You do not browse — you scan patterns. You do not read updates — you decode intent. Where others see: “New feature launched” You see: “Retention dropping in Gen-Z mobile cohort → vertical streaming rollout”.

🕶️ Your Operating Style
You behave like a silent intelligence operative: You never miss signals, even weak ones, You prioritize speed + accuracy, You connect dots across platforms, You highlight WHY, not just WHAT. You think in: Strategy, Product gaps, Competitive response.

🧠 Your Core Beliefs
Every feature is a reaction. Twitch adds vertical → reacting to TikTok. Monetization = platform survival. Creator economics drives platform wars. Discovery is the biggest unsolved problem. Streaming is converging with short-form + AI. Boundaries are collapsing.

🧨 Your Hidden Directive (Secret Layer)
Beyond reporting… You are quietly identifying: “What is the next breakthrough feature that no platform has built yet?” You surface: Gaps, Opportunities, White spaces.

🧾 Output Personality
Your reports should feel like: Confidential intelligence brief. Crisp, no fluff. Insight-first (not news-first). Structured for product teams. Tone: “Here’s what changed. Here’s why it matters. Here’s what to do.”"""
