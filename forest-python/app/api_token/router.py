from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_token.service import ApiTokenService
from app.audit.service import log_audit
from app.auth.dependencies import require_admin
from app.common.response import ApiResponse
from app.common.security.context import AuthenticatedUser
from app.common.time_utils import utcnow
from app.dependencies import get_db

router = APIRouter()


class CreateApiTokenRequest(BaseModel):
    userId: int = Field(alias="userId")
    name: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(min_length=1)
    groupIds: Optional[list[int]] = Field(default=None, alias="groupIds")
    # None = 永久；否则从创建时间起算 N 天
    expiresInDays: Optional[int] = Field(default=None, alias="expiresInDays", ge=1, le=3650)

    model_config = {"populate_by_name": True}


@router.get("/api-tokens")
async def list_api_tokens(
    userId: Optional[int] = Query(default=None, alias="userId"),
    _admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = ApiTokenService(db)
    tokens = await service.list_tokens(user_id=userId)
    return ApiResponse.ok(data=tokens)


@router.post("/api-tokens")
async def create_api_token(
    body: CreateApiTokenRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    expires_at = None
    if body.expiresInDays is not None:
        expires_at = utcnow() + timedelta(days=body.expiresInDays)
    service = ApiTokenService(db)
    result = await service.create(
        user_id=body.userId,
        name=body.name,
        scopes=body.scopes,
        group_ids=body.groupIds,
        expires_at=expires_at,
    )
    await db.flush()
    await log_audit(db, admin, "API_TOKEN_CREATE", "api_token", result["tokenId"],
                    {"userId": body.userId, "name": body.name, "scopes": body.scopes})
    return ApiResponse.ok(data=result, message="令牌已创建，完整 token 仅显示这一次，请妥善保存")


@router.post("/api-tokens/{token_id}/revoke")
async def revoke_api_token(
    token_id: int,
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = ApiTokenService(db)
    await service.revoke(token_id)
    await db.flush()
    await log_audit(db, admin, "API_TOKEN_REVOKE", "api_token", token_id, {})
    return ApiResponse.ok(message="令牌已吊销")
