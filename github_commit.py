import os
from github import Github
from dotenv import load_dotenv

def commit_to_github():
    # Load environment variables (from .env file)
    load_dotenv()
    
    pat = os.environ.get("GITHUB_PAT")
    repo_name = os.environ.get("GITHUB_REPO")
    
    if not pat or not repo_name:
        print("Error: GITHUB_PAT or GITHUB_REPO not found in your environment.")
        print("Please ensure they are defined in your .env file.")
        return

    try:
        print(f"Connecting to GitHub repository: {repo_name}...")
        g = Github(pat)
        repo = g.get_repo(repo_name)
        
        files_to_update = ["app.py", "pdf_utils.py"]
        
        for file_path in files_to_update:
            try:
                # Read local file content
                with open(file_path, "r", encoding="utf-8") as f:
                    local_content = f.read()
                
                # Get remote file to retrieve its SHA (required for updating)
                remote_file = repo.get_contents(file_path)
                
                # Push the update
                repo.update_file(
                    path=remote_file.path,
                    message=f"Update {file_path} for manual/scheduled PDF naming routing",
                    content=local_content,
                    sha=remote_file.sha
                )
                print(f"✅ Successfully committed changes for {file_path}")
                
            except Exception as e:
                print(f"❌ Failed to commit {file_path}: {e}")
                
        print("\nAll done! Changes are now online.")
        
    except Exception as e:
        print(f"❌ GitHub connection failed: {e}")

if __name__ == "__main__":
    commit_to_github()
