import os
import sys
import argparse
import re
import json
import urllib.request
import urllib.error
import zipfile
import shutil
import tempfile
import subprocess

# Configurations from environment
PROJECTS_DIR = os.environ.get("PROJECTS_DIR", "/Users/saranggole24/Downloads/projects").strip()
PRIVATE_REPOS = os.environ.get("PRIVATE_REPOS", "false").lower() in ("true", "1", "yes")
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

# Always exclude the archive folders or files
EXCLUDED_REPOS = {"archive"}

def get_github_username(token):
    url = "https://api.github.com/user"
    req = urllib.request.Request(
        url, 
        headers={
            "Authorization": f"token {token}",
            "User-Agent": "GitHub-Project-Publisher",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data.get("login")
    except Exception as e:
        print(f"Error authenticating with GitHub API: {e}")
        return None

def make_proper_name(name):
    # Remove file extension if any
    name = os.path.splitext(name)[0]
    
    # Strip common branch or copy suffixes repeatedly if nested (e.g. repo-main-copy)
    changed = True
    while changed:
        old_name = name
        for suffix in ["-main", "_main", "-master", "_master", "-copy", "_copy"]:
            if name.lower().endswith(suffix):
                name = name[:-len(suffix)]
        changed = (name != old_name)
    
    # Lowercase
    name = name.lower()
    # Replace spaces and underscores with hyphens
    name = re.sub(r'[\s_]+', '-', name)
    # Remove any characters that are not alphanumeric or hyphens
    name = re.sub(r'[^a-z0-9\-]', '', name)
    # Remove consecutive hyphens
    name = re.sub(r'-+', '-', name)
    # Strip leading/trailing hyphens
    name = name.strip('-')
    return name

def create_github_repo(token, repo_name, is_private):
    url = "https://api.github.com/user/repos"
    payload = json.dumps({
        "name": repo_name,
        "private": is_private,
        "auto_init": False
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"token {token}",
            "User-Agent": "GitHub-Project-Publisher",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 201:
                visibility = "private" if is_private else "public"
                print(f"Successfully created {visibility} repository: {repo_name}")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 422:
            print(f"Repository '{repo_name}' already exists on GitHub. Proceeding to push updates.")
            return True
        else:
            print(f"Failed to create repo '{repo_name}'. Status: {e.code}, Reason: {e.reason}")
            return False
    except Exception as e:
        print(f"Error creating repository '{repo_name}': {e}")
        return False

def run_git_command(args, cwd):
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        # Ignore normal Git warnings or already-setup remotes
        if "remote origin already exists" not in result.stderr:
            print(f"Git Command: {' '.join(args)}\nSTDOUT: {result.stdout.strip()}\nSTDERR: {result.stderr.strip()}")
    return result.returncode == 0

def process_and_push_project(dir_path, repo_name, username, token, is_private):
    print(f"\nProcessing project in: {dir_path} -> repo: {repo_name}")
    
    # 1. Initialize Git if not exists
    git_dir = os.path.join(dir_path, ".git")
    if not os.path.exists(git_dir):
        print("Initializing Git repository...")
        if not run_git_command(["git", "init"], cwd=dir_path):
            return False
        if not run_git_command(["git", "branch", "-M", "main"], cwd=dir_path):
            return False
            
    # 2. Setup standard .gitignore if none exists
    gitignore_path = os.path.join(dir_path, ".gitignore")
    if not os.path.exists(gitignore_path):
        print("Creating default .gitignore...")
        gitignore_content = """node_modules/
.DS_Store
*.log
dist/
build/
.env
.next/
out/
bin/
obj/
"""
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(gitignore_content)
            
    # 3. Add and commit files
    run_git_command(["git", "add", "-A"], cwd=dir_path)
    
    # Check if there is anything to commit
    status_result = subprocess.run(["git", "status", "--porcelain"], cwd=dir_path, stdout=subprocess.PIPE, text=True)
    if status_result.stdout.strip():
        print("Committing files...")
        run_git_command(["git", "commit", "-m", "initial commit"], cwd=dir_path)
    else:
        print("No changes to commit.")
        
    # 4. Create repository on GitHub
    if not create_github_repo(token, repo_name, is_private):
        return False
        
    # 5. Push code
    # Remove existing origin remote
    run_git_command(["git", "remote", "remove", "origin"], cwd=dir_path)
    
    # Add new authenticated origin remote
    remote_url = f"https://{token}@github.com/{username}/{repo_name}.git"
    if not run_git_command(["git", "remote", "add", "origin", remote_url], cwd=dir_path):
        return False
        
    print(f"Pushing to GitHub (https://github.com/{username}/{repo_name})...")
    if not run_git_command(["git", "push", "-u", "origin", "main", "--force"], cwd=dir_path):
        if not run_git_command(["git", "push", "-u", "origin", "main"], cwd=dir_path):
            return False
            
    print(f"Successfully published {repo_name} to GitHub!")
    return True

def main():
    parser = argparse.ArgumentParser(description="Publish projects from local directory to GitHub.")
    parser.add_argument("-p", "--project", type=str, help="Specific project folder name or zip file to publish.")
    parser.add_argument("-l", "--list", action="store_true", help="List all available projects and exit.")
    args = parser.parse_args()

    if not os.path.exists(PROJECTS_DIR):
        print(f"Error: Projects directory {PROJECTS_DIR} does not exist.")
        sys.exit(1)
        
    items = os.listdir(PROJECTS_DIR)
    # Filter out hidden files and non-project files/directories
    items = [i for i in items if not i.startswith(".") and (os.path.isdir(os.path.join(PROJECTS_DIR, i)) or i.endswith(".zip"))]
    
    if args.list:
        print(f"\nAvailable projects in {PROJECTS_DIR}:")
        for idx, item in enumerate(sorted(items), 1):
            print(f"  {idx}. {item}")
        sys.exit(0)
        
    if args.project:
        # Check if project exists or match by proper name
        target_path = os.path.join(PROJECTS_DIR, args.project)
        if not os.path.exists(target_path):
            normalized_target = make_proper_name(args.project)
            found = False
            for item in items:
                if make_proper_name(item) == normalized_target:
                    items = [item]
                    found = True
                    break
            if not found:
                print(f"Error: Project '{args.project}' not found in {PROJECTS_DIR}.")
                sys.exit(1)
        else:
            items = [args.project]

    if not TOKEN:
        print("Error: GITHUB_TOKEN environment variable not set.")
        sys.exit(1)
        
    username = get_github_username(TOKEN)
    if not username:
        print("Error: Could not retrieve GitHub username. Invalid token?")
        sys.exit(1)
        
    print(f"Authenticated as GitHub User: {username}")
    print(f"Source projects directory: {PROJECTS_DIR}")
    print(f"Create repositories as private: {PRIVATE_REPOS}")
            
    # Track paths of folders to process
    folders_to_process = []
    
    # First pass: Handle zips and renames
    for item in items:
        item_path = os.path.join(PROJECTS_DIR, item)
        repo_name = make_proper_name(item)
        target_dir = os.path.join(PROJECTS_DIR, repo_name)
        
        # Skip if it is excluded
        if repo_name in EXCLUDED_REPOS:
            print(f"Skipping excluded project/file: {item}")
            continue
            
        if item.endswith(".zip"):
            print(f"\nExtracting archive: {item}")
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    with zipfile.ZipFile(item_path, 'r') as zip_ref:
                        zip_ref.extractall(tmpdir)
                    
                    # Clean up nested folders inside zip if any
                    contents = os.listdir(tmpdir)
                    contents = [c for c in contents if not c.startswith(".")]
                    
                    if len(contents) == 1 and os.path.isdir(os.path.join(tmpdir, contents[0])):
                        src_dir = os.path.join(tmpdir, contents[0])
                    else:
                        src_dir = tmpdir
                        
                    os.makedirs(target_dir, exist_ok=True)
                    for file_name in os.listdir(src_dir):
                        shutil.move(os.path.join(src_dir, file_name), os.path.join(target_dir, file_name))
                        
                    folders_to_process.append((target_dir, repo_name))
                    print(f"Extracted to cleaned folder: {target_dir}")
                    
                    # Delete the zip file after successful extraction
                    os.remove(item_path)
                except Exception as e:
                    print(f"Error unzipping {item}: {e}")
                    
        elif os.path.isdir(item_path):
            if item_path != target_dir:
                # Rename the directory to proper name
                print(f"\nRenaming folder: {item} -> {repo_name}")
                try:
                    shutil.move(item_path, target_dir)
                    folders_to_process.append((target_dir, repo_name))
                except Exception as e:
                    print(f"Error renaming folder {item}: {e}")
            else:
                folders_to_process.append((target_dir, repo_name))
                
    # Second pass: Initialize Git, create repo, and push
    success_count = 0
    for dir_path, repo_name in folders_to_process:
        if process_and_push_project(dir_path, repo_name, username, TOKEN, PRIVATE_REPOS):
            success_count += 1
            
    print(f"\nAll done! Successfully published {success_count}/{len(folders_to_process)} projects.")

if __name__ == "__main__":
    main()
