"""Thin GitHub REST client built on httpx.

Wraps the handful of endpoints the reviewer needs: listing PR files, reading
raw file contents for context, and posting reviews / comments. Authentication
is a bearer token, which may be a personal access token (Action / manual runs)
or an installation access token (GitHub App).
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

GITHUB_API = "https://api.github.com"


class GitHubError(RuntimeError):
    """Raised when the GitHub API returns an error response."""


class GitHubClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = GITHUB_API,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._client = client or httpx.Client(timeout=timeout)

    # -- low level --------------------------------------------------------
    def _headers(self, accept: str = "application/vnd.github+json") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-github-reviewer",
        }

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        accept = kwargs.pop("accept", "application/vnd.github+json")
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        resp = self._client.request(method, url, headers=self._headers(accept), **kwargs)
        if resp.status_code >= 400:
            raise GitHubError(
                f"{method} {url} -> {resp.status_code}: {resp.text[:500]}"
            )
        return resp

    # -- pull requests ----------------------------------------------------
    def get_pull(self, owner: str, repo: str, number: int) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}").json()

    def list_pull_files(self, owner: str, repo: str, number: int) -> list[dict]:
        """Return all changed files for a PR, following pagination."""
        files: list[dict] = []
        page = 1
        while True:
            resp = self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            batch = resp.json()
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return files

    def get_file_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str | None:
        """Return the raw text of a file at a ref, or None if unavailable."""
        try:
            resp = self._request(
                "GET",
                f"/repos/{owner}/{repo}/contents/{path}",
                params={"ref": ref},
                accept="application/vnd.github.raw",
            )
        except GitHubError:
            return None
        return resp.text

    # -- reviews / comments ----------------------------------------------
    def create_review(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        body: str,
        event: str,
        comments: list[dict] | None = None,
        commit_id: str | None = None,
    ) -> dict:
        """Create a PR review with an optional set of inline comments.

        `event` is one of APPROVE, REQUEST_CHANGES, COMMENT. `comments` are
        inline-comment payloads (path/line/side/body or path/position/body).
        """
        payload: dict[str, Any] = {"body": body, "event": event}
        if comments:
            payload["comments"] = comments
        if commit_id:
            payload["commit_id"] = commit_id
        return self._request(
            "POST", f"/repos/{owner}/{repo}/pulls/{number}/reviews", json=payload
        ).json()

    def create_issue_comment(
        self, owner: str, repo: str, number: int, body: str
    ) -> dict:
        return self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            json={"body": body},
        ).json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
