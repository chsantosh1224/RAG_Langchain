"""Cognito JWT verification.

Cognito signs access tokens with its private key; we verify them with its public
keys (JWKS), which are fetched once and cached. No request ever goes to Cognito.
"""
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

REGION = os.getenv("COGNITO_REGION", "ap-southeast-2")
USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"

_jwks_client = PyJWKClient(f"{ISSUER}/.well-known/jwks.json", cache_keys=True)
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_token(token: str) -> dict:
    try:
        key = _jwks_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.PyJWTError as e:
        raise _unauthorized(f"Invalid token: {e}")

    # Access tokens carry client_id instead of aud, and must not be ID tokens.
    if claims.get("token_use") != "access":
        raise _unauthorized("Not an access token")
    if claims.get("client_id") != CLIENT_ID:
        raise _unauthorized("Token issued for a different app client")
    return claims


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Returns the Cognito user ID (sub), which identifies the user's conversations."""
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    return verify_token(credentials.credentials)["sub"]
