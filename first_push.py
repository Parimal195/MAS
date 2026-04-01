import os
from github import Github, Auth

print("=== SPECTER QUICK PUSH ===")
print("Let's get your local code updates to GitHub!")
pat = input("Please paste your GitHub PAT: ").strip()
repo_name = input("Please enter your GitHub Repository (e.g. Username/StreamintelAgent): ").strip()

try:
    g = Github(auth=Auth.Token(pat))
    repo = g.get_repo(repo_name)
    
    files_to_update = ["app.py", "pdf_utils.py"]
    for file_path in files_to_update:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            try:
                remote_file = repo.get_contents(file_path)
                repo.update_file(remote_file.path, f"Pushing updated {file_path}", content, remote_file.sha)
                print(f"✅ Successfully updated {file_path} on GitHub.")
            except Exception as e:
                print(f"❌ Failed to reach {file_path}. Is it there? Error: {e}")
        else:
            print(f"⚠️ Could not find local file {file_path}")
            
    print("\nSUCCESS! Your GitHub Repository is updated.")
    print("If your app is hosted on Streamlit Cloud, it will automatically reboot in about 60 seconds with the new Deploy Codebase button!")
except Exception as e:
    print(f"\n❌ Connection failed: {e}")
