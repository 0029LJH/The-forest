import logging
from typing import List

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time_utils import utcnow
from app.models_config.models import ModelConfig

logger = logging.getLogger(__name__)


class ModelConfigService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_models(self, user_id: int, model_type: str) -> List[dict]:
        result = await self.session.execute(
            select(ModelConfig)
            .where(ModelConfig.user_id == user_id, ModelConfig.model_type == model_type)
            .order_by(ModelConfig.created_at.desc())
        )
        return [
            {
                "id": m.id, "model_type": m.model_type, "display_name": m.display_name,
                "base_url": m.base_url, "api_key": m.api_key, "model_name": m.model_name,
                "api_format": m.api_format or "openai",
                "parameters": m.parameters or {}, "is_active": m.is_active,
                "fallback_config_id": m.fallback_config_id,
                "created_at": m.created_at.isoformat() + "Z" if m.created_at else None,
            }
            for m in result.scalars()
        ]

    async def add_model(self, user_id: int, model_type: str, display_name: str,
                        base_url: str, api_key: str, model_name: str,
                        parameters: dict | None = None,
                        api_format: str | None = None) -> dict:
        # 模型卡片校验：模型名必须已注册且类型匹配（mineru 不参与卡片注册）。
        # 未注册的自定义模型（如新发布模型、自建网关）允许添加，但必须由
        # 前端指定接入协议（openai 兼容 / anthropic 兼容），且仅限 chat
        card = None
        if model_type in ("chat", "embedding"):
            from app.models_config.cards import get_card
            from app.common.exception.exceptions import BusinessException
            card = get_card(model_name)
            if card is None:
                if model_type == "embedding":
                    raise BusinessException(
                        f"未知模型 {model_name}：embedding 需注册模型卡片"
                        f"（维度校验依赖卡片声明），暂不支持自定义添加")
                if api_format not in ("openai", "anthropic"):
                    raise BusinessException(
                        f"未知模型 {model_name}：自定义模型需从"
                        f"「OpenAI 兼容 / Anthropic 兼容」选项添加以指定接入协议")
            else:
                if card.kind.value != model_type:
                    raise BusinessException(
                        f"{model_name} 是 {card.kind.value} 模型，不能作为 {model_type} 类型添加")
                if api_format is None:
                    api_format = card.api.request_format.value

        # 参数校验：键必须在卡片 schema 中，数值/枚举按 schema 约束校验
        # （自定义模型无卡片 → 参数不过滤，原样保存）
        validated = self._validate_parameters(card, parameters)
        # None 值与缺省等价（运行时按 .get() 兜底默认值），不落库
        validated = {k: v for k, v in validated.items() if v is not None}

        model = ModelConfig(
            user_id=user_id, model_type=model_type, display_name=display_name,
            base_url=base_url, api_key=api_key, model_name=model_name,
            api_format=api_format or "openai",
            parameters=validated or None,
            is_active=False,
        )
        self.session.add(model)
        await self.session.flush()
        return {
            "id": model.id, "model_type": model.model_type, "display_name": model.display_name,
            "base_url": model.base_url, "api_key": model.api_key, "model_name": model.model_name,
            "api_format": model.api_format or "openai",
            "parameters": model.parameters, "is_active": model.is_active,
        }

    @staticmethod
    def _validate_parameters(card, parameters: dict | None) -> dict:
        if not parameters:
            return {}
        if card is None:
            # 自定义模型无卡片 schema：参数原样保存
            return dict(parameters)
        from app.common.exception.exceptions import BusinessException
        schema = card.parameters or {}
        validated = {}
        for key, value in parameters.items():
            prop = schema.get(key)
            if prop is None:
                # 前端 Axios 拦截器把 /model-cards 响应的 schema 键转成
                # camelCase 后原样提交（max_tokens → maxTokens），归一化
                # 回 snake_case 并以 canonical 键入库（运行时按
                # parameters.get("max_tokens") 读取，键不一致会静默丢配置）
                import re
                snake_key = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()
                if snake_key != key and snake_key in schema:
                    key = snake_key
                    prop = schema[key]
            if prop is None:
                raise BusinessException(f"参数 {key} 不在模型 {card.name if card else ''} 的可用参数中")
            ptype = prop.get("type")
            # enum 优先：dimensions 这类参数同时声明 type=integer + enum
            if prop.get("enum"):
                if value not in prop["enum"]:
                    raise BusinessException(f"参数 {key} 只支持: {prop['enum']}")
            elif ptype in ("number", "integer") and isinstance(value, (int, float)) and not isinstance(value, bool):
                if prop.get("minimum") is not None and value < prop["minimum"]:
                    raise BusinessException(f"参数 {key} 不能小于 {prop['minimum']}")
                if prop.get("maximum") is not None and value > prop["maximum"]:
                    raise BusinessException(f"参数 {key} 不能大于 {prop['maximum']}")
            validated[key] = value
        return validated

    async def activate_model(self, user_id: int, model_id: int) -> dict:
        # Deactivate all models of the same type
        model = await self._get_model(user_id, model_id)
        if not model:
            from app.common.exception.exceptions import BusinessException
            raise BusinessException("模型配置不存在")

        # embedding 激活前校验维度与存量向量一致：维度不匹配会令检索整体失效
        if model.model_type == "embedding":
            await self._check_embedding_dimension(model)

        await self.session.execute(
            update(ModelConfig)
            .where(ModelConfig.user_id == user_id, ModelConfig.model_type == model.model_type)
            .values(is_active=False)
        )

        model.is_active = True
        model.updated_at = utcnow()
        await self.session.flush()

        return {
            "id": model.id, "model_type": model.model_type, "display_name": model.display_name,
            "base_url": model.base_url, "api_key": model.api_key, "model_name": model.model_name,
            "is_active": True,
        }

    async def set_fallback(self, user_id: int, config_id: int,
                           fallback_config_id: int | None) -> dict:
        """为配置设置备用模型（降级目标）。

        约束：备用模型必须是同类型的已配置模型、不能是自己、
        且模型名必须在卡片目录（"可用模型"）中注册。
        """
        from app.common.exception.exceptions import BusinessException
        from app.models_config.cards import get_card

        model = await self._get_model(user_id, config_id)
        if not model:
            raise BusinessException("模型配置不存在")

        if fallback_config_id is not None:
            if fallback_config_id == config_id:
                raise BusinessException("备用模型不能是当前配置本身")
            fb = await self._get_model(user_id, fallback_config_id)
            if not fb:
                raise BusinessException("备用模型配置不存在")
            if fb.model_type != model.model_type:
                raise BusinessException("备用模型必须与主模型类型相同")
            if get_card(fb.model_name) is None:
                raise BusinessException(
                    f"{fb.model_name} 未注册模型卡片，不能作为备用模型（仅可用模型列表中的模型）")
            if fb.model_type == "embedding":
                # 备用维度必须与存量向量一致（与主配置同等的维度约束）
                await self._check_embedding_dimension(fb)

        model.fallback_config_id = fallback_config_id
        model.updated_at = utcnow()
        await self.session.flush()
        return {
            "id": model.id, "display_name": model.display_name,
            "fallback_config_id": model.fallback_config_id,
        }

    async def delete_model(self, user_id: int, model_id: int):
        model = await self._get_model(user_id, model_id)
        if not model:
            from app.common.exception.exceptions import BusinessException
            raise BusinessException("模型配置不存在")
        await self.session.delete(model)
        await self.session.flush()

    @staticmethod
    async def _check_embedding_dimension(model: ModelConfig) -> None:
        """激活 embedding 模型前校验：存量向量维度必须与所选维度一致。

        配置了 parameters.dimensions 时以所选维度为准，否则取卡片默认。
        向量库为空（fresh 库）时放行——首次写入决定维度。
        """
        from sqlalchemy import text
        from app.models_config.cards import get_card
        from app.common.exception.exceptions import BusinessException

        card = get_card(model.model_name)
        if card is None or not card.dimensions:
            return
        selected_dim = (model.parameters or {}).get("dimensions") or card.dimensions[0]

        from app.dependencies import engine
        try:
            async with engine.begin() as conn:
                dim = (await conn.execute(text(
                    "SELECT array_length(embedding::real[], 1) "
                    "FROM langchain_pg_embedding LIMIT 1"
                ))).scalar()
        except Exception:
            # 表不存在（fresh 库）：放行
            return

        if dim is not None and selected_dim is not None and dim != selected_dim:
            raise BusinessException(
                f"无法激活 {model.model_name}：所选向量维度为 {selected_dim}，"
                f"但当前向量库维度为 {dim}。切换维度需先重灌向量（reindex）后再激活。")

    async def get_active_model(self, user_id: int, model_type: str) -> dict | None:
        result = await self.session.execute(
            select(ModelConfig)
            .where(ModelConfig.user_id == user_id, ModelConfig.model_type == model_type, ModelConfig.is_active == True)
        )
        m = result.scalar_one_or_none()
        if not m:
            return None
        return {
            "base_url": m.base_url, "api_key": m.api_key, "model_name": m.model_name,
            "api_format": m.api_format or "openai",
            "parameters": m.parameters or {},
        }

    async def _get_model(self, user_id: int, model_id: int) -> ModelConfig | None:
        result = await self.session.execute(
            select(ModelConfig)
            .where(ModelConfig.id == model_id, ModelConfig.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def test_connection(base_url: str, api_key: str, model_name: str, model_type: str,
                              api_format: str | None = None) -> dict:
        if model_type == "mineru":
            return await ModelConfigService._test_mineru(base_url, api_key, model_name)
        # 卡片模型（前端选卡添加）不传 api_format：从卡片推断接入协议，
        # 否则 Claude 这类原生 anthropic 模型会被误当 OpenAI 兼容测试而失败
        if api_format is None:
            from app.models_config.cards import get_card
            card = get_card(model_name)
            if card is not None:
                api_format = card.api.request_format.value
        url = base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                if model_type == "chat":
                    if api_format == "anthropic":
                        resp = await client.post(
                            f"{url}/messages",
                            json={"model": model_name, "max_tokens": 5,
                                  "messages": [{"role": "user", "content": "hi"}]},
                            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                        )
                    else:
                        resp = await client.post(
                            f"{url}/chat/completions",
                            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
                            headers={"Authorization": f"Bearer {api_key}"},
                        )
                else:
                    resp = await client.post(
                        f"{url}/embeddings",
                        json={"model": model_name, "input": "test"},
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                if resp.status_code < 500:
                    return {"ok": True, "status": resp.status_code, "message": "连接成功"}
                return {"ok": False, "status": resp.status_code, "message": f"API 返回 {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "status": 0, "message": str(e)[:200]}

    @staticmethod
    async def _test_mineru(base_url: str, api_key: str, model_name: str) -> dict:
        """验证 MinerU token：申请一次上传链接（不消耗解析额度）"""
        url = (base_url or "https://mineru.net").rstrip("/") + "/api/v4/file-urls/batch"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    json={"files": [{"name": "connection-test.pdf"}],
                          "model_version": model_name or "vlm"},
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {api_key}"},
                )
            data = resp.json()
            if data.get("code") == 0:
                return {"ok": True, "status": resp.status_code, "message": "连接成功"}
            return {"ok": False, "status": resp.status_code, "message": data.get("msg", "连接失败")}
        except Exception as e:
            return {"ok": False, "status": 0, "message": str(e)[:200]}
