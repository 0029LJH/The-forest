import hashlib
import logging
import secrets
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_token.models import ApiToken
from app.auth.models import User
from app.common.exception.exceptions import BusinessException
from app.common.time_utils import utcnow

logger = logging.getLogger(__name__)

VALID_SCOPES = {"qa", "groups_read", "documents_read"}

SCOPE_LABELS = {
    "qa": "知识库问答",
    "groups_read": "群组信息读取",
    "documents_read": "文档读取",
}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> tuple[str, str, str]:
    """Generate a plaintext token. Returns (plaintext, hash, display prefix)."""
    raw = "nexus_" + secrets.token_hex(24)
    return raw, _hash_token(raw), raw[:14] + "…"


def _fmt(dt) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None


class ApiTokenService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, name: str, scopes: list,
                     group_ids: Optional[list], expires_at) -> dict:
        invalid = [s for s in scopes if s not in VALID_SCOPES]
        if invalid:
            raise BusinessException(f"无效的权限范围: {', '.join(invalid)}")
        if not scopes:
            raise BusinessException("至少选择一个权限范围")

        user = (await self.session.execute(
            select(User).where(User.id == user_id, User.status == "ACTIVE")
        )).scalar_one_or_none()
        if user is None:
            raise BusinessException("用户不存在或已被禁用")

        if group_ids:
            from app.group.models import Group
            existing = set((await self.session.execute(
                select(Group.id).where(Group.id.in_(group_ids), Group.status != "DELETED")
            )).scalars().all())
            missing = [gid for gid in group_ids if gid not in existing]
            if missing:
                raise BusinessException(f"群组不存在: {missing}")

        plain, token_hash, prefix = generate_token()
        record = ApiToken(
            user_id=user_id,
            name=name.strip(),
            token_hash=token_hash,
            token_prefix=prefix,
            scopes=scopes,
            group_ids=group_ids or None,
            status="ACTIVE",
            expires_at=expires_at,
        )
        self.session.add(record)
        await self.session.flush()
        logger.info("API token created: id=%s, user=%s, scopes=%s", record.id, user_id, scopes)
        return {
            "tokenId": record.id,
            "token": plain,
            "name": record.name,
            "userId": user_id,
            "scopes": scopes,
            "groupIds": record.group_ids,
            "expiresAt": _fmt(record.expires_at),
        }

    async def list_tokens(self, user_id: Optional[int] = None) -> list[dict]:
        stmt = select(ApiToken, User.username, User.display_name) \
            .join(User, ApiToken.user_id == User.id) \
            .order_by(ApiToken.id.desc())
        if user_id is not None:
            stmt = stmt.where(ApiToken.user_id == user_id)
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "tokenId": t.id,
                "userId": t.user_id,
                "username": username,
                "displayName": display_name,
                "name": t.name,
                "tokenPrefix": t.token_prefix,
                "scopes": t.scopes or [],
                "groupIds": t.group_ids,
                "status": t.status,
                "expiresAt": _fmt(t.expires_at),
                "lastUsedAt": _fmt(t.last_used_at),
                "createdAt": _fmt(t.created_at),
            }
            for t, username, display_name in rows
        ]

    async def revoke(self, token_id: int) -> None:
        result = await self.session.execute(
            update(ApiToken)
            .where(ApiToken.id == token_id, ApiToken.status == "ACTIVE")
            .values(status="REVOKED", updated_at=utcnow())
        )
        if result.rowcount == 0:
            raise BusinessException("令牌不存在或已吊销")
        logger.info("API token revoked: id=%s", token_id)

    async def validate(self, raw_token: str) -> Optional[tuple[ApiToken, User]]:
        """Validate a bearer token. Returns (token, user) or None if invalid."""
        token_hash = _hash_token(raw_token)
        result = await self.session.execute(
            select(ApiToken, User)
            .join(User, ApiToken.user_id == User.id)
            .where(ApiToken.token_hash == token_hash)
        )
        row = result.one_or_none()
        if row is None:
            return None
        token, user = row
        if token.status != "ACTIVE":
            return None
        if token.expires_at is not None and token.expires_at <= utcnow():
            return None
        if user.status != "ACTIVE":
            return None
        return token, user

    async def touch(self, token_id: int) -> None:
        await self.session.execute(
            update(ApiToken)
            .where(ApiToken.id == token_id)
            .values(last_used_at=utcnow())
        )
        await self.session.flush()
