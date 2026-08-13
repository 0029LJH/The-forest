from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from app.engine.vector_store import PgVectorRetrievalAdapter, VectorHit
from app.engine.es_service import es_service, KeywordHit
from app.config import settings
from app.qa.query_planning import EvidenceLevel

logger = logging.getLogger(__name__)

CHANNEL_TOP_K = 50
# Standard RRF smoothing constant (originally 0 = pure 1/rank, which let a
# single-channel rank-1 hit dominate over multi-channel agreement)
RRF_K = 60
DEFAULT_NEIGHBOR_WINDOW = 1
FUSION_TOP_K = 8


@dataclass
class RetrievalCandidate:
    chunk_id: int
    document_id: int
    chunk_index: int
    chunk_text: str = ""
    vector_score: float = 0.0
    keyword_score: float = 0.0
    ranking_score: float = 0.0
    raw_similarity: float = 0.0  # actual cosine similarity before RRF


@dataclass
class EvidenceDocument:
    evidence_id: str
    content: str
    chunk_ids: List[int] = field(default_factory=list)
    source_file: str = ""
    evidence_level: str = ""
    rrf_score: float = 0.0
    document_id: int = 0
    chunk_id: int = 0


@dataclass
class RetrievedEvidenceBundle:
    documents: List[EvidenceDocument]
    evidence_level: EvidenceLevel
    evidence_guidance: str

    @classmethod
    def empty(cls):
        return cls(documents=[], evidence_level=EvidenceLevel.NONE, evidence_guidance="")


class HybridChunkRetrievalService:
    def __init__(self, vector_adapter: PgVectorRetrievalAdapter):
        self.vector_adapter = vector_adapter

    async def retrieve(self, group_id: int, question: str,
                       planned_queries: List[str], top_k: int = FUSION_TOP_K) -> RetrievedEvidenceBundle:
        candidates: Dict[int, RetrievalCandidate] = {}

        self._t0 = time.perf_counter()
        logger.info("Retrieval timing: enter retrieve (queries=%d)", len(planned_queries))
        # Run both retrieval channels for all planned queries concurrently.
        # Safe on one event loop: dict mutations are synchronous blocks with no
        # await between read-modify-write, so coroutines cannot interleave them.
        await asyncio.gather(*[
            asyncio.gather(
                self._merge_vector_hits(candidates, group_id, query),
                self._merge_keyword_hits(candidates, group_id, query),
            )
            for query in planned_queries
        ])

        logger.info("Retrieval timing: gather done in %.0fms",
                    (time.perf_counter() - self._t0) * 1000 if hasattr(self, "_t0") else 0)
        if not candidates:
            logger.info("Retrieval fusion: 0 candidates (both channels empty)")
            return RetrievedEvidenceBundle.empty()

        # 融合贡献统计：两通道各自命中、交集（RRF 中两通道都命中的 chunk 得分翻倍）
        v_only = sum(1 for c in candidates.values() if c.vector_score > 0 and c.keyword_score == 0)
        k_only = sum(1 for c in candidates.values() if c.vector_score == 0 and c.keyword_score > 0)
        both = sum(1 for c in candidates.values() if c.vector_score > 0 and c.keyword_score > 0)
        logger.info("Retrieval fusion: candidates=%d (vector_only=%d, es_only=%d, both=%d)",
                    len(candidates), v_only, k_only, both)

        ranked = sorted(candidates.values(), key=lambda c: c.ranking_score, reverse=True)
        ranked = ranked[:top_k]

        # Normalize RRF scores to 0-1 range (top hit = 1.0)
        if ranked:
            max_score = max(c.ranking_score for c in ranked)
            if max_score > 0:
                for c in ranked:
                    c.ranking_score = c.ranking_score / max_score

        clusters = self._build_clusters(ranked)

        # Fetch actual chunk text from DB (including neighbor windows)
        db_rows = await self._fetch_chunk_rows(group_id, ranked)

        documents = []
        for i, cluster in enumerate(clusters):
            doc = await self._build_document(f"E{i+1}", db_rows, cluster)
            if doc:
                documents.append(doc)

        evidence_level = self._assess_evidence(documents, ranked)
        guidance = self._build_guidance(evidence_level)

        return RetrievedEvidenceBundle(
            documents=documents,
            evidence_level=evidence_level,
            evidence_guidance=guidance,
        )

    async def _merge_vector_hits(self, candidates: dict, group_id: int, query: str):
        hits = await self.vector_adapter.search(group_id, query, CHANNEL_TOP_K)
        logger.info("Retrieval vector channel: query=%s hits=%d", query[:50], len(hits))
        for rank, hit in enumerate(hits, start=1):
            c = candidates.setdefault(hit.chunk_id, RetrievalCandidate(
                chunk_id=hit.chunk_id, document_id=hit.document_id,
                chunk_index=hit.chunk_index, chunk_text=hit.chunk_text,
            ))
            rrf_score = 1.0 / (RRF_K + rank)
            c.vector_score = max(c.vector_score, rrf_score)
            c.ranking_score += rrf_score
            c.raw_similarity = max(c.raw_similarity, hit.score)

    async def _merge_keyword_hits(self, candidates: dict, group_id: int, query: str):
        hits = await es_service.search(group_id, query, CHANNEL_TOP_K)
        logger.info("Retrieval ES channel: query=%s hits=%d", query[:50], len(hits))
        for rank, hit in enumerate(hits, start=1):
            c = candidates.setdefault(hit.chunk_id, RetrievalCandidate(
                chunk_id=hit.chunk_id, document_id=hit.document_id,
                chunk_index=hit.chunk_index, chunk_text=hit.chunk_text,
            ))
            rrf_score = 1.0 / (RRF_K + rank)
            c.keyword_score = max(c.keyword_score, rrf_score)
            c.ranking_score += rrf_score

    def _build_clusters(self, ranked: List[RetrievalCandidate]) -> List[List[RetrievalCandidate]]:
        if not ranked:
            return []
        clusters = []
        current_cluster = [ranked[0]]

        for c in ranked[1:]:
            prev = current_cluster[-1]
            if c.document_id == prev.document_id and c.chunk_index <= prev.chunk_index + DEFAULT_NEIGHBOR_WINDOW + 1:
                current_cluster.append(c)
            else:
                clusters.append(current_cluster)
                current_cluster = [c]

        clusters.append(current_cluster)
        return clusters

    async def _fetch_chunk_rows(self, group_id: int, ranked: List[RetrievalCandidate]) -> dict:
        from app.dependencies import async_session_factory
        from app.ingestion.models import DocumentChunk
        from app.document.models import Document
        from sqlalchemy import select, tuple_

        # Collect (document_id, chunk_index) windows around every ranked hit.
        # Neighbors must be looked up by index within the same document — the
        # global chunk_id is a shared sequence, so id±1 can cross documents.
        pairs = set()
        for c in ranked:
            for offset in range(-DEFAULT_NEIGHBOR_WINDOW, DEFAULT_NEIGHBOR_WINDOW + 1):
                idx = c.chunk_index + offset
                if idx >= 0:
                    pairs.add((c.document_id, idx))

        if not pairs:
            return {}

        # Inner join + exclude soft-deleted documents: leftover vectors of
        # deleted documents must never surface as evidence.
        async with async_session_factory() as session:
            result = await session.execute(
                select(DocumentChunk, Document.file_name)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(
                    tuple_(DocumentChunk.document_id, DocumentChunk.chunk_index).in_(pairs),
                    DocumentChunk.group_id == group_id,
                    Document.deleted == False,  # noqa: E712
                )
            )
            return {(row.document_id, row.chunk_index): (row, file_name or "未知文件")
                    for row, file_name in result}

    async def _build_document(self, evidence_id: str, db_rows: dict,
                              cluster: List[RetrievalCandidate]) -> Optional[EvidenceDocument]:
        if not cluster:
            return None

        # Expand with neighbor window (same document, adjacent chunk_index)
        valid_rows = {}
        for c in cluster:
            for offset in range(-DEFAULT_NEIGHBOR_WINDOW, DEFAULT_NEIGHBOR_WINDOW + 1):
                key = (c.document_id, c.chunk_index + offset)
                if key[1] >= 0 and key in db_rows and key not in valid_rows:
                    valid_rows[key] = db_rows[key]

        sorted_rows = sorted(valid_rows.items(), key=lambda kv: kv[0][1])
        content = "\n\n".join(row[0].chunk_text for _, row in sorted_rows if row[0].chunk_text)

        if not content.strip():
            return None

        # Get source file name, chunk index, and RRF score.
        # Prefer a valid row over the cluster head — the head may be a leftover
        # vector whose chunk row was deleted (file attribution would be wrong).
        entry = None
        for c in cluster:
            candidate = db_rows.get((c.document_id, c.chunk_index))
            if candidate is not None:
                entry = candidate
                break
        if entry is None:
            return None
        source_file = entry[1] or "未知文件"
        main_chunk_index = entry[0].chunk_index

        return EvidenceDocument(
            evidence_id=evidence_id,
            content=content,
            chunk_ids=[main_chunk_index],
            source_file=source_file,
            rrf_score=cluster[0].ranking_score,
            document_id=cluster[0].document_id,
            chunk_id=entry[0].id,
        )

    def _assess_evidence(self, documents: List[EvidenceDocument],
                         candidates: List[RetrievalCandidate]) -> EvidenceLevel:
        if not documents:
            return EvidenceLevel.NONE

        # Check if the content is actually semantically relevant
        max_raw_sim = max((c.raw_similarity for c in candidates), default=0)
        if max_raw_sim < 0.65:
            return EvidenceLevel.NONE  # vector similarity too low, content is irrelevant

        has_vector = any(c.vector_score > 0 for c in candidates)
        has_keyword = any(c.keyword_score > 0 for c in candidates)
        both = has_vector and has_keyword

        # Note: the former `top_score >= 0.85` clause was always true — ranking
        # scores are normalized (max = 1.0) before assessment — so it is removed
        if len(documents) >= 2 and (both or has_vector):
            return EvidenceLevel.SUFFICIENT
        elif both or len(documents) >= 2:
            return EvidenceLevel.PARTIAL
        else:
            return EvidenceLevel.WEAK

    def _build_guidance(self, level) -> str:
        """按证据等级生成强约束回答策略（与证据等级一起传入 LLM）。"""
        from app.qa.query_planning import EvidenceLevel
        if level == EvidenceLevel.SUFFICIENT:
            return "当前证据较充分，可以正常回答，但仍然不得超出证据进行臆测。"
        elif level == EvidenceLevel.PARTIAL:
            return "当前证据只覆盖部分问题，只能回答证据明确支持的部分，未覆盖部分必须明确说明不足。"
        elif level == EvidenceLevel.WEAK:
            return "当前证据相关性有限，只能谨慎回答，必须明确说明依据有限，不能给出确定性结论。"
        return "当前没有可用证据，必须直接拒答。"
