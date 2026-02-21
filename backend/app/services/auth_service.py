from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from app.models.user import User, OAuthAccount, RefreshToken
from app.core.security import create_refresh_token, hash_token
from app.core.config import settings

async def get_or_create_user(db: AsyncSession, google_user_info: dict) -> User:
    provider_id = str(google_user_info["sub"])
    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_user_id == provider_id
        )
    )
    oauth_account = result.scalar_one_or_none()
    if oauth_account:
        result = await db.execute(select(User).where(User.id == oauth_account.user_id))
        return result.scalar_one()

    result = await db.execute(select(User).where(User.email == google_user_info["email"]))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=google_user_info["email"],
            display_name=google_user_info.get("name"),
            avatar_url=google_user_info.get("picture")
        )
        db.add(user)
        await db.flush()

    oauth = OAuthAccount(user_id=user.id, provider="google", provider_user_id=provider_id)
    db.add(oauth)
    await db.commit()
    await db.refresh(user)
    return user

async def create_refresh_token_for_user(db: AsyncSession, user_id) -> str:
    raw_token, token_hash = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(db_token)
    await db.commit()
    return raw_token

async def get_current_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()