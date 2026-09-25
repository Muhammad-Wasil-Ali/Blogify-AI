import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.config import settings


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    try:
        header = jwt.get_unverified_header(credentials.credentials)
        algorithm = header.get("alg", "HS256")
        if algorithm == "HS256":
            key = settings.SUPABASE_JWT_SECRET
        else:
            jwks_client = jwt.PyJWKClient(
                f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
            )
            key = jwks_client.get_signing_key_from_jwt(credentials.credentials).key
        payload = jwt.decode(
            credentials.credentials,
            key,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    return user_id
