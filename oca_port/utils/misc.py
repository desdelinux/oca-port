# Copyright 2022 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl)

import giturlparse
import json
import os
import re
from collections import defaultdict

MANIFEST_NAMES = ("__manifest__.py", "__openerp__.py")


# Copy-pasted from OCA/maintainer-tools
def get_manifest_path(addon_dir):
    for manifest_name in MANIFEST_NAMES:
        manifest_path = os.path.join(addon_dir, manifest_name)
        if os.path.isfile(manifest_path):
            return manifest_path


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[39m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ENDD = "\033[22m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def clean_text(text):
    """Clean text by removing patterns like '13.0', '[13.0]' or '[IMP]'."""
    return re.sub(r"\[.*\]|\d+\.\d+", "", text).strip()


def defaultdict_from_dict(d):
    nd = lambda: defaultdict(nd)  # noqa
    ni = nd()
    ni.update(d)
    return ni


class Output:
    """Mixin to handle the output of oca-port."""

    def _print(self, *args, **kwargs):
        """Like built-in 'print' method but check if oca-port is used in CLI."""
        app = self
        # FIXME: determine class
        if hasattr(self, "app"):
            app = self.app
        if app.cli and not app.output:
            print(*args, **kwargs)

    def _render_output(self, output, data):
        """Render the data with the expected format."""
        return getattr(self, f"_render_output_{output}")(data)

    def _render_output_json(self, data):
        """Render the data as JSON."""
        return json.dumps(data)


class SmartDict(dict):
    """Dotted notation dict."""

    def __getattr__(self, attrib):
        val = self.get(attrib)
        return self.__class__(val) if isinstance(val, dict) else val


REF_REGEX = r"((?P<remote>[\w-]+)/)?(?P<branch>.*)"


def parse_ref(ref):
    """Parse reference in the form '[remote/]branch'."""
    group = re.match(REF_REGEX, ref)
    return SmartDict(group.groupdict()) if group else None


def extract_ref_info(repo, kind, ref, remote=None):
    """Extract info from `ref`.

    >>> extract_ref_info(repo, "source", "origin/16.0")
    {'remote': 'origin', 'repo': 'server-tools', 'platform': 'github', 'branch': '16.0', 'kind': 'src', 'org': 'OCA'}
    """
    info = parse_ref(ref)
    if not info:
        raise ValueError(f"No valid {kind}")
    info["ref"] = ref
    info["kind"] = kind
    info["remote"] = info["remote"] or remote
    info.update({"org": None, "repo_full_name": None, "platform": None, "repo_name": None})
    if info["remote"]:
        remote_url = repo.remotes[info["remote"]].url
        p = giturlparse.parse(remote_url)
        if p.valid:
            info["repo_name"] = p.name
            info["platform"] = p.platform
            info["org"] = p.owner
            if p.owner and p.name:
                info["repo_full_name"] = f"{p.owner}/{p.name}"
            elif p.name: # Handles cases like local paths that are git repos but no owner
                info["repo_full_name"] = p.name

    else:
        # Fallback on 'origin' to grab info like platform, and repository name
        if "origin" in repo.remotes:
            remote_url = repo.remotes["origin"].url
            p = giturlparse.parse(remote_url)
            if p.valid:
                info["repo_name"] = p.name
                info["platform"] = p.platform
                info["org"] = p.owner
                if p.owner and p.name:
                    info["repo_full_name"] = f"{p.owner}/{p.name}"
                elif p.name:
                    info["repo_full_name"] = p.name
    return info


def pr_ref_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = giturlparse.parse(url)
        if not p.valid:
            return ""

        owner = p.owner
        repo_name = p.name  # For GitLab, this is just the project name, owner might contain group/subgroup

        if p.platform == "github":
            # URL: https://github.com/OCA/edi/pull/371
            # p.owner = OCA, p.name = edi
            # Need to extract PR number from the path
            match = re.search(r"/pull/(\d+)", p.pathname)
            if match:
                pr_number = match.group(1)
                return f"{owner}/{repo_name}#{pr_number}"
        elif p.platform == "gitlab":
            # URL: https://gitlab.com/group/project/-/merge_requests/123
            # URL: https://gitlab.com/group/subgroup/project/-/merge_requests/123
            # p.owner = group or group/subgroup, p.name = project
            # Need to extract MR IID from the path
            match = re.search(r/-/merge_requests/(\d+)", p.pathname)
            if match:
                mr_iid = match.group(1)
                # For GitLab, repo_full_name is owner/name
                repo_full_name = f"{owner}/{repo_name}" if owner else repo_name
                return f"{repo_full_name}!{mr_iid}"
    except Exception: # Broad exception to catch any parsing errors
        return "" # Or raise a custom error / log
    return ""
