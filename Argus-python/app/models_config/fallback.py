"""备用模型降级：主模型调用失败（异常/首字节超时）自动切换备用模型。

用 langchain 的 with_fallbacks 机制包装：主模型与备用模型都是
ChatOpenAI（OpenAI 兼容协议，见模型卡片），流式场景下仅在首个
chunk 产出前失败才会切换（中途失败保留部分答案，由上层处理）。
"""

import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# 首字节超时：deepseek 等 API 排队时最坏 20s+，60s 兜底
REQUEST_TIMEOUT = 60


async def _get_fallback_config(user_id: int, model_type: str) -> dict | None:
    """激活配置的备用模型配置（无备用返回 None）。"""
    from sqlalchemy import select
    from app.dependencies import async_session_factory
    from app.models_config.models import ModelConfig

    async with async_session_factory() as session:
        active = (await session.execute(
            select(ModelConfig).where(
                ModelConfig.user_id == user_id,
                ModelConfig.model_type == model_type,
                ModelConfig.is_active == True,  # noqa: E712
            )
        )).scalar_one_or_none()
        if not active or not active.fallback_config_id:
            return None
        fb = (await session.execute(
            select(ModelConfig).where(ModelConfig.id == active.fallback_config_id)
        )).scalar_one_or_none()
        if not fb:
            return None
        return {
            "base_url": fb.base_url,
            "api_key": fb.api_key,
            "model_name": fb.model_name,
            "api_format": fb.api_format or "openai",
            "parameters": fb.parameters or {},
        }


async def build_chat_model_with_fallback(
    user_id: int,
    streaming: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """构建带备用降级的聊天模型，按配置的接入协议分流：

    - openai（默认）：ChatOpenAI，/chat/completions 协议
    - anthropic：ChatAnthropic，原生 /v1/messages 协议

    显式传入的 temperature/max_tokens 只作用于主模型；备用模型使用
    自己配置的 parameters（回退 .env 默认）。
    """
    from app.models_config.resolver import get_chat_config

    cfg = await get_chat_config(user_id)
    params = cfg.get("parameters") or {}

    def _make(c: dict) -> BaseChatModel:
        api_format = c.get("api_format") or "openai"
        c_params = c.get("parameters") or {}

        if temperature is not None:
            eff_temperature = temperature
        elif c_params.get("temperature") is not None:
            eff_temperature = c_params["temperature"]
        else:
            eff_temperature = settings.chat.temperature
        if max_tokens is not None:
            eff_max_tokens = max_tokens
        elif c_params.get("max_tokens"):
            eff_max_tokens = c_params["max_tokens"]
        else:
            eff_max_tokens = None

        if api_format == "anthropic":
            from langchain_anthropic import ChatAnthropic
            kwargs: dict = {
                "model": c["model_name"],
                "api_key": c["api_key"],
                "base_url": c["base_url"],
                "timeout": REQUEST_TIMEOUT,
            }
            if streaming:
                kwargs["streaming"] = True
            # anthropic 温度范围 0~1（越界会被 API 直接拒绝，钳制兜底）；
            # max_tokens 必传，缺省时用库默认 1024
            if eff_temperature is not None:
                kwargs["temperature"] = max(0.0, min(1.0, eff_temperature))
            if eff_max_tokens is not None:
                kwargs["max_tokens"] = eff_max_tokens
            return ChatAnthropic(**kwargs)

        kwargs: dict = {
            "model": c["model_name"],
            "openai_api_key": c["api_key"],
            "openai_api_base": c["base_url"],
            "timeout": REQUEST_TIMEOUT,
        }
        if streaming:
            kwargs["streaming"] = True
            # 末 chunk 携带真实 token 用量（OpenAI 兼容协议，
            # dashscope/deepseek/openai 均支持 include_usage）
            kwargs["model_kwargs"] = {"stream_options": {"include_usage": True}}
        if eff_temperature is not None:
            kwargs["temperature"] = eff_temperature
        if eff_max_tokens is not None:
            kwargs["max_tokens"] = eff_max_tokens
        return ChatOpenAI(**kwargs)

    primary = _make(cfg)
    fallback_cfg = await _get_fallback_config(user_id, "chat")
    if fallback_cfg is None:
        return primary

    fallback = _make(fallback_cfg)
    logger.info(
        "Chat model with fallback: %s (fallback: %s)",
        cfg["model_name"], fallback_cfg["model_name"],
    )
    return primary.with_fallbacks([fallback], exceptions_to_handle=(Exception,))
