# p1/student/main.py
import os
import json
import time
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from github import Auth, Github, GithubException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fetch credentials
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USER = os.getenv("GITHUB_USERNAME")

if not GITHUB_TOKEN or not GITHUB_USER:
    raise RuntimeError("Please set GITHUB_TOKEN and GITHUB_USERNAME in .env")

# Authenticate with GitHub using PyGithub
auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)

# Initialize FastAPI
app = FastAPI()


# 🔔 Step 7: Notify evaluator API (with retry logic)
def notify_evaluator(task_data, repo_url, commit_sha, pages_url):
    body = {
        "email": task_data["email"],
        "task": task_data["task"],
        "round": task_data["round"],
        "nonce": task_data["nonce"],
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url,
    }

    for delay in [1, 2, 4, 8, 16]:  # Step 8 retry logic
        try:
            r = requests.post(task_data["evaluation_url"], json=body)
            if r.status_code == 200:
                print(f"✅ Pinged evaluator successfully: {r.status_code}")
                break
            else:
                print(f"⚠️ Evaluator ping failed ({r.status_code}), retrying in {delay}s...")
        except Exception as e:
            print(f"❌ Error pinging evaluator: {e}")
        time.sleep(delay)


# 🧱 Step 1: Create repo and push files (Round 1)
def create_repo_and_push_files(task_data: dict) -> dict:
    repo_name = task_data.get("task", "demo-app").strip()
    repo_full_name = f"{GITHUB_USER}/{repo_name}"
    brief = task_data.get("brief", f"Demo app for {repo_name}")

    user = gh.get_user()
    repo = None
    try:
        repo = user.get_repo(repo_name)
    except GithubException:
        repo = user.create_repo(
            name=repo_name,
            private=False,
            description=brief,
            auto_init=False
        )

    files = {
        "index.html": f"<html><body><h1>{brief}</h1></body></html>",
        "README.md": f"# {repo_name}\n\n{brief}\n",
        "LICENSE": "MIT License\n\nCopyright (c) 2025"
    }

    for path, content in files.items():
        try:
            existing = repo.get_contents(path)
            repo.update_file(
                path,
                f"Update {path}",
                content,
                existing.sha,
                branch="main"
            )
        except GithubException:
            repo.create_file(
                path,
                f"Add {path}",
                content,
                branch="main"
            )

    pages_url = f"https://{GITHUB_USER}.github.io/{repo_name}/"
    try:
        repo.create_pages_site(source="main")
    except Exception:
        pass  # fallback; Pages may already be active

    return {"repo_url": repo.html_url, "pages_url": pages_url}


# 🔁 Step 9: Handle round 2+ updates
def pull_and_update_repo(task_data: dict) -> dict:
    repo_name = task_data.get("task", "demo-app").strip()
    brief = task_data.get("brief", f"Updated brief for {repo_name}")
    user = gh.get_user()
    repo = user.get_repo(repo_name)

    updated_files = {
        "index.html": f"<html><body><h1>{brief}</h1><p>Updated for round {task_data['round']}</p></body></html>",
        "README.md": f"# {repo_name}\n\nUpdated Brief: {brief}\n"
    }

    for path, content in updated_files.items():
        try:
            existing = repo.get_contents(path)
            repo.update_file(
                path,
                f"Round {task_data['round']} update {path}",
                content,
                existing.sha,
                branch="main"
            )
        except Exception as e:
            print(f"⚠️ Could not update {path}: {e}")

    pages_url = f"https://{GITHUB_USER}.github.io/{repo_name}/"
    return {"repo_url": repo.html_url, "pages_url": pages_url}


# 🚀 Main endpoint for handling both build + update tasks
@app.post("/build-app")
async def build_app(request: Request):
    task_data = await request.json()

    if "task" not in task_data:
        return JSONResponse({"detail": "missing task field"}, status_code=400)

    round_num = int(task_data.get("round", 1))

    try:
        if round_num == 1:
            result = create_repo_and_push_files(task_data)
        else:
            result = pull_and_update_repo(task_data)

        repo_name = task_data["task"]
        repo = gh.get_user().get_repo(repo_name)
        commit_sha = repo.get_commits()[0].sha

        notify_evaluator(
            task_data,
            repo_url=result["repo_url"],
            commit_sha=commit_sha,
            pages_url=result["pages_url"]
        )

        response_data = {
            "message": "Task accepted",
            "round": round_num,
            "repo_url": result["repo_url"],
            "pages_url": result["pages_url"],
        }
        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        print("❌ Error during build/update:", e)
        return JSONResponse({"message": "Failed to deploy", "error": str(e)}, status_code=500)


@app.get("/")
def read_root():
    return {"message": "Captcha Solver API running successfully!"}
