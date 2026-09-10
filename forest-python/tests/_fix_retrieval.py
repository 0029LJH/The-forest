"""Fix retrieval.py: add rerank support."""
import re

path = r'D:\Ai应用工程师\RAG_agent\forest-python\app\qa\retrieval.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add rerank-related constants
content = content.replace(
    'FUSION_TOP_K = 8',
    'FUSION_TOP_K = 8\nRERANK_TOP_K = 6\nRERANK_THRESHOLD = 0.05'
)

# Add rerank_score field
content = content.replace(
    '    raw_similarity: float = 0.0  # actual cosine similarity before RRF',
    '    raw_similarity: float = 0.0\n    rerank_score: float = 0.0'
)

# Add rerank parameter to retrieve method
content = content.replace(
    '    async def retrieve(self, group_id: int, question: str,\n                       planned_queries: List[str], top_k: int = FUSION_TOP_K) -> RetrievedEvidenceBundle:',
    '    async def retrieve(self, group_id: int, question: str,\n                       planned_queries: List[str], top_k: int = FUSION_TOP_K,\n                       user_id: int = 1,\n                       rerank: bool | None = None) -> RetrievedEvidenceBundle:'
)

# Add _rerank_candidates method before _merge_vector_hits
rerank_method = '''
    async def _rerank_candidates(
        self, question: str, candidates: List[RetrievalCandidate],
        user_id: int, rerank: bool | None = None,
    ) -> List[RetrievalCandidate]:
        """Rerank candidates using cross-encoder, with explicit enable/disable support."""
        from app.models_config.resolver import get_reranker_config
        enabled = None
        if rerank is not None:
            enabled = rerank
        else:
            try:
                cfg = await get_reranker_config(user_id)
                params = cfg.get("parameters") or {}
                enabled = params.get("rerank_enabled", True)
            except Exception:
                enabled = True
        if not enabled:
            logger.info("Reranking disabled (rerank=%s, rerank_enabled=%s)", rerank, enabled)
            return candidates
        from app.qa.reranker import RerankerService
        pairs = [(c.chunk_id, c.chunk_text) for c in candidates]
        try:
            reranker = RerankerService()
            results = await reranker.rerank(question, pairs, user_id=user_id)
            await reranker.close()
        except Exception as e:
            logger.warning("Reranker failed, falling back to RRF order: %s", e)
            return candidates
        rerank_map = {r.chunk_id: r.score for r in results}
        for c in candidates:
            c.rerank_score = rerank_map.get(c.chunk_id, 0.0)
        kept = [c for c in candidates if c.rerank_score >= RERANK_THRESHOLD]
        if not kept:
            logger.info("Rerank: all %d candidates below threshold %.2f, keeping top RRF",
                        len(candidates), RERANK_THRESHOLD)
            return candidates[:RERANK_TOP_K]
        kept.sort(key=lambda c: c.rerank_score, reverse=True)
        logger.info("Rerank: %d -> %d kept (threshold=%.2f), top score=%.3f",
                    len(candidates), len(kept), RERANK_THRESHOLD, kept[0].rerank_score)
        return kept[:RERANK_TOP_K]

'''
content = content.replace(
    '    async def _merge_vector_hits(',
    rerank_method + '    async def _merge_vector_hits('
)

# Add reranking step after score normalization
old_block = '        clusters = self._build_clusters(ranked)'
new_block = '''        # Cross-encoder reranking
        reranked = await self._rerank_candidates(question, ranked, user_id, rerank)

        clusters = self._build_clusters(reranked)'''
content = content.replace(old_block, new_block)

# Update references from ranked to reranked
content = content.replace(
    '        db_rows = await self._fetch_chunk_rows(group_id, ranked)',
    '        db_rows = await self._fetch_chunk_rows(group_id, reranked)'
)
content = content.replace(
    '        evidence_level = self._assess_evidence(documents, ranked)',
    '        evidence_level = self._assess_evidence(documents, reranked)'
)

# Add rerank threshold check in _assess_evidence
old_assess = '''        has_vector = any(c.vector_score > 0 for c in candidates)
        has_keyword = any(c.keyword_score > 0 for c in candidates)
        both = has_vector and has_keyword

        # Note: the former `top_score >= 0.85` clause was always true'''
new_assess = '''        max_rerank = max((c.rerank_score for c in candidates), default=0)
        if max_rerank < RERANK_THRESHOLD:
            return EvidenceLevel.NONE

        has_vector = any(c.vector_score > 0 for c in candidates)
        has_keyword = any(c.keyword_score > 0 for c in candidates)
        both = has_vector and has_keyword

        # Note: the former `top_score >= 0.85` clause was always true'''
content = content.replace(old_assess, new_assess)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Updated retrieval.py, length: {len(content)}')
