# Copyright Odoo Community Association (OCA)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import abc
from typing import Optional, List, Dict, Any
from .git import PullRequest # Assuming PullRequest is generic enough

class VersionControlService(abc.ABC):
    @abc.abstractmethod
    def get_token(self) -> Optional[str]:
        '''Returns the token used for authentication.'''
        pass

    @abc.abstractmethod
    def get_original_request(
        self, repo_full_name: str, branch: str, commit_sha: str
    ) -> Optional[PullRequest]:
        '''
        Retrieves the original Pull/Merge Request associated with a commit.
        repo_full_name is like 'org/repo' for GitHub or 'group/project' for GitLab.
        '''
        pass

    @abc.abstractmethod
    def get_request_commits(
        self, repo_full_name: str, request_id: int # request_id is PR number or MR IID
    ) -> List[str]:
        '''
        Fetches all commit SHAs for a given Pull/Merge Request.
        '''
        pass

    @abc.abstractmethod
    def search_migration_requests(
        self, repo_full_name: str, target_branch: str, addon_name: str
    ) -> Optional[PullRequest]:
        '''
        Searches for existing migration Pull/Merge Requests.
        '''
        pass

    @abc.abstractmethod
    def create_request(
        self, repo_full_name: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        '''
        Creates a new Pull/Merge Request.
        'data' contains necessary information like title, body, source/target branches.
        Returns a dictionary representing the created request (e.g., from API response).
        '''
        pass

    @abc.abstractmethod
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
        '''
        Generates a URL to manually create a new Pull/Merge Request
        with pre-filled information.
        '''
        pass

    @abc.abstractmethod
    def request(
        self,
        endpoint: str,
        method: str = "get",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None, # Changed from 'json' to avoid conflict with requests library's json param
        check_errors: bool = True,
    ) -> Any:
        '''Generic method to make an API request to the VCS.'''
        pass
