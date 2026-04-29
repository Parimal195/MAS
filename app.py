"""
=============================================================================
 🎛️ THE DASHBOARD WEBSITE (app.py)

 What this file does in plain English:
 This file is the visual interface that you click on. It is built using a tool
 called Streamlit. It acts as the "Universal Remote Control" for the entire 
 intelligence system.

 Tab 1 (Online Configuration): Allows you to save your target keywords and 
                             default emails directly into your GitHub repository 
                             so the background night-robot uses them.
 Tab 2 (Immediate Execution): Allows you to push the giant "Execute" button 
                              to force the AI to do a scan right now and email 
                              the results to you immediately.
=============================================================================
"""

import streamlit as st

st.set_page_config(page_title="SPECTER | STREAMINTEL", page_icon="👁️", layout="wide")

import os
import json
import pytz
from datetime import datetime
from dotenv import load_dotenv

# Force reload .env on every Streamlit run
from pathlib import Path
if Path(".env").exists():
    from dotenv import dotenv_values
    env_vars = dotenv_values(".env")
    for key, value in env_vars.items():
        if value:
            os.environ[key] = value
elif Path(".env.example").exists():
    st.warning("⚠️ Please copy .env.example to .env and add your API keys!")

from github import Github
from streamintel_agent import StreamIntelAgent
try:
    from pdf_utils import markdown_to_pdf
    PDF_UTILS_AVAILABLE = True
except ImportError:
    PDF_UTILS_AVAILABLE = False
    print("Warning: pdf_utils not available - PDF generation disabled")
from email_utils import send_report_email
from prd_engine import PRDOrchestrator
from logger_config import prd_logger


# Add system styling
st.markdown("""
<style>
    .reportview-container .main .block-container{ padding-top: 2rem; }
    h1 { color: #2C3E50; border-bottom: 2px solid #E74C3C; padding-bottom: 15px; }
    .status-text { color: #E74C3C; font-weight: bold; font-family: monospace; font-size: 1.2rem;}
</style>
""", unsafe_allow_html=True)

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("👁️ STREAMINTEL (Project Specter)")
    st.markdown("##### Covert Intelligence Entity · Dashboard Active")
with col_status:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='status-text'>STATUS: CONNECTED TO GITHUB <br> ENGINE: CLOUD HYBRID</div>", unsafe_allow_html=True)

st.divider()

# Core logic securely grabbed from env (Never printed to UI)
APP_PASSWORD = os.environ.get("APP_PASSWORD", "specter") # default simple password
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

col_pwd, _ = st.columns([1, 2])
with col_pwd:
    admin_pwd = st.text_input("Admin Password 🔐 (Required for internal modifications/pushes)", type="password")
is_authenticated = (admin_pwd == APP_PASSWORD)

# Session state initialization
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'keywords' not in st.session_state:
    # Try local load
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
            st.session_state.keywords = cfg.get("keywords", [])
            st.session_state.emails = cfg.get("emails", [])
            time_str = cfg.get("schedule_time", "00:00")
            st.session_state.saved_time = datetime.strptime(time_str, "%H:%M").time()
    except:
        st.session_state.keywords = ["Twitch engagement", "YouTube Live discovery"]
        st.session_state.emails = []
        st.session_state.saved_time = datetime.now().time()

def get_utc_cron_string(local_time_obj, timezone_str):
    """Converts a local time string to UTC and returns the CRON string format (Minute Hour * * *)"""
    local_tz = pytz.timezone(timezone_str)

    # Current date with the chosen time
    today = datetime.now()
    local_dt = local_tz.localize(datetime(today.year, today.month, today.day, local_time_obj.hour, local_time_obj.minute))

    utc_dt = local_dt.astimezone(pytz.utc)
    return f"{utc_dt.minute} {utc_dt.hour} * * *"

def update_github_online(pat, repo_name, keywords_list, emails_list, enable_schedule, cron_string, schedule_time):
    """Pushes updates physically into the GitHub repo configs"""
    try:
        g = Github(pat)
        repo = g.get_repo(repo_name)

        # 1. Update config.json
        config_data = json.dumps({"keywords": keywords_list, "emails": emails_list, "schedule_time": schedule_time.strftime("%H:%M")}, indent=2)
        try:
            file = repo.get_contents("config.json")
            repo.update_file(file.path, "Update agent search vectors globally", config_data, file.sha)
        except Exception:
            # File might not exist yet online
            repo.create_file("config.json", "Initialize config file", config_data)

        # 2. Update the Schedule YAML file if scheduling changed
        try:
            workflow_path = ".github/workflows/specter_daily.yml"
            workflow_file = repo.get_contents(workflow_path)
            content_str = workflow_file.decoded_content.decode("utf-8")

            # This is a naive regex-like search to replace cron, but we will do simple string replace
            lines = content_str.split("\n")
            new_lines = []
            for line in lines:
                if "- cron:" in line:
                    if enable_schedule:
                        new_lines.append(f"    - cron: '{cron_string}'")
                    else:
                        # Disable schedule by putting a cron that doesn't run, or a comment. GitHub Actions ignores commented out triggers.
                        # Wait, we can't easily disable it without breaking yaml, what if we use an impossible date?
                        # Or just comment it out. But simpler is just changing the cron schedule!
                        st.session_state.warning_msg = "Note: To completely disable the backend Action, visit GitHub.com and 'Disable Workflow'. The time was still updated!"
                        new_lines.append(f"    - cron: '{cron_string}'")
                else:
                    new_lines.append(line)

            new_content = "\n".join(new_lines)
            if new_content != content_str:
                 repo.update_file(workflow_file.path, "Update agent schedule globally", new_content, workflow_file.sha)

        except Exception as e:
            raise Exception(f"Failed to update GitHub Actions workflow file: {e}")

        return True
    except Exception as e:
        st.error(f"GitHub Sync Error: {e}")
        return False

def push_codebase_to_github(pat, repo_name, commit_message="Update codebase"):
    try:
        g = Github(pat)
        repo = g.get_repo(repo_name)

        ignore_dirs = ['.git', '__pycache__', 'reports', 'venv', 'env', '.streamlit']
        ignore_files = ['.env', 'github_commit.py']
        updated_count = 0

        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file in ignore_files or file.endswith('.pdf') or file.endswith('.pyc'):
                    continue

                local_path = os.path.join(root, file)
                remote_path = os.path.relpath(local_path, ".").replace("\\", "/")

                with open(local_path, "r", encoding="utf-8") as f:
                    content = f.read()

                try:
                    remote_file = repo.get_contents(remote_path)
                    if remote_file.decoded_content.decode('utf-8') != content:
                        repo.update_file(remote_path, commit_message, content, remote_file.sha)
                        updated_count += 1
                except Exception as e: 
                    if "404" in str(e):
                        repo.create_file(remote_path, commit_message, content)
                        updated_count += 1

        return True, f"Successfully shipped {updated_count} updated files to production!"
    except Exception as e:
        return False, str(e)

def push_report_to_github(pat, repo_name, local_pdf_path):
    try:
        g = Github(pat)
        repo = g.get_repo(repo_name)
        remote_path = local_pdf_path.replace("\\", "/") # e.g. reports/instant-report...
        with open(local_pdf_path, "rb") as f:
            content = f.read()

        commit_message = f"docs: Automated Manual Agent Scan {os.path.basename(local_pdf_path)}"
        repo.create_file(remote_path, commit_message, content)
        return True, "Success"
    except Exception as e:
        return False, str(e)

tab_input, tab_dashboard, tab_prd = st.tabs(["🎛️ Online Configuration", "⚡ Manual Sweep", "📋 PRD Maker"])

with tab_input:
    st.markdown("### ☁️ Cloud Persistence Engine")
    st.info("Because standard free servers sleep automatically, this dashboard connects directly to your GitHub Repository to update the permanent background scheduler and target vectors! The UI is your remote-control.")

    col_vectors, col_schedule = st.columns(2)

    with col_vectors:
        st.subheader("🎯 Target Vectors")
        st.markdown("Supply the exact search targets for the background agent to run.")

        if "keywords_input_str" not in st.session_state:
            st.session_state.keywords_input_str = ", ".join(st.session_state.keywords)

        keywords_input = st.text_area(
            "Target Search Vectors (comma separated)", 
            key="keywords_input_str",
            height=150
        )
        parsed_keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

        st.markdown("---")
        st.markdown("#### Automated Daily Mailing List")
        st.markdown("Supply the emails that should automatically receive the daily backend schedule.")
        if "default_emails_input_str" not in st.session_state:
            st.session_state.default_emails_input_str = ", ".join(st.session_state.emails)

        default_emails_input = st.text_area(
            "Daily Targets (comma separated)", 
            key="default_emails_input_str",
            height=70
        )
        parsed_emails = [e.strip() for e in default_emails_input.split(",") if e.strip()]

        if parsed_keywords != st.session_state.keywords or parsed_emails != st.session_state.emails:
            st.session_state.keywords = parsed_keywords
            st.session_state.emails = parsed_emails
            try:
                with open("config.json", "r") as f: cfg = json.load(f)
            except: cfg = {}
            cfg["keywords"] = parsed_keywords
            cfg["emails"] = parsed_emails
            with open("config.json", "w") as f: json.dump(cfg, f, indent=2)

    with col_schedule:
        st.subheader("⏱️ Remote GitHub Scheduler")

        # Standard timezones based on where users typically deploy
        tz_choices = pytz.all_timezones
        default_tz = tz_choices.index("Asia/Kolkata") if "Asia/Kolkata" in tz_choices else 0 # Defaulting to IST

        time_zone = st.selectbox("Your Local Timezone", tz_choices, index=default_tz)
        schedule_time = st.time_input("When should the background engine run every day?", value=st.session_state.saved_time)

        if schedule_time != st.session_state.saved_time:
            st.session_state.saved_time = schedule_time
            try:
                with open("config.json", "r") as f: cfg = json.load(f)
            except: cfg = {}
            cfg["schedule_time"] = schedule_time.strftime("%H:%M")
            with open("config.json", "w") as f: json.dump(cfg, f, indent=2)

        enable_scheduler = st.toggle("Enable Schedule Change", value=True)

    st.divider()

    if st.button("💾 DEPLOY CONFIGURATION TO GITHUB", type="primary", use_container_width=True):
        if not is_authenticated:
            st.error("Invalid Admin Password. Access Denied.")
        elif not GITHUB_PAT or not GITHUB_REPO:
            st.error("Missing Backend Secrets (GITHUB_PAT/GITHUB_REPO) configuration.")
        else:
            with st.spinner("Connecting to GitHub API and injecting updates into your online repository..."):
                cron_utc = get_utc_cron_string(schedule_time, time_zone)
                success = update_github_online(
                    GITHUB_PAT, 
                    GITHUB_REPO, 
                    parsed_keywords, 
                    parsed_emails,
                    enable_scheduler, 
                    cron_utc,
                    schedule_time
                )
                if success:
                    st.session_state.keywords = parsed_keywords
                    st.session_state.emails = parsed_emails
                    st.success(f"✅ Success! Your background agent will now target these vectors daily at {cron_utc} UTC.")
                    if hasattr(st.session_state, 'warning_msg'):
                        st.warning(st.session_state.warning_msg)

with tab_dashboard:
    col_action, col_report = st.columns([1, 2])

    with col_action:
        st.subheader("Immediate Execution")

        st.markdown("Launch a covert sweep right now from this dashboard.")

        engine_choice = st.radio(
            "Manual Search Engine Model Selection",
            ["tavily", "duckduckgo"],
            format_func=lambda x: "🌐 Tavily (Deep AI Research)" if x == "tavily" else "🦆 DuckDuckGo (Free/Fast/No Auth)",
            disabled=st.session_state.is_running
        )

        st.markdown("---")
        st.subheader("One-Time Manual Mail Drop (Optional)")
        target_emails_input = st.text_input(
            "Ad-Hoc Emails (comma separated)", 
            placeholder="example@gmail.com, team@company.com",
            disabled=st.session_state.is_running
        )
        st.markdown("---")

        # Stop Search Interruption UI Logic
        if st.session_state.is_running:
            st.warning("⏱️ Specter has locked its targets and is analyzing...")
            if st.button("🛑 STOP SEARCH", type="primary", use_container_width=True):
                st.session_state.is_running = False
                st.rerun() # Forces a rerun to interrupt the block!
        else:
            if st.button("▶️ EXECUTE SPECTER NOW", use_container_width=True):
                st.session_state.is_running = True
                st.session_state.engine_choice = engine_choice
                st.session_state.target_emails_input = target_emails_input
                # Clear previous email states
                st.session_state.pop('email_success_msg', None)
                st.session_state.pop('email_error_msg', None)
                st.rerun() # Forces rerun to lock the UI and show the stop button before logic fires

        # The actual heavy logic occurs down here asynchronously relative to UI draws
        if st.session_state.is_running:
            with st.spinner(f"Specter is scanning the digital fabric using {st.session_state.engine_choice.upper()}..."):
                API_KEY = os.environ.get("GEMINI_API_KEY", "")
                TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

                if not API_KEY:
                    st.error("Cannot execute without Gemini API Key.")
                    st.session_state.is_running = False
                    st.stop() # Immediately halts execution so the user can see the error
                else:
                    agent = StreamIntelAgent(api_key=API_KEY, tavily_api_key=TAVILY_API_KEY)
                    try:
                        report_md = agent.generate_report(st.session_state.keywords, engine=st.session_state.engine_choice)
                        st.session_state.last_report = report_md
                        if PDF_UTILS_AVAILABLE:
                            pdf_path = markdown_to_pdf(report_md, is_manual=True)
                            st.session_state.last_pdf = pdf_path
                        else:
                            st.warning("PDF generation unavailable - report saved as markdown only")
                            st.session_state.last_pdf = None

                        # Handle Email Distribution
                        email_input = st.session_state.get('target_emails_input', '')
                        if email_input.strip():
                            emails_list = [email.strip() for email in email_input.split(",") if email.strip()]
                            if emails_list:
                                try:
                                    e_success, e_msg = send_report_email(emails_list, pdf_path)
                                    if e_success:
                                        st.session_state.email_success_msg = e_msg
                                    else:
                                        st.session_state.email_error_msg = e_msg
                                except Exception as e:
                                    st.session_state.email_error_msg = str(e)

                        if is_authenticated and GITHUB_PAT and GITHUB_REPO:
                             success, msg = push_report_to_github(GITHUB_PAT, GITHUB_REPO, pdf_path)
                             if success:
                                 st.session_state.pushed_success = True
                             else:
                                 st.error(f"Cloud Push Failed: {msg}")
                        st.session_state.is_running = False # Reset
                        st.rerun() # Final rerun to show success state
                    except Exception as e:

                        st.error(f"Error during intelligence sweep: {e}")
                        st.session_state.is_running = False
                        st.stop() # Halts execution and keeps error visible

    with col_report:
        if st.session_state.is_running:
            st.info("Processing massive scale intelligence. Stand by...")

        elif 'last_report' in st.session_state:
            st.success("Intelligence compiled successfully.")
            if st.session_state.get('pushed_success'):
                 st.info("☁️ Automatically pushed report to GitHub!")

            if 'email_success_msg' in st.session_state:
                 st.success(f"📧 EMAIL SUCCESS: {st.session_state.email_success_msg}")
            if 'email_error_msg' in st.session_state:
                 st.error(f"📧 EMAIL ERROR: {st.session_state.email_error_msg}")

            if 'last_pdf' in st.session_state and os.path.exists(st.session_state.last_pdf):
                with open(st.session_state.last_pdf, "rb") as f:
                    st.download_button(
                        label="📄 Download Fully Structured PDF Brief",
                        data=f,
                        file_name=os.path.basename(st.session_state.last_pdf),
                        mime="application/pdf",
                        use_container_width=True
                    )

            with st.expander("👁️ View Raw Decoded Markdown", expanded=True):
                st.markdown(st.session_state.last_report)
        else:
            st.info("No compiled dashboard intel. Wait for backend Github Agent or trigger manually.")


with tab_prd:
    st.markdown("### 📋 PRD Maker — Autonomous AI Product Team")
    st.markdown("**7 specialized AI agents** work together to research, write, review, and refine your Product Requirements Document — just like a real product team.")

    # ---- API Keys Configuration ----
    with st.expander("🔑 API Keys Configuration", expanded=True):
        st.markdown("Configure your API keys. **Required:** GEMINI_API_KEY.")
        
        env_file = ".env"
        if not os.path.exists(env_file):
            st.warning(f"⚠️ No `.env` file found. Please create one from the `.env.example` template.")
        
        gemini_key_input = st.text_input(
            "Google Gemini API Key *",
            value=os.environ.get("GEMINI_API_KEY", ""),
            type="password",
            key="gemini_key_input"
        )
        
        if gemini_key_input:
            existing_env = {}
            if os.path.exists(env_file):
                with open(env_file, "r") as f:
                    for line in f:
                        if "=" in line and not line.startswith("#"):
                            key, val = line.strip().split("=", 1)
                            existing_env[key] = val
            
            existing_env["GEMINI_API_KEY"] = gemini_key_input
            
            with open(env_file, "w") as f:
                for key, val in existing_env.items():
                    f.write(f"{key}={val}\n")
            
            os.environ["GEMINI_API_KEY"] = gemini_key_input
            st.success("✅ API key saved to .env file!")
        
        # ---- API Status Display ----
        with st.expander("🔍 API Status", expanded=False):
            gemini_configured = bool(os.environ.get("GEMINI_API_KEY"))
            
            if gemini_configured:
                st.success("✅ Gemini API Key: Configured")
            else:
                st.error("❌ Gemini API Key: Not configured")

    # ---- Session State for PRD ----
    if 'prd_memory' not in st.session_state:
        st.session_state.prd_memory = None
    if 'prd_running' not in st.session_state:
        st.session_state.prd_running = False
    if 'prd_result' not in st.session_state:
        st.session_state.prd_result = None
    if 'agent_log' not in st.session_state:
        st.session_state.agent_log = []
    if 'prd_refine_running' not in st.session_state:
        st.session_state.prd_refine_running = False

    # ---- INPUT SECTION ----
    has_existing_prd = st.session_state.prd_memory is not None

    if not has_existing_prd:
        st.subheader("📝 Describe Your Product Idea or Problem")
        prd_input = st.text_area(
            "What do you want to build? (Be as specific or vague as you like — the agents will figure it out)",
            placeholder="Example: 'Create a mobile app that helps small businesses manage inventory in real-time using AI-powered demand forecasting'",
            height=120,
            key="prd_initial_input"
        )

        if st.button("🚀 Generate PRD", type="primary", use_container_width=True, disabled=st.session_state.prd_running):
            if not prd_input.strip():
                st.error("Please enter an idea or problem statement first.")
            else:
                st.session_state.prd_running = True
                st.session_state.prd_input_text = prd_input
                st.session_state.agent_log = []
                st.session_state.prd_result = None
                st.rerun()

    # ---- GENERATION LOGIC ----
    if st.session_state.prd_running and not has_existing_prd:
        progress_placeholder = st.empty()
        log_placeholder = st.empty()

        def update_progress(message):
            st.session_state.agent_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
            progress_placeholder.info(message)
            log_placeholder.markdown("  \n".join(st.session_state.agent_log[-5:]))

        try:
            GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
            TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
            GOOGLE_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY", "")
            GOOGLE_CX = os.environ.get("GOOGLE_SEARCH_CX", "")

            if not GEMINI_API_KEY:
                st.error("Missing GEMINI_API_KEY in environment variables.")
                st.session_state.prd_running = False
                st.stop()

            orchestrator = PRDOrchestrator(
                GEMINI_API_KEY, TAVILY_API_KEY, GOOGLE_API_KEY, GOOGLE_CX,
                GITHUB_PAT, GITHUB_REPO
            )

            success, docx_path, message, memory = orchestrator.generate_prd(
                st.session_state.prd_input_text, update_progress
            )

            st.session_state.prd_result = {
                'success': success, 'docx_path': docx_path, 'message': message
            }
            if success and memory:
                st.session_state.prd_memory = memory
                st.session_state.prd_orchestrator = orchestrator

        except Exception as e:
            st.session_state.prd_result = {
                'success': False, 'docx_path': '', 'message': f"Error: {str(e)}"
            }
        finally:
            st.session_state.prd_running = False
            st.rerun()

    # ---- REFINEMENT LOGIC ----
    if st.session_state.prd_refine_running and has_existing_prd:
        progress_placeholder = st.empty()

        def update_refine_progress(message):
            st.session_state.agent_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
            progress_placeholder.info(message)

        try:
            orchestrator = st.session_state.get('prd_orchestrator')
            if not orchestrator:
                GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
                TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
                GOOGLE_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY", "")
                GOOGLE_CX = os.environ.get("GOOGLE_SEARCH_CX", "")
                orchestrator = PRDOrchestrator(
                    GEMINI_API_KEY, TAVILY_API_KEY, GOOGLE_API_KEY, GOOGLE_CX,
                    GITHUB_PAT, GITHUB_REPO
                )

            refine_input = st.session_state.get('refine_input_text', '')
            refine_section = st.session_state.get('refine_specific_section', None)

            success, docx_path, message, memory = orchestrator.refine_prd(
                refine_input, st.session_state.prd_memory,
                update_refine_progress, refine_section
            )

            st.session_state.prd_result = {
                'success': success, 'docx_path': docx_path, 'message': message
            }
            if success and memory:
                st.session_state.prd_memory = memory

        except Exception as e:
            st.session_state.prd_result = {
                'success': False, 'docx_path': '', 'message': f"Refinement Error: {str(e)}"
            }
        finally:
            st.session_state.prd_refine_running = False
            st.rerun()

    # ---- DISPLAY RESULTS ----
    if st.session_state.prd_result:
        result = st.session_state.prd_result
        if result['success']:
            st.success(f"✅ {result['message']}")
        else:
            st.error(f"❌ {result['message']}")

    # ---- PRD DISPLAY (when PRD exists in memory) ----
    if has_existing_prd:
        memory = st.session_state.prd_memory
        st.divider()

        col_info, col_version = st.columns([3, 1])
        with col_info:
            st.subheader("📄 Your Product Requirements Document")
        with col_version:
            st.markdown(f"**Version:** v{memory.version}")
            if memory.vp_review and memory.vp_review.get('review_passed'):
                st.markdown("**Status:** ✅ VP Approved")

        # Show each section in expanders
        from prd_engine import PRDGeneratorAgent
        for section_name in PRDGeneratorAgent.SECTIONS:
            if section_name in memory.prd_state:
                section = memory.prd_state[section_name]
                with st.expander(f"📌 {section_name}", expanded=False):
                    st.markdown(section.selected_option or "_Not yet generated_")
                    if section.rationale:
                        st.caption(f"💡 Selection rationale: {section.rationale}")

        # Engineering Review
        if memory.engineering_review:
            with st.expander("🏗️ Engineering Review", expanded=False):
                eng_data = memory.engineering_review
                if isinstance(eng_data, dict):
                    raw = eng_data.get('raw_review', str(eng_data))
                    try:
                        parsed = json.loads(raw) if isinstance(raw, str) else raw
                        if isinstance(parsed, dict) and parsed.get('issues'):
                            for issue in parsed['issues']:
                                sev = issue.get('severity', 'info').upper()
                                st.markdown(f"- **[{sev}]** {issue.get('section', '')}: {issue.get('issue', '')} → _{issue.get('recommendation', '')}_")
                        approval = "✅ Approved" if parsed.get('approved') else "⚠️ Needs Work"
                        st.markdown(f"\n**Status:** {approval}")
                    except:
                        st.markdown(str(eng_data))

        # VP Product Review
        if memory.vp_review and memory.vp_review.get('missed_cases'):
            with st.expander("👔 VP Product Executive Review", expanded=False):
                st.markdown(memory.vp_review['missed_cases'])

        st.divider()

        # ---- HEAD OF PRODUCT MODE ----
        st.subheader("🎩 Head of Product Mode")
        st.markdown("_Add new requirements, modify existing ones, or ask for improvements. Only affected sections will be regenerated._")

        refine_input = st.text_area(
            "Your instructions for the AI team",
            placeholder="Example: 'Add offline mode support' or 'The pricing section needs to include a freemium tier' or 'Make the technical architecture more detailed'",
            height=100,
            key="prd_refine_input"
        )

        col_refine, col_add, col_regen = st.columns(3)

        with col_refine:
            if st.button("🔄 Refine PRD", use_container_width=True, disabled=st.session_state.prd_refine_running):
                if refine_input.strip():
                    st.session_state.prd_refine_running = True
                    st.session_state.refine_input_text = refine_input
                    st.session_state.refine_specific_section = None
                    st.rerun()
                else:
                    st.warning("Please enter refinement instructions first.")

        with col_add:
            if st.button("➕ Add Requirement", use_container_width=True, disabled=st.session_state.prd_refine_running):
                if refine_input.strip():
                    st.session_state.prd_refine_running = True
                    st.session_state.refine_input_text = f"Add this new requirement: {refine_input}"
                    st.session_state.refine_specific_section = None
                    st.rerun()
                else:
                    st.warning("Please describe the new requirement first.")

        with col_regen:
            section_to_regen = st.selectbox(
                "Regenerate specific section",
                ["-- Select --"] + list(memory.prd_state.keys()),
                key="regen_section_select"
            )
            if st.button("🔃 Regenerate Section", use_container_width=True, disabled=st.session_state.prd_refine_running):
                if section_to_regen != "-- Select --":
                    st.session_state.prd_refine_running = True
                    st.session_state.refine_input_text = refine_input or f"Improve and regenerate the {section_to_regen} section with more detail."
                    st.session_state.refine_specific_section = section_to_regen
                    st.rerun()
                else:
                    st.warning("Please select a section to regenerate.")

        st.divider()

        # ---- DOWNLOAD SECTION ----
        st.subheader("📥 Download PRD")
        col_dl1, col_dl2, col_dl3 = st.columns(3)

        # DOCX Download
        with col_dl1:
            if st.session_state.prd_result and st.session_state.prd_result.get('docx_path'):
                docx_path = st.session_state.prd_result['docx_path']
                if os.path.exists(docx_path):
                    with open(docx_path, "rb") as f:
                        st.download_button(
                            "📄 Download DOCX", data=f,
                            file_name=os.path.basename(docx_path),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )

        # Markdown Download
        with col_dl2:
            md_content = memory.get_prd_markdown()
            st.download_button(
                "📝 Download Markdown", data=md_content,
                file_name=f"PRD_v{memory.version}.md",
                mime="text/markdown",
                use_container_width=True
            )

        # PDF Download
        with col_dl3:
            orchestrator = st.session_state.get('prd_orchestrator')
            if orchestrator:
                pdf_path = orchestrator.generate_pdf_export(memory)
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "📕 Download PDF", data=f,
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf",
                            use_container_width=True
                        )
                else:
                    st.button("📕 PDF (unavailable)", disabled=True, use_container_width=True)
            else:
                st.button("📕 PDF (unavailable)", disabled=True, use_container_width=True)

        st.divider()

        # ---- AGENT ACTIVITY LOG ----
        with st.expander("🤖 Agent Activity Log"):
            # Add link to view full log file
            log_file = "logs/prd_engine.log"
            if os.path.exists(log_file):
                with open(log_file, "r") as f:
                    log_content = f.read()
                st.text_area("Full Log File", log_content, height=300, key="full_log_viewer")
            else:
                st.info("No log file found yet.")
            
            st.markdown("---")
            st.markdown("**Session Activity:**")
            if st.session_state.agent_log:
                for log_entry in st.session_state.agent_log:
                    st.text(log_entry)
            else:
                st.info("No agent activity recorded yet.")

        # ---- CHANGE HISTORY ----
        if memory.version > 1:
            with st.expander("📜 Change History"):
                for i, user_inp in enumerate(memory.user_inputs):
                    st.markdown(f"**v{i+1}:** {user_inp}")

        # ---- START OVER ----
        if st.button("🗑️ Start New PRD", use_container_width=True):
            st.session_state.prd_memory = None
            st.session_state.prd_result = None
            st.session_state.prd_running = False
            st.session_state.prd_refine_running = False
            st.session_state.agent_log = []
            if 'prd_orchestrator' in st.session_state:
                del st.session_state.prd_orchestrator
            st.rerun()

    # ---- HOW IT WORKS ----
    with st.expander("ℹ️ How the Multi-Agent System Works"):
        st.markdown("""
        ### 🧠 Your AI Product Team (7 Agents)

        **🎯 God Agent (Master Orchestrator)**
        The "Head of Product" — understands what you want, decides which agents
        to activate, and manages the entire workflow dynamically.

        **📋 Classifier Agent**
        Reads your input and figures out: is this an idea, a problem statement,
        or both? This shapes how the rest of the team approaches the work.

        **🔬 Research Agent**
        Your dedicated market researcher. Searches the internet using multiple
        engines simultaneously, pulls insights from existing Specter intelligence
        reports, and builds a comprehensive research brief.

        **✍️ PRD Generator Agent**
        The workhorse writer. For every section of the PRD, it creates 3 complete
        drafts — each taking a different angle — so the best one can be selected.

        **⚖️ Evaluator Agent**
        Reviews all 3 drafts for each section and picks the strongest one based
        on clarity, completeness, and business alignment.

        **🔍 Gap Detector Agent**
        After the PRD is assembled, this agent scans for missing pieces, weak
        logic, and incomplete sections — like a quality inspector on a factory line.

        **🏗️ Engineering Manager Agent**
        A technical expert who reviews the PRD from an engineering perspective —
        checking for scalability issues, missing API specs, edge cases, and
        technical feasibility. If problems are found, affected sections get
        sent back for rewriting.

        **👔 VP Product Agent**
        The final executive gate. Reviews the complete PRD for business strategy,
        go-to-market risks, competitive gaps, and anything the team might have
        missed. Nothing ships without VP approval.

        ---
        📄 **Output:** Professional DOCX / PDF / Markdown document ready for stakeholders

        🔄 **Iterative:** Use "Refine PRD" to add requirements —
        only affected sections get regenerated, saving time and cost.
        """)




