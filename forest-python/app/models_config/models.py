from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    model_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "chat" / "embedding" / "reranker" / "mineru"
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 接入协议：openai（OpenAI 兼容 /chat/completions）或 anthropic（原生 /v1/messages）。
    # 注册卡片模型按卡片声明填充；自定义模型由添加时选定；存量行 NULL 视为 openai
    api_format: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    # 按模型卡片参数 schema 配置的推理参数（temperature/max_tokens/dimensions...）
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 备用模型：主模型调用失败（异常/首字节超时）时自动切换的同类型配置
    fallback_config_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
