import os
import re
import subprocess
import urllib.parse

import requests

from .git import PullRequest

GITLAB_API_URL = "https://gitlab.com/api/v4"


class GitLab:
    def __init__(self, token=None):
        if not token:
            token = self._get_token()
        self.token = token

    def request(self, url: str, method: str = "get", params=None, json=None):
        """Request GitLab API."""
        headers = {}
        if self.token:
            headers["Private-Token"] = self.token
        full_url = "/".join([GITLAB_API_URL, url])
        response = getattr(requests, method)(
            full_url, headers=headers, params=params, json=json
        )
        if not response.ok:
            raise RuntimeError(response.text)
        return response.json()

    def get_original_pr(
        self, from_org: str, repo_name: str, branch: str, commit_sha: str
    ):
        """Return original GitLab MR data of a commit."""
        project = urllib.parse.quote(f"{from_org}/{repo_name}", safe="")
        mrs = self.request(
            f"projects/{project}/repository/commits/{commit_sha}/merge_requests"
        )
        for mr in mrs:
            if mr.get("target_branch") == branch:
                return mr
        return {}

    def search_migration_pr(
        self, from_org: str, repo_name: str, branch: str, addon: str
    ):
        """Return an existing migration MR (if any) of `addon` for `branch`."""
        project = urllib.parse.quote(f"{from_org}/{repo_name}", safe="")
        for state in ("opened", "merged"):
            mrs = self.request(
                f"projects/{project}/merge_requests",
                params={
                    "state": state,
                    "target_branch": branch,
                    "search": addon,
                    "in": "title",
                },
            )
            for mr in mrs:
                if self._addon_in_text(addon, mr["title"]):
                    return PullRequest(
                        number=mr["iid"],
                        url=mr["web_url"],
                        author=mr.get("author", {}).get("username", ""),
                        title=mr["title"],
                        body=mr.get("description", ""),
                    )

    def _addon_in_text(self, addon: str, text: str):
        """Return ``True`` if ``addon`` is present in ``text``."""
        return any(addon == term for term in re.split(r"\W+", text))

    @staticmethod
    def _get_token():
        token = os.environ.get("GITLAB_TOKEN")
        if not token:
            try:
                token = subprocess.check_output(
                    ["glab", "auth", "token"], text=True
                ).strip()
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        return token
