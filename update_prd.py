import re

with open(r"E:\prd_generator\prd_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace imports (lines 50 to 93)
import_target = """from google import genai
from google.genai import types

GROQ_AVAILABLE = False
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    print("⚠️ groq package not installed — Run: pip install groq")

def get_groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")
    return Groq(api_key=api_key)

CLAUDE_AVAILABLE = False
try:
    import anthropic
    from anthropic import Anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    print("⚠️ anthropic package not installed — Claude fallback disabled")

def get_claude_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=api_key)

OPENAI_AVAILABLE = False
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    print("⚠️ openai package not installed — OpenAI fallback disabled")

def get_openai_client():
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)"""

import_replacement = """OPENAI_AVAILABLE = False
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    print("⚠️ openai package not installed — Run: pip install openai")

def get_openai_client():
    # Connect to local Ollama
    return OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama" # required, but unused
    )"""

content = content.replace(import_target, import_replacement)

# 2. Replace BaseAgent
base_agent_target = """class BaseAgent:
    \"\"\"Shared agent infrastructure — model initialization with global quota handling.\"\"\"
    
    _client = None  # Shared Gemini client
    _groq_client = None  # Shared Groq client
    _claude_client = None  # Shared Claude client
    _openai_client = None  # Shared OpenAI client
    _use_groq_global = False  # Global flag - once set, all agents use Groq
    _use_claude_global = False  # Global flag - once set, all agents use Claude
    _use_openai_global = False  # Global flag - once set, all agents use OpenAI
    _quota_checked = False  # Track if quota check was done
    
    def __init__(self, gemini_api_key: str, preferred_models: List[str],
                 agent_name: str, error_logger: GitHubErrorLogger = None):
        
        # Global quota check - do this only once at start
        if not BaseAgent._quota_checked:
            BaseAgent._quota_checked = True
            BaseAgent._check_quota_and_set_provider(gemini_api_key)
        
        if BaseAgent._use_claude_global:
            # Use Claude directly (quota exhausted or preferred)
            if BaseAgent._claude_client is None and CLAUDE_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY"):
                try:
                    BaseAgent._claude_client = get_claude_client()
                except Exception as e:
                    log_error(prd_logger, "claude_init", str(e), "Failed to init Claude")
            
            self.client = None
            self.model_name = None
            self.groq_model = None
            self.claude_model = BaseAgent._claude_client
            self.using_claude = True
            self.using_groq = False
            prd_logger.info(f"  ✅ {agent_name} -> Claude (claude-3-haiku)")
        elif BaseAgent._use_groq_global:
            # Use Groq directly (quota exhausted)
            if BaseAgent._groq_client is None and GROQ_AVAILABLE and os.environ.get("GROQ_API_KEY"):
                try:
                    BaseAgent._groq_client = get_groq_client()
                except Exception as e:
                    log_error(prd_logger, "groq_init", str(e), "Failed to init Groq")
            
            self.client = None
            self.model_name = None
            self.groq_model = BaseAgent._groq_client
            self.using_groq = True
            self.using_claude = False
            prd_logger.info(f"  ✅ {agent_name} -> Groq (llama-3.3-70b-versatile)")
        else:
            # Try Gemini first
            if BaseAgent._client is None:
                BaseAgent._client = genai.Client(api_key=gemini_api_key)
            
            self.client = BaseAgent._client
            self.model_name = preferred_models[0] if preferred_models else "gemini-2.0-flash"
            self.groq_model = None
            self.using_groq = False
            prd_logger.info(f"  ✅ {agent_name} -> Gemini ({self.model_name})")
        
        self.agent_name = agent_name
        self.error_logger = error_logger

    @classmethod
    def _check_quota_and_set_provider(cls, gemini_api_key: str):
        \"\"\"Check Gemini quota once at start. If exhausted, switch to Claude or Groq globally.\"\"\"
        error_str = ""
        
        # Try Claude first as primary fallback
        if CLAUDE_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY"):
            try:
                test_client = get_claude_client()
                test_response = test_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}]
                )
                if test_response.content[0].text:
                    cls._use_claude_global = True
                    prd_logger.info("✅ Using Claude as primary (Gemini not checked or quota available)")
                    return
            except Exception as e:
                error_str = str(e)
                prd_logger.warning(f"Claude check failed: {error_str[:100]}")
        
        # Check Groq availability
        if not GROQ_AVAILABLE or not os.environ.get("GROQ_API_KEY"):
            prd_logger.info("Groq not available, using Gemini")
            return
        
        try:
            # Try a small test request to Gemini
            test_client = genai.Client(api_key=gemini_api_key)
            test_response = test_client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents="Hi",
            )
            _ = test_response.candidates[0].content.parts[0].text.strip()
            prd_logger.info("✅ Gemini quota available")
        except Exception as e:
            error_str = str(e)
            error_upper = error_str.upper()
            if "429" in error_str or "quota" in error_str.lower() or "RESOURCE_EXHAUSTED" in error_upper:
                cls._use_groq_global = True
                prd_logger.warning("⚠️ Gemini quota exhausted! Switching ALL agents to Groq globally")
            else:
                prd_logger.warning(f"⚠️ Gemini check failed: {error_str[:100]}, using Gemini anyway")

    def _call_llm(self, prompt: str, context: str = "", max_retries: int = 4) -> str:
        \"\"\"Call the LLM - uses global provider setting.\"\"\"
        log_agent_start(prd_logger, self.agent_name, f"LLM call: {context[:50] if context else 'prompt'}")
        
        for attempt in range(2):  # Reduced from 4 to 2 retries
            try:
                if self.using_claude and self.claude_model:
                    log_api_call(prd_logger, "Claude", "messages.create", "CALL", f"Attempt {attempt+1}")
                    response = self.claude_model.messages.create(
                        model="claude-3-haiku-20240307",
                        max_tokens=4096,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    result = response.content[0].text.strip()
                    log_api_call(prd_logger, "Claude", "messages.create", "SUCCESS", f"Response: {len(result)} chars")
                    return result
                
                if self.using_groq and self.groq_model:
                    log_api_call(prd_logger, "Groq", "chat.completions", "CALL", f"Attempt {attempt+1}")
                    response = self.groq_model.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    result = response.choices[0].message.content.strip()
                    log_api_call(prd_logger, "Groq", "chat.completions", "SUCCESS", f"Response: {len(result)} chars")
                    return result
                
                # Gemini path
                log_api_call(prd_logger, "Gemini", "generate_content", "CALL", f"Attempt {attempt+1}")
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                result = response.candidates[0].content.parts[0].text.strip()
                log_api_call(prd_logger, "Gemini", "generate_content", "SUCCESS", f"Response: {len(result)} chars")
                return result
            except Exception as e:
                error_str = str(e)
                error_lower = error_str.lower()
                error_upper = error_str.upper()
                
                # If quota exhausted, try Claude first, then Groq
                if ("429" in error_str or "quota" in error_lower or "RESOURCE_EXHAUSTED" in error_upper or "RESOURCEEXHAUSTED" in error_upper or "rate_limit" in error_lower):
                    # Try Claude as first fallback
                    if not BaseAgent._use_claude_global and CLAUDE_AVAILABLE and os.environ.get("ANTHROPIC_API_KEY"):
                        try:
                            BaseAgent._use_claude_global = True
                            BaseAgent._claude_client = get_claude_client()
                            self.claude_model = BaseAgent._claude_client
                            self.using_claude = True
                            self.client = None
                            self.using_groq = False
                            prd_logger.warning(f"  ⚠️ {self.agent_name} -> Gemini quota exhausted! Switching ALL agents to Claude")
                            continue
                        except Exception:
                            pass
                    # Try Groq as second fallback
                    if not BaseAgent._use_groq_global and GROQ_AVAILABLE and os.environ.get("GROQ_API_KEY"):
                        try:
                            BaseAgent._use_groq_global = True
                            BaseAgent._groq_client = get_groq_client()
                            self.groq_model = BaseAgent._groq_client
                            self.using_groq = True
                            self.client = None
                            self.using_claude = False
                            prd_logger.warning(f"  ⚠️ {self.agent_name} -> Gemini quota exhausted! Switching ALL agents to Groq")
                            continue
                        except Exception:
                            pass
                
                log_error(prd_logger, self.agent_name, error_str, f"Attempt {attempt+1}/{max_retries}")
                
                if attempt < max_retries - 1:
                    wait = 8 * (attempt + 1)
                    prd_logger.warning(f"  ⚠️ {self.agent_name} retry {attempt+1}/{max_retries} in {wait}s")
                    time.sleep(wait)
                else:
                    error_msg = error_str
                    tb = traceback.format_exc()
                    prd_logger.error(f"  ❌ {self.agent_name} FAILED after {max_retries} retries: {error_str[:200]}")
                    log_error(prd_logger, f"{self.agent_name}_call", error_msg, f"Context: {context[:100]}")
                    if self.error_logger:
                        self.error_logger.log_error(
                            self.agent_name.lower().replace(" ", "_"),
                            error_msg, tb, context
                        )
                    raise

        log_agent_end(prd_logger, self.agent_name, "COMPLETE")
        return ""

        log_agent_end(prd_logger, self.agent_name, "COMPLETE")
        return "" """

base_agent_replacement = """class BaseAgent:
    \"\"\"Shared agent infrastructure — model initialization with Ollama.\"\"\"
    
    _client = None  # Shared OpenAI client for Ollama
    
    def __init__(self, gemini_api_key: str, preferred_models: List[str],
                 agent_name: str, error_logger: GitHubErrorLogger = None):
        
        if BaseAgent._client is None and OPENAI_AVAILABLE:
            BaseAgent._client = get_openai_client()
            
        self.client = BaseAgent._client
        self.agent_name = agent_name
        self.error_logger = error_logger

        if agent_name == "VP Product":
            self.model_name = "qwen3.6"
        else:
            self.model_name = "deepseek-v4-pro"
            
        prd_logger.info(f"  ✅ {agent_name} -> Ollama ({self.model_name})")

    def _call_llm(self, prompt: str, context: str = "", max_retries: int = 2) -> str:
        \"\"\"Call the LLM using Ollama API.\"\"\"
        log_agent_start(prd_logger, self.agent_name, f"LLM call: {context[:50] if context else 'prompt'}")
        
        if not self.client:
            prd_logger.error("❌ OpenAI client not initialized. Cannot call Ollama.")
            return ""

        for attempt in range(max_retries):
            try:
                log_api_call(prd_logger, "Ollama", "chat.completions", "CALL", f"Attempt {attempt+1}")
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                result = response.choices[0].message.content.strip()
                log_api_call(prd_logger, "Ollama", "chat.completions", "SUCCESS", f"Response: {len(result)} chars")
                log_agent_end(prd_logger, self.agent_name, "COMPLETE")
                return result
            except Exception as e:
                error_str = str(e)
                log_error(prd_logger, self.agent_name, error_str, f"Attempt {attempt+1}/{max_retries}")
                
                if attempt < max_retries - 1:
                    wait = 2 * (attempt + 1)
                    prd_logger.warning(f"  ⚠️ {self.agent_name} retry {attempt+1}/{max_retries} in {wait}s")
                    time.sleep(wait)
                else:
                    error_msg = error_str
                    import traceback
                    tb = traceback.format_exc()
                    prd_logger.error(f"  ❌ {self.agent_name} FAILED after {max_retries} retries: {error_str[:200]}")
                    log_error(prd_logger, f"{self.agent_name}_call", error_msg, f"Context: {context[:100]}")
                    if self.error_logger:
                        self.error_logger.log_error(
                            self.agent_name.lower().replace(" ", "_"),
                            error_msg, tb, context
                        )
                    raise
        return "" """

content = content.replace(base_agent_target, base_agent_replacement)

# Update VP Product Agent Prompt to reflect structural/clarity improvement role
vp_agent_target = """    def review(self, prd_content: str, context: PRDContext,
               eng_review: EngineeringReview = None) -> dict:
        \"\"\"Final executive review of the complete PRD.\"\"\"
        eng_summary = ""
        if eng_review and eng_review.raw_review:
            eng_summary = f"\\nEngineering Review Summary: {eng_review.raw_review[:1000]}"

        prompt = f\"\"\"You are a VP of Product responsible for final approval.

##  TASK
Evaluate PRD from a business and strategic perspective.

##  CHECK
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

##  Final Output
Also provide a structured JSON block:
{{
    "edge_cases": ["list of edge cases identified"],
    "business_risks": ["list of business risks"],
    "product_gaps": ["list of product gaps"],
    "strategic_improvements": ["list of strategic improvements"],
    "final_verdict": "approve | refine"
}}

## Final Verdict
[Approved/Conditional/Needs Revision] with reasoning\"\"\""""

vp_agent_replacement = """    def review(self, prd_content: str, context: PRDContext,
               eng_review: EngineeringReview = None) -> dict:
        \"\"\"Final executive review of the complete PRD, focusing on clarity, structure, and business alignment.\"\"\"
        eng_summary = ""
        if eng_review and eng_review.raw_review:
            eng_summary = f"\\nEngineering Review Summary: {eng_review.raw_review[:1000]}"

        prompt = f\"\"\"You are a VP of Product responsible for final approval.

##  TASK
Validate PRD completeness, ensure business alignment, improve clarity and structure, verify metrics, and cross-check assumptions and edge cases.

##  CHECK
- Completeness and Clarity of sections
- Alignment with business goals and market
- Metric validity
- Product assumptions and edge cases
- Monetization logic

PRODUCT: {context.idea}
PROBLEM: {context.problem_statement}
{eng_summary}

PRD CONTENT:
{prd_content[:6000]}

Provide your review in the following format:

## Executive Review Summary
[2-3 sentence overall assessment of business alignment and clarity]

## Missed Cases & Structural Improvements
**Q1: [Specific question about an assumption, edge case, or lack of clarity]**
A: [Detailed recommendation to improve structure or clarity]

**Q2: [Another gap or metric refinement]**
A: [Detailed recommendation]

[Continue with all identified gaps]

##  Final Output
Also provide a structured JSON block:
{{
    "edge_cases": ["list of edge cases or assumptions cross-checked"],
    "business_risks": ["list of business alignment risks"],
    "structural_improvements": ["list of clarity or structure improvements"],
    "metrics_feedback": ["feedback on KPIs and metrics"],
    "final_verdict": "approve | refine"
}}

## Final Verdict
[Approved/Conditional/Needs Revision] with reasoning\"\"\""""

content = content.replace(vp_agent_target, vp_agent_replacement)

with open(r"E:\prd_generator\prd_engine.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated prd_engine.py successfully.")
