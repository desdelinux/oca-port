# Copyright Odoo Community Association (OCA)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import os
import re
import requests
import urllib.parse
from typing import Optional, List, Dict, Any

from .git import PullRequest
from .vcs import VersionControlService

GITLAB_API_VERSION = "v4"

class GitLab(VersionControlService):
    def __init__(self, token: Optional[str] = None, gitlab_url: Optional[str] = None):
        self.gitlab_url = gitlab_url or os.environ.get("GITLAB_URL", "https://gitlab.com")
        self.api_url = f"{self.gitlab_url}/api/{GITLAB_API_VERSION}"
        self.token = token or self.get_token()

    def get_token(self) -> Optional[str]:
        token = os.environ.get("GITLAB_TOKEN")
        return token

    def request(
        self,
        endpoint: str,
        method: str = "get",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        check_errors: bool = True,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token

        url = f"{self.api_url}/{endpoint.lstrip('/')}"

        response = requests.request(
            method=method.lower(), url=url, headers=headers, params=params, json=json_data
        )
        if check_errors:
            response.raise_for_status()
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            return response

    def get_original_request(
        self, repo_full_name: str, branch: str, commit_sha: str
    ) -> Optional[PullRequest]:
        project_id = urllib.parse.quote_plus(repo_full_name)
        try:
            mrs_data = self.request(f"projects/{project_id}/repository/commits/{commit_sha}/merge_requests")
        except RuntimeError as e:
            if isinstance(e.__cause__, requests.exceptions.HTTPError) and e.__cause__.response.status_code == 404:
                return None
            return None

        if not isinstance(mrs_data, list): return None

        for mr_data in mrs_data:
            if not isinstance(mr_data, dict): continue
            if mr_data.get("target_branch") == branch and mr_data.get("state") in ["merged", "closed", "locked"]:
                return PullRequest(
                    number=mr_data["iid"],
                    url=mr_data["web_url"],
                    author=mr_data.get("author", {}).get("username", "N/A"),
                    title=mr_data["title"],
                    body=mr_data.get("description", ""),
                    merged_at=mr_data.get("merged_at"),
                )
        return None

    def get_request_commits(self, repo_full_name: str, request_id: int) -> List[str]:
        project_id = urllib.parse.quote_plus(repo_full_name)
        try:
            commits_data = self.request(f"projects/{project_id}/merge_requests/{request_id}/commits")
        except RuntimeError:
            return []

        if not isinstance(commits_data, list): return []
        return [commit["id"] for commit in commits_data if isinstance(commit, dict) and "id" in commit]

    def search_migration_requests(
        self, repo_full_name: str, branch: str, addon: str
    ) -> Optional[PullRequest]:
        project_id = urllib.parse.quote_plus(repo_full_name)
        params = {
            "state": "opened", "target_branch": branch,
            "search": f"mig {addon}", "in": "title", "scope": "all",
        }
        try:
            mrs_data = self.request(f"projects/{project_id}/merge_requests", params=params)
        except RuntimeError:
            return None

        if not isinstance(mrs_data, list): return None

        for mr_data in mrs_data:
            if not isinstance(mr_data, dict): continue
            title = mr_data.get("title", "")
            if self._addon_in_text(addon, title):
                return PullRequest(
                    number=mr_data["iid"], url=mr_data["web_url"],
                    author=mr_data.get("author", {}).get("username", "N/A"),
                    title=title, body=mr_data.get("description", ""),
                    merged_at=mr_data.get("merged_at"),
                )
        return None

    def _addon_in_text(self, addon: str, text: str) -> bool:
        if not text: return False
        return any(addon == term for term in re.split(r'\W+', text))

    def create_request(self, repo_full_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        project_id = urllib.parse.quote_plus(repo_full_name)
        try:
            response_json = self.request(f"projects/{project_id}/merge_requests", method="post", json_data=data)
            if not isinstance(response_json, dict):
                raise RuntimeError(f"Unexpected response type from GitLab API: {type(response_json)}")
            return response_json
        except RuntimeError:
            raise

    def get_pr_or_mr_url(
        self,
        owner_or_group: str, # For GitLab, this is the top-level group/user
        repo_or_project: str, # This is the project path, possibly including subgroups: group/subgroup/project
        target_branch: str,
        head_branch_owner_or_group: str, # Often same as owner_or_group for non-fork MRs
        head_branch: str,
        title: str,
        body: str # Body prefill is limited for GitLab via URL
    ) -> str:
        # repo_or_project is the full path like 'group/subgroup/project'
        # The head_branch_owner_or_group is not typically part of the simple "new MR" URL structure
        # unless dealing with forks explicitly by source_project_id, which is more complex.
        # This URL assumes MR within the same project.
        encoded_title = urllib.parse.quote_plus(title)
        # The 'repo_full_name' for GitLab includes the group and project.
        # So, self.gitlab_url + / + repo_or_project (as group/project) + /-/merge_requests/new
        return (
            f"{self.gitlab_url.rstrip('/')}/{repo_or_project.lstrip('/')}/-/merge_requests/new"
            f"?merge_request[source_branch]={urllib.parse.quote_plus(head_branch)}"
            f"&merge_request[target_branch]={urllib.parse.quote_plus(target_branch)}"
            f"&merge_request[title]={encoded_title}"
        )
