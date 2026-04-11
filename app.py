import streamlit as st
import os
import json
import pytz
from datetime import datetime
from dotenv import load_dotenv
from github import Github
from streamintel_agent import StreamIntelAgent
from pdf_utils import markdown_to_pdf
from email_utils import send_report_email

# Load variables
load_dotenv()

st.set_page_config(page_title="SPECTER | STREAMINTEL", page_icon="👁️", layout="wide")

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

# --- GITHUB HELPER FUNCTIONS ---
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

# --- UI TABS ---

tab_input, tab_dashboard = st.tabs(["🎛️ Online Configuration", "⚡ Manual Sweep"])

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
                        pdf_path = markdown_to_pdf(report_md, is_manual=True)
                        st.session_state.last_pdf = pdf_path
                        
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


