"""模型卡片注册表（借鉴 AgentScope 的 ModelCard YAML 目录）。

卡片声明模型的元数据与 API 行为差异（请求/响应格式、维度、批量上限、
参数约束），替代散落在代码里的 if/else 特判：

- ``api.request_format`` / ``api.response_format`` 决定 embedding 适配器
  用哪种协议（dashscope 原生 / OpenAI 兼容）
- ``dimensions`` 声明支持向量维度，用于激活时与 pgvector 列校验
- ``batch_limit`` 声明 embedding 批大小上限
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CARDS_DIR = Path(__file__).parent / "cards"


class ApiFormat(str, Enum):
    OPENAI = "openai"
    DASHSCOPE = "dashscope"
    ANTHROPIC = "anthropic"


class ModelKind(str, Enum):
    CHAT = "chat"
    EMBEDDING = "embedding"


class CardApi(BaseModel):
    request_format: ApiFormat
    response_format: ApiFormat
    endpoint: Optional[str] = None
    base_url: Optional[str] = None
    """OpenAI 兼容接口的默认地址（前端选卡后自动填充表单）。"""
    dimension_param: bool = False
    """OpenAI 兼容接口是否支持请求体传 dimensions（如 text-embedding-3-*）。"""


class ModelCard(BaseModel):
    name: str
    label: str
    provider: str
    """厂商名（deepseek / dashscope / ...），前端按此分组展示。"""
    kind: ModelKind
    status: Literal["active", "deprecated"] = "active"
    description: str = ""
    api: CardApi
    context_size: int = 128000
    output_size: int = 8192
    dimensions: Optional[list[int]] = None
    batch_limit: Optional[int] = None
    parameters: dict = Field(default_factory=dict)
    """可调参数的 JSON Schema properties（title/type/default/min/max/enum），
    前端据此动态渲染参数表单（借鉴 AgentScope web_ui 的 ModelParametersPopover）。"""


_cache: Optional[dict[str, ModelCard]] = None


def load_cards(force: bool = False) -> dict[str, ModelCard]:
    """扫描 cards/ 目录并解析全部 YAML 卡片（进程内缓存）。"""
    global _cache
    if _cache is not None and not force:
        return _cache

    cards: dict[str, ModelCard] = {}
    for yaml_file in sorted(CARDS_DIR.glob("*.yaml")):
        try:
            card = ModelCard(**yaml.safe_load(yaml_file.read_text(encoding="utf-8")))
            cards[card.name] = card
        except Exception as e:
            logger.warning("Model card %s failed to load: %s", yaml_file.name, e)
    _cache = cards
    logger.info("Loaded %d model cards", len(cards))
    return cards


def get_card(name: str) -> Optional[ModelCard]:
    return load_cards().get(name)


def list_cards(kind: Optional[ModelKind] = None) -> list[ModelCard]:
    cards = list(load_cards().values())
    if kind is not None:
        cards = [c for c in cards if c.kind == kind]
    return cards


def card_form_schema(card: ModelCard) -> dict:
    """前端添加模型表单需要的展示信息。"""
    return {
        "name": card.name,
        "label": card.label,
        "provider": card.provider,
        "kind": card.kind.value,
        "status": card.status,
        "description": card.description,
        "contextSize": card.context_size,
        "outputSize": card.output_size,
        "dimensions": card.dimensions,
        "batchLimit": card.batch_limit,
        "parameters": card.parameters,
        "apiBaseUrl": card.api.base_url,
    }
