from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GOOGLE_SCOPES: Sequence[str] = (
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students",
    "https://www.googleapis.com/auth/drive.file",
)


# ---------------------------------------------------------------------------
# Token data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OAuthTokenBundle:
    provider: str
    access_token: str
    refresh_token: str
    expires_at: datetime


@dataclass(frozen=True)
class EncryptedOAuthTokenBundle:
    provider: str
    access_token_enc: bytes
    refresh_token_enc: bytes
    expires_at: datetime


# ---------------------------------------------------------------------------
# Fernet cipher for token storage
# ---------------------------------------------------------------------------

class TokenCipher:
    def __init__(self, key: str | bytes) -> None:
        self.fernet = Fernet(key)

    def encrypt_bundle(self, bundle: OAuthTokenBundle) -> EncryptedOAuthTokenBundle:
        return EncryptedOAuthTokenBundle(
            provider=bundle.provider,
            access_token_enc=self.fernet.encrypt(bundle.access_token.encode("utf-8")),
            refresh_token_enc=self.fernet.encrypt(bundle.refresh_token.encode("utf-8")),
            expires_at=bundle.expires_at.astimezone(timezone.utc),
        )

    def decrypt_bundle(self, bundle: EncryptedOAuthTokenBundle) -> OAuthTokenBundle:
        return OAuthTokenBundle(
            provider=bundle.provider,
            access_token=self.fernet.decrypt(bundle.access_token_enc).decode("utf-8"),
            refresh_token=self.fernet.decrypt(bundle.refresh_token_enc).decode("utf-8"),
            expires_at=bundle.expires_at.astimezone(timezone.utc),
        )


# ---------------------------------------------------------------------------
# OAuth flow helpers
# ---------------------------------------------------------------------------

class GoogleOAuthFlow:
    """Wraps google-auth-oauthlib Flow for the web server OAuth 2.0 flow."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }
        self.redirect_uri = redirect_uri

    def authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """Return the URL the user should be redirected to, and the code verifier."""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=list(GOOGLE_SCOPES),
            redirect_uri=self.redirect_uri,
        )
        url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state or "",
        )
        return url, flow.code_verifier

    def exchange_code(self, code: str, code_verifier: str | None = None) -> OAuthTokenBundle:
        """Exchange an authorization code for an OAuthTokenBundle."""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=list(GOOGLE_SCOPES),
            redirect_uri=self.redirect_uri,
        )
        if code_verifier:
            flow.code_verifier = code_verifier
        flow.fetch_token(code=code)
        creds: Credentials = flow.credentials
        expires_at = creds.expiry or datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return OAuthTokenBundle(
            provider="google",
            access_token=creds.token or "",
            refresh_token=creds.refresh_token or "",
            expires_at=expires_at,
        )


# ---------------------------------------------------------------------------
# Credential builder (used by monitor + submission service)
# ---------------------------------------------------------------------------

def build_credentials(bundle: OAuthTokenBundle, client_id: str, client_secret: str) -> Credentials:
    """Build a google.oauth2.credentials.Credentials object from a stored bundle.

    Refreshes the access token automatically if it has expired.
    """
    creds = Credentials(
        token=bundle.access_token,
        refresh_token=bundle.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(GOOGLE_SCOPES),
    )
    if not creds.valid:
        try:
            creds.refresh(Request())
            logger.info("Refreshed Google OAuth access token.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Token refresh failed: %s", exc)
            raise
    return creds


def build_classroom_service(creds: Credentials):
    return build("classroom", "v1", credentials=creds)


def build_drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)
