import json
import os
import re

from flask import Flask, request
from github import Github, GithubIntegration, GithubException

ORGANISATION = "leslie-alldridge"
SOURCE_BRANCH = "main"
SUBSCRIPTIONS_FILE = "subscriptions.json"

app = Flask(__name__)
app_id = os.environ["APP_ID"]

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


def add_subscriptions(file):
    """
    Load subscriptions from JSON file
    """
    f = open(file)
    loaded_content = json.loads(f.read())
    f.close()
    return loaded_content


def commit_changes(repo_instance, current_version, new_version, string_content, page, module_name):
    """
    Commit module bump changes to a versioned branch. Therefore, it's possible to have
    multiple open PRs at any given time.
    """
    versioned_branch_name = f"{module_name}-{new_version}"
    print(
        f"Replacing current version - {current_version} with desired version - {new_version}")
    new_content = string_content.replace(
        current_version[0], new_version)

    print(f"New file content: {new_content}")
    contents = repo_instance.get_contents(page.path, ref=SOURCE_BRANCH)

    # Get source branch
    sb = repo_instance.get_branch(SOURCE_BRANCH)
    # Checkout new branch from source
    repo_instance.create_git_ref(
        ref=f'refs/heads/{versioned_branch_name}', sha=sb.commit.sha)

    repo_instance.update_file(contents.path, f"Bump {module_name} to {new_version}",
                              new_content, contents.sha, branch=versioned_branch_name)

    return versioned_branch_name


def create_git_connection(repo):
    """
    Obtain OAuth Token for specific repository
    """
    return Github(
        login_or_token=git_integration.get_access_token(
            git_integration.get_installation(
                ORGANISATION, repo).id
        ).token
    )


def get_module_version_from_code(page, module_name):
    """
    Decode page content and return current module version saved in code
    """
    # Convert file contents from bytes to normal string
    byte_string = page.decoded_content
    string_content = byte_string.decode("utf-8")

    # Find current version using regex
    return re.findall(
        fr'{module_name}.git\?ref=(v[\d.]+)',
        string_content
    ), string_content


def get_repo_instance(repo):
    """
    Retrieve repository instance using PyGitHub
    """
    git_connection = create_git_connection(repo)

    return git_connection.get_repo(f"{ORGANISATION}/{repo}")


def is_published_release_event(payload):
    """
    Ignore events if they aren't published releases
    """
    if payload['action'] != 'published' or 'release' not in payload:
        return False
    return True


@app.route("/", methods=['POST'])
def bot():
    # Get the event payload
    payload = request.json

    # Open subscriptions file and parse load JSON
    CONFIG = add_subscriptions(SUBSCRIPTIONS_FILE)
    print(f"Loaded config: {CONFIG}")

    # 1. Ignore any events not related to a GitHub released being published
    if not is_published_release_event(payload):
        return "ok"

    new_version = payload['release']['tag_name']  # e.g. v1.2.0
    module_name = payload['repository']['name']  # e.g. module.rds-cluster
    print(f"new_version: {new_version} module_name: {module_name}")

    # 2. Check if module is managed with automation
    if module_name not in CONFIG:
        print(f"{module_name} is not managed by this bot.")
        return "ok"

    module = CONFIG[module_name]

    # 3. Do any repositories consume this module?
    if 'repositories' not in module:
        print(f"No repositories are using module: {module_name}")
        return "ok"

    # 4. Loop over repos listed as consumers in subscriptions.json
    for repo in module["repositories"]:
        print(f"Processing update for {repo}")
        try:
            repo_instance = get_repo_instance(repo)
            git_connection = create_git_connection(repo)
        except GithubException as exc:
            print(exc)
            return "ok"

        # 5. Search for files in the repo calling our module
        search_query = f"git::https://github.com/week-2-notes repo:{ORGANISATION}/{repo}"
        print(f"Searching for module references with: {search_query}")

        for page in git_connection.search_code(search_query):
            current_version, string_content = get_module_version_from_code(
                page, module_name)

            # 6. Replace with desired release tag (version)
            if not current_version:
                print("No module call found, exiting...")
                return "ok"

            # 7. Commit changes to TARGET_BRANCH
            versioned_branch_name = commit_changes(repo_instance, current_version,
                                                   new_version, string_content, page, module_name)

            # 8. Create PR from versioned_branch_name to SOURCE_BRANCH (e.g. module.rds-cluster-v1.2.8)
            repo_instance.create_pull(
                title=f"Automation: Bump {module_name} to {new_version}", body="Bump managed by automation", head=versioned_branch_name, base=SOURCE_BRANCH)

    return "ok"


if __name__ == "__main__":
    app.run(debug=True, port=3000)
