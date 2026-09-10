from datetime import datetime
from typing import Optional

from sqlalchemy import String, BigInteger, DateTime, ForeignKey, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApiToken(Base):
    """Open API access token (admin-managed, per-user, scoped)."""

    __tablename__ = "api_tokens"

    __table_args__ = (
        Index("idx_api_token_hash", "token_hash", unique=True),
        Index("idx_api_token_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    # 细粒度权限：["qa", "groups_read", "documents_read"] 的任意子集
    scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    # 限定可访问的群组 id 列表；null = 不限制（继承用户身份能访问的全部群组）
    group_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
