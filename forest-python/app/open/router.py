"""Open API — external systems access the knowledge base with scoped bearer tokens.

Auth: Authorization: Bearer nexus_xxx (created by admins in 管理控制台 → API 令牌).
Tokens carry fine-grained scopes (qa / groups_read / documents_read) and an
optional group allow-list; every endpoint re-checks the token's user identity
against group membership (require_group_access).
"""

import io
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_token.service import ApiTokenService
from app.auth.models import User
from app.common.exception.exceptions import AuthenticationException, BusinessException, ForbiddenException
from app.dependencies import get_db
from app.group.service import require_group_access, GroupManagementService, GroupMembershipService

router = APIRouter(prefix="/api/open", tags=["Open API"])

SCOPE_QA = "qa"
SCOPE_GROUPS_READ = "groups_read"
SCOPE_DOCUMENTS_READ = "documents_read"


class OpenApiContext:
    def __init__(self, user: User, token):
        self.user = user
        self.token = token

    @property
    def user_id(self) -> int:
        return self.user.id


async def get_open_context(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> OpenApiContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("缺少 Bearer Token（Authorization: Bearer nexus_xxx）")
    raw = authorization[len("Bearer "):].strip()
    if not raw:
        raise AuthenticationException("Token 不能为空")

    service = ApiTokenService(db)
    result = await service.validate(raw)
    if result is None:
        raise AuthenticationException("Token 无效、已吊销或已过期")
    token, user = result
    await service.touch(token.id)
    return OpenApiContext(user, token)


def require_scope(ctx: OpenApiContext, scope: str) -> None:
    if scope not in (ctx.token.scopes or []):
        raise ForbiddenException(f"Token 缺少 {scope} 权限")


def ensure_group_allowed(ctx: OpenApiContext, group_id: int) -> None:
    """Token 配置了群组白名单时必须命中，否则拒绝。"""
    if ctx.token.group_ids is not None and group_id not in ctx.token.group_ids:
        raise ForbiddenException("Token 无权访问该群组")


# ---- Token info ----

@router.get("/me")
async def open_me(ctx: OpenApiContext = Depends(get_open_context)):
    """验证 token 并返回其身份与权限（调试/接入用）。"""
    t = ctx.token
    return {
        "userId": ctx.user.id,
        "userCode": ctx.user.user_code,
        "displayName": ctx.user.display_name,
        "systemRole": ctx.user.system_role,
        "scopes": t.scopes or [],
        "groupIds": t.group_ids,
        "expiresAt": t.expires_at.isoformat() + "Z" if t.expires_at else None,
    }


# ---- QA ----

class OpenAskRequest(BaseModel):
    groupId: int = Field(alias="groupId")
    question: str = Field(min_length=1, max_length=5000)

    model_config = {"populate_by_name": True}


@router.post("/qa/ask")
async def open_qa_ask(
    request: OpenAskRequest,
    ctx: OpenApiContext = Depends(get_open_context),
    db: AsyncSession = Depends(get_db),
):
    require_scope(ctx, SCOPE_QA)
    ensure_group_allowed(ctx, request.groupId)
    await require_group_access(db, ctx.user_id, ctx.user.system_role, request.groupId)

    from app.qa.router import qa_service
    return await qa_service.ask(ctx.user_id, request.groupId, request.question)


# ---- Groups ----

@router.get("/groups/my")
async def open_groups_my(
    ctx: OpenApiContext = Depends(get_open_context),
    db: AsyncSession = Depends(get_db),
):
    require_scope(ctx, SCOPE_GROUPS_READ)
    data = await GroupManagementService(db).list_my_groups(ctx.user_id)
    if ctx.token.group_ids is not None:
        allowed = set(ctx.token.group_ids)
        data["owned_groups"] = [g for g in data["owned_groups"] if g["group_id"] in allowed]
        data["joined_groups"] = [g for g in data["joined_groups"] if g["group_id"] in allowed]
        data["pending_invitations"] = [i for i in data["pending_invitations"] if i["group_id"] in allowed]
    return data


@router.get("/groups/{group_id}/members")
async def open_group_members(
    group_id: int,
    ctx: OpenApiContext = Depends(get_open_context),
    db: AsyncSession = Depends(get_db),
):
    require_scope(ctx, SCOPE_GROUPS_READ)
    ensure_group_allowed(ctx, group_id)
    await require_group_access(db, ctx.user_id, ctx.user.system_role, group_id)
    return await GroupMembershipService(db).list_members(group_id)


# ---- Documents ----

@router.get("/documents")
async def open_documents(
    groupId: int = Query(alias="groupId"),
    status: str = Query(default=""),
    fileName: str = Query(default="", alias="fileName"),
    ctx: OpenApiContext = Depends(get_open_context),
    db: AsyncSession = Depends(get_db),
):
    require_scope(ctx, SCOPE_DOCUMENTS_READ)
    ensure_group_allowed(ctx, groupId)
    await require_group_access(db, ctx.user_id, ctx.user.system_role, groupId)

    from app.document.service import DocumentQueryService
    return await DocumentQueryService(db).list_documents(
        groupId, status=status or None, file_name=fileName or None
    )


@router.get("/documents/{document_id}/download")
async def open_document_download(
    document_id: int,
    ctx: OpenApiContext = Depends(get_open_context),
    db: AsyncSession = Depends(get_db),
):
    require_scope(ctx, SCOPE_DOCUMENTS_READ)

    # 文档归属以数据库为准，不接受客户端自报的 group_id
    from app.document.models import Document
    doc = (await db.execute(
        select(Document).where(Document.id == document_id, Document.deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if doc is None:
        raise BusinessException("文档不存在")
    ensure_group_allowed(ctx, doc.group_id)
    await require_group_access(db, ctx.user_id, ctx.user.system_role, doc.group_id)

    from app.document.service import DocumentQueryService
    data, file_name, content_type = await DocumentQueryService(db).download(document_id)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"},
    )
