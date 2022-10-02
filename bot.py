import os
import re

from flask import Flask, request
from github import Github, GithubIntegration


app = Flask(__name__)
app_id = os.environ["APP_ID"]

ORGANISATION = "leslie-alldridge"
SOURCE_BRANCH = "main"
TARGET_BRANCH = "bump-module-automation"

# Read the bot certificate
with open(
        os.path.normpath(os.path.expanduser('./releases.pem')),
        'r'
) as cert_file:
    app_key = cert_file.read()

# Create an GitHub integration instance
git_integration = GithubIntegration(
    app_id,
    app_key,
)

CONFIG = {
    "week-2-notes": {
        "repositories": ["test"]
    }
}


@app.route("/", methods=['POST'])
def bot():
    # Get the event payload
    payload = request.json

    # 1. Check if the event is a GitHub release published event
    if payload['action'] != 'published' or 'release' not in payload:
        return "ok"

    tag_name = payload['release']['tag_name']
    module_name = payload['repository']['name']

    print(f"tag_name: {tag_name} module_name: {module_name}")

    # 2. Check if module is managed with automation
    if module_name not in CONFIG:
        print(f"{module_name} is not managed by me.")
        return "ok"

    module = CONFIG[module_name]

    # Do any repositories consume this module
    if 'repositories' not in module:
        print(f"No repositories are using module: {module_name}")
        return "ok"

    for repo in module["repositories"]:
        print(f"Processing update for {repo}")

        git_connection = Github(
            login_or_token=git_integration.get_access_token(
                git_integration.get_installation(
                    ORGANISATION, repo).id
            ).token
        )

        repo = git_connection.get_repo(f"{ORGANISATION}/{repo}")
        print(repo)

        # Search for files in this repo calling our module
        search_query = f"git::https://github.com/week-2-notes repo:{ORGANISATION}/test"
        print(search_query)

        for page in git_connection.search_code(search_query):
            print(page)
            byte_string = page.decoded_content
            string_content = byte_string.decode("utf-8")

            # Find current version
            current_version = re.findall(
                r'week-2-notes.git\?ref=(v[\d.]+)', string_content)

            # Replace with desired release tag (version)
            if not current_version:
                print("No module call found, exiting...")

            new_content = string_content.replace(current_version[0], tag_name)

            print(new_content)

            contents = repo.get_contents(page.path, ref=SOURCE_BRANCH)

            # get source branch
            sb = repo.get_branch(SOURCE_BRANCH)
            # checkout new branch from source
            repo.create_git_ref(
                ref=f'refs/heads/{TARGET_BRANCH}', sha=sb.commit.sha)

            print(contents)

            repo.update_file(contents.path, "bump module",
                             new_content, contents.sha, branch=TARGET_BRANCH)

            # Create PR
            repo.create_pull(
                title=f"Bump {module_name} to {tag_name}", body="Bump managed by automation", head=TARGET_BRANCH, base=SOURCE_BRANCH)

    return "ok"


if __name__ == "__main__":
    app.run(debug=True, port=3000)
