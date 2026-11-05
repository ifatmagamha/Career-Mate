"""Who is calling: verify the Supabase access token sent as `Authorization: Bearer <jwt>`.

Supabase signs its tokens; we only check the signature and claims, no call to Supabase per request
(the public keys are fetched once from the project's JWKS endpoint and cached).
Without SUPABASE_URL (local development) every request is one fixed dev user.
"""
from functools import lru_cache
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config.settings import settings
from src.llm import port

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


def check_config() -> None:
    """Refuse to start a production server that would let anyone in as the dev user."""
    if settings.APP_ENV == "production" and not settings.SUPABASE_URL:
        raise RuntimeError("APP_ENV=production requires SUPABASE_URL (auth). Refusing to start without login.")


@lru_cache(maxsize=4)
def _jwks(supabase_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def verify(token: str, *, supabase_url: str, jwt_secret: str = "") -> str:
    """The user id (`sub`) of a valid access token; raises jwt.PyJWTError otherwise."""
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256":  # legacy projects: one shared secret
        if not jwt_secret:
            raise jwt.InvalidAlgorithmError("HS256 token but SUPABASE_JWT_SECRET is not set")
        key, algorithms = jwt_secret, ["HS256"]
    else:  # current projects: asymmetric signing keys, public half published as JWKS
        key, algorithms = _jwks(supabase_url).get_signing_key_from_jwt(token).key, ["ES256", "RS256"]
    claims = jwt.decode(token, key, algorithms=algorithms, audience="authenticated",
                        issuer=f"{supabase_url}/auth/v1", options={"require": ["exp", "sub"]})
    return claims["sub"]


_bearer = HTTPBearer(auto_error=False)


async def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> str:
    """FastAPI dependency: the caller's user id, or 401. Async so the id it sets is seen by the endpoint."""
    if not settings.SUPABASE_URL:
        user_id = DEV_USER_ID
    else:
        if not creds:
            raise HTTPException(status_code=401, detail="Not signed in", headers={"WWW-Authenticate": "Bearer"})
        try:  # the first JWKS fetch is a network call: keep it off the event loop
            user_id = await run_in_threadpool(verify, creds.credentials, supabase_url=settings.SUPABASE_URL,
                                              jwt_secret=settings.SUPABASE_JWT_SECRET)
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired session", headers={"WWW-Authenticate": "Bearer"})
    port.current_user.set(user_id)  # llm_calls rows record who triggered them
    return user_id


if __name__ == "__main__":
    import time
    from cryptography.hazmat.primitives.asymmetric import ec

    URL, SECRET, SUB = "https://abc.supabase.co", "s" * 40, "5f0c6a1e-0000-4000-8000-000000000001"
    good = {"sub": SUB, "aud": "authenticated", "iss": f"{URL}/auth/v1", "exp": int(time.time()) + 60}

    def rejected(token, **kw):
        try:
            verify(token, supabase_url=URL, **kw)
        except jwt.PyJWTError:
            return True
        return False

    # legacy HS256
    assert verify(jwt.encode(good, SECRET, "HS256"), supabase_url=URL, jwt_secret=SECRET) == SUB
    assert rejected(jwt.encode(good, SECRET, "HS256"))                                    # no secret configured
    assert rejected(jwt.encode(good, "x" * 40, "HS256"), jwt_secret=SECRET)               # wrong signature
    assert rejected(jwt.encode({**good, "exp": int(time.time()) - 5}, SECRET, "HS256"), jwt_secret=SECRET)  # expired
    assert rejected(jwt.encode({**good, "aud": "anon"}, SECRET, "HS256"), jwt_secret=SECRET)                # wrong audience
    assert rejected(jwt.encode({**good, "iss": "https://evil.supabase.co/auth/v1"}, SECRET, "HS256"), jwt_secret=SECRET)
    assert rejected(jwt.encode(good, None, "none"), jwt_secret=SECRET)                    # unsigned token

    # asymmetric (ES256) via JWKS: the public key comes from the (here faked) JWKS endpoint
    private = ec.generate_private_key(ec.SECP256R1())
    other = ec.generate_private_key(ec.SECP256R1())

    class FakeJWKS:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": private.public_key()})()

    _jwks.cache_clear()
    real, _jwks = _jwks, lambda url: FakeJWKS()  # noqa: F811
    assert verify(jwt.encode(good, private, "ES256"), supabase_url=URL) == SUB
    assert rejected(jwt.encode(good, other, "ES256"))                                     # signed by someone else
    # algorithm confusion: an HS256 token "signed" with public material is not accepted without the secret
    assert rejected(jwt.encode(good, "public-key-bytes" * 3, "HS256"))
    _jwks = real
    print("auth ok")
