import logging
from typing import Optional

from app.config import settings
from app.models_config.service import ModelConfigService


logger = logging.getLogger(__name__)


async def get_chat_config(user_id: int) -> dict:
    """Get chat model config for the user, falling back to .env defaults."""
    try:
        from app.dependencies import async_session_factory
        async with async_session_factory() as session:
            service = ModelConfigService(session)
            active = await service.get_active_model(user_id, "chat")
            await session.commit()
            if active:
                return active
    except Exception:
        pass

    return {
        "base_url": settings.chat.base_url,
        "api_key": settings.chat.api_key,
        "model_name": settings.chat.model_name,
        "api_format": "openai",
        "parameters": {},
    }


async def get_embedding_config(user_id: int) -> dict:
    """Get embedding model config for the user, falling back to .env defaults."""
    try:
        from app.dependencies import async_session_factory
        async with async_session_factory() as session:
            service = ModelConfigService(session)
            active = await service.get_active_model(user_id, "embedding")
            await session.commit()
            if active:
                return active
    except Exception:
        pass

    return {
        "base_url": settings.embedding.base_url,
        "api_key": settings.embedding.api_key,
        "model_name": settings.embedding.model_name,
        "parameters": {},
    }


async def get_mineru_config(user_id: int) -> dict:
    """Get MinerU document-parsing config, falling back to .env defaults."""
    try:
        from app.dependencies import async_session_factory
        async with async_session_factory() as session:
            service = ModelConfigService(session)
            active = await service.get_active_model(user_id, "mineru")
            await session.commit()
            if active:
                return active
    except Exception:
        pass

    return {
        "base_url": settings.mineru.base_url,
        "api_key": settings.mineru.token,
        "model_name": settings.mineru.model,
    }


async def get_reranker_config(user_id: int) -> dict:
    """Get reranker model config for the user, falling back to .env defaults."""
    try:
        from app.dependencies import async_session_factory
        async with async_session_factory() as session:
            service = ModelConfigService(session)
            active = await service.get_active_model(user_id, "reranker")
            await session.commit()
            if active:
                return active
    except Exception as e:
        logger.warning("Failed to load reranker config from DB: %s", e)

    return {
        "base_url": settings.reranker.base_url,
        "api_key": settings.reranker.api_key,
        "model_name": settings.reranker.model_name,
        "api_format": "openai",
        "parameters": {},
    }
