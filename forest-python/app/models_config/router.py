from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import log_audit
from app.auth.dependencies import get_current_user, require_admin
from app.common.response import ApiResponse
from app.common.security.context import AuthenticatedUser
from app.dependencies import get_db
from app.models_config.service import ModelConfigService

router = APIRouter()


@router.get("/model-configs")
async def list_models(
    model_type: str = Query(..., alias="modelType"),
    _admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = ModelConfigService(db)
    models = await service.list_models(_admin.user_id, model_type)
    return ApiResponse.ok(data=models)


@router.get("/model-cards")
async def list_model_cards(
    _admin: AuthenticatedUser = Depends(require_admin),
):
    """模型卡片目录（前端添加模型表单的数据源）。"""
    from app.models_config.cards import list_cards, card_form_schema
    cards = [card_form_schema(c) for c in list_cards()]
    return ApiResponse.ok(data=cards)


@router.post("/model-configs")
async def add_model(
    body: dict,
    _admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = ModelConfigService(db)
    result = await service.add_model(
        _admin.user_id,
        model_type=body.get("model_type", body.get("modelType", "chat")),
        display_name=body.get("display_name", body.get("displayName", "")),
        base_url=body.get("base_url", body.get("baseUrl", "")),
        api_key=body.get("api_key", body.get("apiKey", "")),
        model_name=body.get("model_name", body.get("modelName", "")),
        parameters=body.get("parameters") or {},
        api_format=body.get("api_format", body.get("apiFormat")),
    )
    await log_audit(db, _admin, "MODEL_CONFIG_ADD", "model_config", result["id"],
                    {"modelName": result["model_name"], "modelType": result["model_type"]})
    return ApiResponse.ok(data=result)


class SetFallbackRequest(BaseModel):
    fallbackConfigId: int | None = Field(default=None, alias="fallbackConfigId")

    model_config = {"populate_by_name": True}


@router.patch("/model-configs/{model_id}/fallback")
async def set_fallback(
    model_id: int,
    body: SetFallbackRequest,
    admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = ModelConfigService(db)
    result = await service.set_fallback(admin.user_id, model_id, body.fallbackConfigId)
    await db.flush()
    await log_audit(db, admin, "MODEL_CONFIG_FALLBACK", "model_config", model_id,
                    {"fallbackConfigId": body.fallbackConfigId})
    return ApiResponse.ok(data=result, message="备用模型已更新")


@router.patch("/model-configs/{model_id}/activate")
async def activate_model(
    model_id: int,
    _admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = ModelConfigService(db)
    result = await service.activate_model(_admin.user_id, model_id)
    await log_audit(db, _admin, "MODEL_CONFIG_ACTIVATE", "model_config", model_id,
                    {"modelName": result["model_name"], "modelType": result["model_type"]})
    return ApiResponse.ok(data=result)


@router.delete("/model-configs/{model_id}")
async def delete_model(
    model_id: int,
    _admin: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = ModelConfigService(db)
    await service.delete_model(_admin.user_id, model_id)
    await log_audit(db, _admin, "MODEL_CONFIG_DELETE", "model_config", model_id)
    return ApiResponse.ok(message="已删除")


@router.post("/model-configs/test")
async def test_connection(
    body: dict,
    _admin: AuthenticatedUser = Depends(require_admin),
):
    result = await ModelConfigService.test_connection(
        base_url=body.get("base_url", body.get("baseUrl", "")),
        api_key=body.get("api_key", body.get("apiKey", "")),
        model_name=body.get("model_name", body.get("modelName", "")),
        model_type=body.get("model_type", body.get("modelType", "chat")),
        api_format=body.get("api_format", body.get("apiFormat")),
    )
    return ApiResponse.ok(data=result)
