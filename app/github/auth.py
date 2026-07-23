"""GitHub App authentication.

Builds a short-lived App JWT (RS256) from the App id + private key, then
exchanges it for an installation access token used to call the REST API on
behalf of a repository installation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
import jwt

GITHUB_API = "https://api.github.com"


def build_app_jwt(app_id: str, private_key_pem: str, *, now: int | None = None) -> str:
    """Create a signed App JWT valid for ~10 minutes.

    GitHub allows a maximum 10-minute expiry; we back-date `iat` by 60s to
    tolerate minor clock skew between us and GitHub.
    """
    issued = (now or int(time.time())) - 60
    payload = {
        "iat": issued,
        "exp": issued + 600,  # 10 minutes (GitHub's maximum)
        "iss": app_id,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


@dataclass
class InstallationToken:
    token: str
    expires_at: str | None = None


def get_installation_token(
    app_id: str,
    private_key_pem: str,
    installation_id: int,
    *,
    client: httpx.Client | None = None,
) -> InstallationToken:
    """Exchange an App JWT for an installation access token."""
    app_jwt = build_app_jwt(app_id, private_key_pem)
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"

    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        resp = client.post(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return InstallationToken(token=data["token"], expires_at=data.get("expires_at"))
    finally:
        if owns_client:
            client.close()
