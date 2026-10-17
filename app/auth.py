"""Password hashing (stdlib scrypt) and the signed-cookie session helpers."""
import base64
import hashlib
import hmac
import os

from fastapi import HTTPException, Request

from . import db


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
    except ValueError:
        return False
    salt = base64.b64decode(salt_b64)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


def current_user(request: Request):
    uid = request.session.get("uid")
    return db.one("SELECT id, email, name, role, org FROM users WHERE id = ?", uid) if uid else None


class LoginRequired(Exception):
    pass


def require(request: Request, role: str | None = None):
    user = current_user(request)
    if not user:
        raise LoginRequired()
    if role and user["role"] != role:
        raise HTTPException(403, "This page is for " + role + "s.")
    return user
