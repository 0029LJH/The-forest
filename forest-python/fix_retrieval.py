import re

filepath = r'D:\Ai应用工程师\RAG_agent\forest-python\app\qa\retrieval.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add rerank param to retrieve() signature
content = content.replace(
    '        user_id: int = 1,\n    ) -> RetrievedEvidenceBundle:',
    '        user_id: int = 1,\n        rerank: bool | None = None,\n    ) -> RetrievedEvidenceBundle:'
)

# 2. Pass rerank flag to _rerank_candidates
content = content.replace(
    'reranked = await self._rerank_candidates(question, ranked, user_id)',
    'reranked = await self._rerank_candidates(question, ranked, user_id, rerank)'
)

# 3. Update _rerank_candidates signature and add early-exit logic
old_rerank_sig = '''    async def _rerank_candidates(
        self, question: str, candidates: List[RetrievalCandidate],
        user_id: int,
    ) -> List[RetrievalCandidate]:'''
new_rerank_sig = '''    async def _rerank_candidates(
        self, question: str, candidates: List[RetrievalCandidate],
        user_id: int, rerank: bool | None = None,
    ) -> List[RetrievalCandidate]:
        """Rerank candidates using cross-encoder, with explicit enable/disable support.

        If rerank is None (default), check model config's rerank_enabled parameter.
        If rerank is True/False, use that directly (query-level override).
        """
        # Check if reranking is enabled
        from app.models_config.resolver import get_reranker_config
        from app.config import settings
        enabled = None
        if rerank is not None:
            enabled = rerank
        else:
            try:
                cfg = await get_reranker_config(user_id)
                params = cfg.get("parameters") or {}
                enabled = params.get("rerank_enabled", True)
            except Exception:
                enabled = True  # default on if config unavailable
        if not enabled:
            logger.info("Reranking disabled (rerank=%s, rerank_enabled=%s)", rerank, enabled)
            return candidates'''
content = content.replace(old_rerank_sig, new_rerank_sig)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('retrieval.py updated')
