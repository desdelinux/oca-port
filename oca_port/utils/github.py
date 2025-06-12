# Copyright 2022 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import re
import os
import subprocess
import requests
import urllib.parse

from .git import PullRequest
from .vcs import VersionControlService

GITHUB_API_URL = "https://api.github.com"


class GitHub(VersionControlService):
    def __init__(self, token=None):
        self.token = token or self.get_token()

    def request(self, endpoint: str, method: str = "get", params=None, json_data=None, check_errors: bool = True):
        headers = {"Accept": "application/vnd.github.groot-preview+json"}
        if self.token:
            headers.update({"Authorization": f"token {self.token}"})

        full_url = f"{GITHUB_API_URL}/{endpoint.lstrip('/')}"

        kwargs = {"headers": headers}
        if json_data:
            kwargs.update(json=json_data)
        if params:
            kwargs.update(params=params)

        response = getattr(requests, method)(full_url, **kwargs)
        if check_errors and not response.ok:
            raise RuntimeError(response.text)
        # Assuming it always returns JSON, or adjust as per original. If not, handle response.content
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError: # Handle cases where response is not JSON
            return response # Or response.text, or raise an error

    def get_original_request(
        self, repo_full_name: str, branch: str, commit_sha: str
    ) -> Optional[PullRequest]:
        try:
            gh_commit_pulls = self.request(
                f"repos/{repo_full_name}/commits/{commit_sha}/pulls"
            )
        except RuntimeError:
            return None

        if not isinstance(gh_commit_pulls, list):
            return None

        for data in gh_commit_pulls:
            if not isinstance(data, dict) or not data.get("base"):
                continue
            if (
                data["base"]["ref"] == branch
                and data["base"]["repo"]["full_name"] == repo_full_name
            ):
                return PullRequest(
                    number=data["number"],
                    url=data["html_url"],
                    author=data["user"]["login"] if data.get("user") else "N/A",
                    title=data["title"],
                    body=data["body"],
                    merged_at=data.get("merged_at"),
                )
        return None

    def get_request_commits(self, repo_full_name: str, request_id: int) -> List[str]:
        try:
            commits_data = self.request(
                f"repos/{repo_full_name}/pulls/{request_id}/commits?per_page=100"
            )
        except RuntimeError:
            return []

        if not isinstance(commits_data, list):
            return []
        return [commit["sha"] for commit in commits_data if isinstance(commit, dict) and "sha" in commit]


    def search_migration_requests(
        self, repo_full_name: str, branch: str, addon: str
    ) -> Optional[PullRequest]:
        for pr_state in ("open",):
            query = f"is:pr is:{pr_state} repo:{repo_full_name} base:{branch} in:title mig {addon}"
            try:
                prs = self.request(
                    "search/issues", params={"q": query}
                )
            except RuntimeError:
                continue

            if not isinstance(prs, dict) or "items" not in prs or not isinstance(prs["items"], list):
                continue

            for pr_data in prs.get("items", []):
                if not isinstance(pr_data, dict): continue
                if self._addon_in_text(addon, pr_data.get("title","")):
                    return PullRequest(
                        number=pr_data["number"],
                        url=pr_data["html_url"],
                        author=pr_data.get("user",{}).get("login", "N/A"),
                        title=pr_data["title"],
                        body=pr_data.get("body",""),
                    )
        return None

    def create_request(self, repo_full_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response_json = self.request(
                f"repos/{repo_full_name}/pulls",
                method="post",
                json_data=data,
            )
            if not isinstance(response_json, dict):
                 raise RuntimeError(f"Unexpected response type from GitHub API: {type(response_json)}")
            return response_json
        except RuntimeError:
            raise

    def get_pr_or_mr_url(
        self,
        owner_or_group: str,
        repo_or_project: str,
        target_branch: str,
        head_branch_owner_or_group: str,
        head_branch: str,
        title: str,
        body: str
    ) -> str:
        encoded_title = urllib.parse.quote_plus(title)
        encoded_body = urllib.parse.quote_plus(body)
        return (
            f"https://github.com/{owner_or_group}/{repo_or_project}/compare/"
            f"{target_branch}...{head_branch_owner_or_group}:{head_branch}"
            f"?expand=1&title={encoded_title}&body={encoded_body}"
        )

    def _addon_in_text(self, addon: str, text: str):
        if not text: return False
        return any(addon == term for term in re.split(r'\W+', text))

    def get_token(self) -> Optional[str]:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            try:
                token = subprocess.check_output(
                    ["gh", "auth", "token"], text=True
                ).strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        return token
