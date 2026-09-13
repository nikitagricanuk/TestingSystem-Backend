from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Any, Callable, Optional, Dict
from uuid import uuid4
import inspect

from jwcrypto import jwt as jw_jwt, jwk

from app.core.config import settings
from app.core.databases import init_redis_connection
from app.utils.time import get_current_time, datetime_to_unix
from .sessions import Session


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime


class JWTService:
    """
    OOP-style JWT service that keeps configuration (keys, TTLs, issuer/audience, algorithm)
    on the instance and exposes methods to create and validate tokens.
    All jwcrypto operations are synchronous, but we keep async signatures to minimize
    integration changes in the codebase.
    """

    def __init__(self, *,
                 issuer: str, audience: str, algorithm: str,
                 access_ttl_minutes: int, refresh_ttl_minutes: int,
                 access_jwk: Optional[jwk.JWK] = None,
                 refresh_jwk: Optional[jwk.JWK] = None,
                 access_secret: Optional[str] = None,
                 refresh_secret: Optional[str] = None,
                 leeway_seconds: int = 0,
                 token_store: Optional[Any] = None,
                 token_store_factory: Optional[Callable[[], Any]] = None,
                 token_prefix: str = "rt:" ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.algorithm = algorithm
        self.access_ttl_minutes = access_ttl_minutes
        self.refresh_ttl_minutes = refresh_ttl_minutes
        self.leeway_seconds = leeway_seconds

        # `token_store` may be provided directly (e.g. in tests), or lazily resolved via
        # `token_store_factory` on first use so importing this module never opens a
        # Redis connection (mirrors the lazy-connect pattern in .sessions.Session).
        self.token_store = token_store
        self._token_store_factory = token_store_factory
        self.token_prefix = token_prefix

        # Accept either JWKs **or** raw secrets; derive keys if secrets are provided.
        if access_jwk and refresh_jwk:
            self.access_jwk = access_jwk
            self.refresh_jwk = refresh_jwk
        elif access_secret and refresh_secret:
            self.access_jwk = jwk.JWK.from_password(access_secret)
            self.refresh_jwk = jwk.JWK.from_password(refresh_secret)
        else:
            raise ValueError("Provide either (access_jwk & refresh_jwk) or (access_secret & refresh_secret)")

    def _get_token_store(self) -> Optional[Any]:
        if self.token_store is None and self._token_store_factory is not None:
            try:
                self.token_store = self._token_store_factory()
            except Exception:
                return None
        return self.token_store

    async def create(
            self,
            subject: str | Any,
            *,
            access_extra: Optional[Dict[str, Any]] = None,
            refresh_extra: Optional[Dict[str, Any]] = None,
            session_ip: Optional[str] = None,
            session_ua: Optional[str] = None,
    ) -> TokenPair:
        access_token = await self.__create_access_token(subject, extra_claims=access_extra)
        refresh_token = await self.__create_refresh_token(subject, extra_claims=refresh_extra)

        # Persist refresh token fingerprint (by jti) to Redis-like store for allow-list validation
        try:
            _rt = jw_jwt.JWT(jwt=refresh_token, key=self.refresh_jwk)
            _claims = _rt.claims
            _data = jw_jwt.json_decode(_claims) if isinstance(_claims, str) else _claims
            _jti = _data.get("jti")
            _sub = _data.get("sub")
            _exp = int(_data.get("exp")) if _data.get("exp") is not None else None
            if _jti and _sub and _exp is not None:
                await self.__store_refresh_record(_jti, _sub, _exp)
        except Exception:
            # Storing is best-effort; token remains valid cryptographically even if store is unavailable
            pass

        # Optionally create a server-side Session bound to this refresh token
        try:
            if session_ip is not None:
                Session.create(user_id=str(subject), ip=session_ip, refresh_token=refresh_token, ua=session_ua)
        except Exception:
            # Session persistence shouldn't break token minting
            pass

        return TokenPair(access_token=access_token, refresh_token=refresh_token,
                         access_token_expires_at=get_current_time() + timedelta(minutes=self.access_ttl_minutes),
                         refresh_token_expires_at=get_current_time() + timedelta(minutes=self.refresh_ttl_minutes))

    async def validate(self, token_str: str, *, expected_scope: Optional[str] = None) -> Dict[str, Any]:
        """Verify signature with both keys (access then refresh), validate registered claims,
        and for *refresh* tokens additionally enforce allow-list presence in Redis (if configured).
        Returns the token claims as a dict or raises `ValueError`.
        """
        last_err: Optional[Exception] = None
        for key, kind in ((self.access_jwk, "access"), (self.refresh_jwk, "refresh")):
            try:
                tok = jw_jwt.JWT(jwt=token_str, key=key)
                claims = tok.claims
                data = jw_jwt.json_decode(claims) if isinstance(claims, str) else claims
                self.__validate_registered_claims(data, expected_scope=expected_scope)

                # If it's a refresh token, validate presence in Redis allow-list (by jti)
                if data.get("scope") == "refresh":
                    jti = data.get("jti")
                    if not jti:
                        raise ValueError("Missing jti for refresh token")
                    allowed = await self.__check_refresh_record(jti)
                    if not allowed:
                        raise ValueError("Refresh token is revoked or unknown")
                return data
            except Exception as e:
                last_err = e
                continue
        raise ValueError(f"Invalid token: {last_err}")
    async def __store_refresh_record(self, jti: str, subject: str, exp_ts: int) -> None:
        """Allow-list a refresh token by its JTI with an expiry matching the token's exp."""
        store = self._get_token_store()
        if not store:
            return
        ttl = max(0, exp_ts - datetime_to_unix(get_current_time()))
        key = f"{self.token_prefix}{jti}"
        value = subject
        try:
            setex = getattr(store, "setex", None)
            if not setex:
                return
            if inspect.iscoroutinefunction(setex):
                await setex(key, ttl, value)
            else:
                setex(key, ttl, value)
        except Exception:
            # Best-effort: swallow store errors
            pass

    async def __check_refresh_record(self, jti: str) -> bool:
        """Return True if the refresh token JTI is present in the allow-list (or if no store configured)."""
        store = self._get_token_store()
        if not store:
            return True
        key = f"{self.token_prefix}{jti}"
        try:
            get_fn = getattr(store, "get", None)
            if not get_fn:
                return True
            if inspect.iscoroutinefunction(get_fn):
                val = await get_fn(key)
            else:
                val = get_fn(key)
            return bool(val)
        except Exception:
            # If store is down, fail-safe to False for refresh validation
            return False

    async def __delete_refresh_record(self, jti: str) -> None:
        store = self._get_token_store()
        if not store:
            return
        key = f"{self.token_prefix}{jti}"
        try:
            delete_fn = getattr(store, "delete", None)
            if not delete_fn:
                return
            if inspect.iscoroutinefunction(delete_fn):
                await delete_fn(key)
            else:
                delete_fn(key)
        except Exception:
            pass

    async def revoke_refresh(self, jti: str) -> None:
        """Public helper to revoke a refresh token (remove from allow-list)."""
        await self.__delete_refresh_record(jti)

    # ---------- token creation ----------
    def __build_claims(self, subject: str, ttl_minutes: int, scope: str, extra: Optional[Dict[str, Any]] = None) -> \
            Dict[str, Any]:
        now = get_current_time()
        exp = now + timedelta(minutes=ttl_minutes)
        claims: Dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": str(subject),
            "scope": scope,  # "access" or "refresh"
            "iat": datetime_to_unix(now),
            "nbf": datetime_to_unix(now),
            "exp": datetime_to_unix(exp),
        }
        if scope == "refresh":
            claims["jti"] = str(uuid4())
        if extra:
            claims.update(extra)
        return claims

    async def __create_access_token(
            self,
            subject: str | Any,
            *,
            expires_delta: Optional[int] = None,  # minutes
            extra_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        ttl = expires_delta or self.access_ttl_minutes
        claims = self.__build_claims(str(subject), ttl, scope="access", extra=extra_claims)
        token = jw_jwt.JWT(header={"alg": self.algorithm, "typ": "JWT"}, claims=claims)
        token.make_signed_token(self.access_jwk)
        return token.serialize()

    async def __create_refresh_token(
            self,
            subject: str | Any,
            *,
            expires_delta: Optional[int] = None,  # minutes
            extra_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        ttl = expires_delta or self.refresh_ttl_minutes
        claims = self.__build_claims(str(subject), ttl, scope="refresh", extra=extra_claims)
        token = jw_jwt.JWT(header={"alg": self.algorithm, "typ": "JWT"}, claims=claims)
        token.make_signed_token(self.refresh_jwk)
        return token.serialize()

    # ---------- token validation / decoding ----------
    def __validate_registered_claims(self, claims: Dict[str, Any], *, expected_scope: Optional[str]) -> None:
        now_ts = datetime_to_unix(get_current_time())
        nbf = int(claims.get("nbf", 0))
        iat = int(claims.get("iat", 0))
        exp = int(claims.get("exp", 0))
        iss = claims.get("iss")
        aud = claims.get("aud")
        if iss != self.issuer:
            raise ValueError("Invalid issuer")
        if aud != self.audience:
            raise ValueError("Invalid audience")
        if expected_scope and claims.get("scope") != expected_scope:
            raise ValueError("Invalid scope for this operation")
        # time checks with leeway
        if now_ts + self.leeway_seconds < nbf:
            raise ValueError("Token not yet valid (nbf)")
        if now_ts - self.leeway_seconds < iat - self.leeway_seconds:
            # iat should not be far in the future; mild sanity check
            pass
        if now_ts - self.leeway_seconds >= exp:
            raise ValueError("Token expired (exp)")

    async def validate_refresh_and_get_session(self, refresh_token: str) -> tuple[Dict[str, Any], Session]:
        """Validate the refresh token cryptographically + allow-list, then return (claims, Session).
        Raises ValueError if invalid or if no active, non-expired session found for this token.
        """
        claims = await self.validate(refresh_token, expected_scope="refresh")
        sess = Session.validate(refresh_token)
        if not sess:
            raise ValueError("Refresh token valid, but session not found / inactive / expired")
        return claims, sess

    @staticmethod
    def __jwk_from_secret(secret: str) -> jwk.JWK:
        """Create a symmetric JWK from a secret string.
        We use `from_password` to derive a stable oct key from the given secret.
        """
        return jwk.JWK.from_password(secret)



# Instantiate a singleton service using current module constants
JWT = JWTService(
    issuer=settings.auth_jwt_issuer,
    audience=settings.auth_jwt_audience,
    algorithm=settings.auth_jwt_algorithm,
    access_ttl_minutes=settings.auth_jwt_access_token_expire_minutes,
    refresh_ttl_minutes=settings.auth_jwt_refresh_token_expire_minutes,
    access_secret=settings.auth_jwt_secret_key,
    refresh_secret=settings.auth_jwt_refresh_secret_key,
    # Resolved lazily on first use so importing this module never opens a Redis
    # connection (init_redis_connection() retries with backoff and can block/raise).
    token_store_factory=init_redis_connection,
    token_prefix=getattr(settings, "auth_refresh_token_prefix", "rt:")
)


# Optional FastAPI dependency helper
async def get_jwt_service() -> JWTService:
    return JWT
