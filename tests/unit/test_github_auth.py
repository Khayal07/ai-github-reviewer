"""Unit tests for GitHub App JWT construction."""

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.github.auth import build_app_jwt


def _rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def test_build_app_jwt_has_expected_claims():
    private_pem, public_pem = _rsa_keypair()
    token = build_app_jwt("42", private_pem, now=1_700_000_000)

    # Fixed `now` puts exp in the past relative to wall clock; only check claims.
    decoded = jwt.decode(
        token, public_pem, algorithms=["RS256"], options={"verify_exp": False}
    )
    assert decoded["iss"] == "42"
    # iat back-dated by 60s, exp 10 minutes after iat.
    assert decoded["iat"] == 1_700_000_000 - 60
    assert decoded["exp"] - decoded["iat"] == 600
