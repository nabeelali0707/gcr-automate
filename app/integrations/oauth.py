from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.fernet import Fernet


GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students",
    "https://www.googleapis.com/auth/drive.file",
)


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
