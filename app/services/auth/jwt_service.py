from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional, Dict
from uuid import uuid4

from jwcrypto import jwt as jw_jwt, jwk

from app.core.config import settings
from app.utils.time import get_current_time, datetime_to_unix


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


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
                 leeway_seconds: int = 0) -> None:
        self.issuer = issuer
        self.audience = audience
        self.algorithm = algorithm
        self.access_ttl_minutes = access_ttl_minutes
        self.refresh_ttl_minutes = refresh_ttl_minutes
        self.leeway_seconds = leeway_seconds

        # Accept either JWKs **or** raw secrets; derive keys if secrets are provided.
        if access_jwk and refresh_jwk:
            self.access_jwk = access_jwk
            self.refresh_jwk = refresh_jwk
        elif access_secret and refresh_secret:
            self.access_jwk = jwk.JWK.from_password(access_secret)
            self.refresh_jwk = jwk.JWK.from_password(refresh_secret)
        else:
            raise ValueError("Provide either (access_jwk & refresh_jwk) or (access_secret & refresh_secret)")

    async def create(
            self,
            subject: str | Any,
            *,
            access_extra: Optional[Dict[str, Any]] = None,
            refresh_extra: Optional[Dict[str, Any]] = None,
    ) -> TokenPair:
        access_token = await self.__create_access_token(subject, extra_claims=access_extra)
        refresh_token = await self.__create_refresh_token(subject, extra_claims=refresh_extra)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    async def validate(self, token_str: str, *, expected_scope: Optional[str] = None) -> Dict[str, Any]:
        """Verify signature with both keys (access then refresh) and return claims as dict.
        The caller can also pin `expected_scope` to enforce correct token kind.
        """
        last_err: Optional[Exception] = None
        for key, kind in ((self.access_jwk, "access"), (self.refresh_jwk, "refresh")):
            try:
                tok = jw_jwt.JWT(jwt=token_str, key=key)
                claims = tok.claims
                data = jw_jwt.json_decode(claims) if isinstance(claims, str) else claims
                # if expected_scope provided, validate; otherwise accept any and validate later
                self.__validate_registered_claims(data, expected_scope=expected_scope)
                return data
            except Exception as e:  # signature mismatch or invalid claims
                last_err = e
                continue
        raise ValueError(f"Invalid token: {last_err}")

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
)


# Optional FastAPI dependency helper
async def get_jwt_service() -> JWTService:
    return JWT
