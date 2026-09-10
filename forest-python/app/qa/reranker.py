# DashScope Reranker API (OpenAI compatible format)
# POST /v1/chat/completions
# body: { "model": "gte-rerank-v2", "input": {"query": "...", "documents": [...]}} }
# response: { "output": {"results": [{"index": 0, "score": 0.92}, ...]} }

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx

from app.config import settings
from app.models_config.cards import get_card
from app.models_config.resolver import get_reranker_config

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    chunk_id: int
    score: float
    rank: int


class RerankerService:
    """Cross-encoder reranker service. Calls DashScope / Ollama reranker API."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def rerank(
        self,
        question: str,
        candidates: List[Tuple[int, str]],  # [(chunk_id, chunk_text), ...]
        user_id: int = 1,
    ) -> List[RerankResult]:
        """Rerank candidates by (question, chunk) relevance.

        Returns sorted list of RerankResult by score descending.
        Falls back to identity ranking on any error.
        """
        if not candidates:
            return []

        cfg, card = await self._resolve_config(user_id)
        api_key = cfg["api_key"]
        model_name = cfg["model_name"]
        api_url = cfg.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        # Build prompt pairs
        query = question
        documents = [text for _, text in candidates]
        chunk_ids = [cid for cid, _ in candidates]

        # Batch into groups of batch_limit
        batch_limit = (card.batch_limit if card else None) or 8
        results_by_index: dict[int, float] = {}

        for batch_start in range(0, len(documents), batch_limit):
            batch_docs = documents[batch_start:batch_start + batch_limit]
            batch_ids = chunk_ids[batch_start:batch_start + batch_limit]

            try:
                scores = await self._call_api(api_url, api_key, model_name, query, batch_docs)
                for i, score in enumerate(scores):
                    idx = batch_start + i
                    if idx < len(chunk_ids):
                        results_by_index[idx] = score
            except Exception as e:
                logger.warning("Reranker batch %d-%d failed: %s", batch_start, batch_start + len(batch_docs), e)
                # Fallback: assign neutral score
                for i in range(len(batch_docs)):
                    idx = batch_start + i
                    if idx not in results_by_index:
                        results_by_index[idx] = 0.5

        # Build results
        ranked = []
        for idx, score in sorted(results_by_index.items(), key=lambda x: -x[1]):
            ranked.append(RerankResult(
                chunk_id=chunk_ids[idx],
                score=float(score),
                rank=len(ranked) + 1,
            ))
        return ranked

    async def _call_api(
        self, api_url: str, api_key: str, model_name: str,
        query: str, documents: List[str],
    ) -> List[float]:
        """Call reranker API and return scores aligned with input order."""
        url = api_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model_name,
            "query": query,
            "documents": documents,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()

        # Parse response — DashScope OpenAI-compatible format
        output = body.get("output", {})
        results = output.get("results", [])

        scores = []
        for r in results:
            idx = r.get("index", 0)
            score = r.get("relevance_score", r.get("score", 0.0))
            # Pad with neutral score if indices are sparse
            while len(scores) <= idx:
                scores.append(0.5)
            scores[idx] = float(score)

        # Fill any missing positions
        while len(scores) < len(documents):
            scores.append(0.5)

        return scores[:len(documents)]

    async def _resolve_config(
        self, user_id: int
    ) -> Tuple[dict, "object | None"]:
        """Get reranker config, falling back to .env defaults."""
        from app.models_config.cards import get_card

        cfg = {
            "base_url": settings.reranker.base_url,
            "api_key": settings.reranker.api_key,
            "model_name": settings.reranker.model_name,
        }
        try:
            active = await get_reranker_config(user_id)
            if active:
                cfg = active
        except Exception:
            pass
        card = get_card(cfg["model_name"])
        return cfg, card
