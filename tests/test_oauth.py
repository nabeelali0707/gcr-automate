from datetime import datetime, timezone

from cryptography.fernet import Fernet

from app.integrations.oauth import OAuthTokenBundle, TokenCipher


def test_token_cipher_round_trip() -> None:
    cipher = TokenCipher(Fernet.generate_key())
    bundle = OAuthTokenBundle(
        provider="google",
        access_token="access-secret",
        refresh_token="refresh-secret",
        expires_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )

    encrypted = cipher.encrypt_bundle(bundle)
    decrypted = cipher.decrypt_bundle(encrypted)

    assert encrypted.access_token_enc != b"access-secret"
    assert decrypted == bundle
