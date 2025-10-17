from github import Auth, Github
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

token = os.getenv("GITHUB_TOKEN")
username = os.getenv("GITHUB_USERNAME")

auth = Auth.Token(token)
g = Github(auth=auth)

user = g.get_user()
repo_name = "captcha-solver-demo"

repo = user.create_repo(
    repo_name,
    private=False,
    description="Demo app for LLM deployment"
)

print(f"✅ Repository created successfully: {repo.html_url}")