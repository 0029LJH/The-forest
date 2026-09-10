from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.security import parse_access_token
from app.common.security.context import AuthenticatedUser, UserContext
from app.common.exception.exceptions import AuthenticationException, ForbiddenException
from app.config import settings
from app.dependencies import get_db


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> AuthenticatedUser:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    else:
        token = auth_header.strip()

    if not token:
        raise AuthenticationException("Token 无效或已过期")

    try:
        claims = parse_access_token(token)
    except Exception:
        raise AuthenticationException("Token 无效或已过期")

    if claims.get("iss") != settings.auth.issuer:
        raise AuthenticationException("Token 无效或已过期")

    # 校验 DB 用户状态：被禁用/删除的账号即使 token 未过期也立即失效；
    # 角色以 DB 为准，管理员降权后旧 token 不再具备管理权限
    from sqlalchemy import select
    from app.auth.models import User
    result = await db.execute(
        select(User.status, User.system_role, User.display_name, User.must_change_password)
        .where(User.id == claims["uid"])
    )
    row = result.first()
    if row is None or row[0] != "ACTIVE":
        raise AuthenticationException("账号已被禁用或不存在")

    user = AuthenticatedUser(
        user_id=claims["uid"],
        user_code=claims["sub"],
        display_name=row[2] or claims["displayName"],
        system_role=row[1],
        must_change_password=row[3],
    )
    UserContext.set(user)
    return user


async def require_admin(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if current_user.system_role != "ADMIN":
        raise ForbiddenException("需要管理员权限")
    return current_user
