import json
import logging
import uuid
from typing import List, Optional
from dataclasses import dataclass

import httpx
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "rag_document_chunks"


async def _resolve_embedding() -> tuple[dict, "object | None"]:
    """返回 (embedding 配置 dict, 模型卡片)。激活配置优先，失败回退 .env。"""
    from app.models_config.resolver import get_embedding_config
    from app.models_config.cards import get_card

    s = settings.embedding
    cfg = {"base_url": s.base_url, "api_key": s.api_key, "model_name": s.model_name}
    try:
        active = await get_embedding_config(1)
        if active:
            cfg = active
    except Exception:
        pass
    return cfg, get_card(cfg["model_name"])


async def _embed_texts(texts: List[str], user_id: int = None) -> List[List[float]]:
    """Call embedding API, using active model config if available.

    请求/响应协议由模型卡片声明（api.request_format / api.response_format）；
    未注册的模型按 base_url 推断（含 dashscope → 原生协议）。
    """
    import time
    _t0 = time.perf_counter()
    from app.models_config.cards import ApiFormat

    cfg, card = await _resolve_embedding()
    api_key = cfg["api_key"]
    model_name = cfg["model_name"]
    api_url = cfg["base_url"]
    logger.info("Embedding timing: config ready in %.0fms, sending %d texts (model=%s)",
                (time.perf_counter() - _t0) * 1000, len(texts), model_name)

    if card is not None:
        use_native = card.api.request_format == ApiFormat.DASHSCOPE
    else:
        use_native = "dashscope" in (api_url or "") or not api_url

    # 维度优先级：配置 parameters.dimensions > 卡片默认 > .env 默认
    dimension = (cfg.get("parameters") or {}).get("dimensions")
    if not dimension and card and card.dimensions:
        dimension = card.dimensions[0]
    if not dimension:
        dimension = settings.embedding.dimensions

    if use_native:
        endpoint = (card.api.endpoint if card else None) or (
            "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
        )
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                endpoint,
                json={
                    "model": model_name,
                    "input": {"texts": texts},
                    "parameters": {"dimension": dimension},
                },
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.error("Embedding API error: %s %s", resp.status_code, resp.text[:500])
                raise RuntimeError(f"Embedding API returned {resp.status_code}: {resp.text[:200]}")
            body = resp.json()
            embeddings = body.get("output", {}).get("embeddings", [])
            embeddings.sort(key=lambda d: d.get("text_index", 0))
            return [e["embedding"] for e in embeddings]

    # OpenAI-compatible API：data[] 按 index 排序（此前误按 dashscope 的
    # output.embeddings/text_index 解析，非 dashscope 端点必崩 IndexError）
    url = (api_url or settings.embedding.base_url).rstrip("/") + "/embeddings"
    payload = {"model": model_name, "input": texts}
    # 支持 dimensions 的模型（如 text-embedding-3-*）需显式传维度，
    # 否则 API 返回默认维度，与激活校验所选维度不一致导致检索失效
    if dimension and card is not None and card.api.dimension_param:
        payload["dimensions"] = dimension
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            logger.error("Embedding API error: %s %s", resp.status_code, resp.text[:500])
            raise RuntimeError(f"Embedding API returned {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        items = body.get("data") or []
        items.sort(key=lambda d: d.get("index", 0))
        return [e["embedding"] for e in items]


@dataclass
class VectorHit:
    document_id: int
    chunk_id: int
    chunk_index: int
    chunk_text: str
    score: float


class PgVectorRetrievalAdapter:
    def __init__(self, connection_string: str):
        pass

    async def ensure_table(self) -> None:
        from app.dependencies import engine
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
                    id SERIAL PRIMARY KEY,
                    collection_id UUID,
                    embedding vector,
                    document VARCHAR,
                    cmetadata JSONB,
                    custom_id VARCHAR
                )
            """))
            # HNSW 要求固定维度：历史表是无维度 vector，迁移为 vector(N)
            col_type = (await conn.execute(text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid='langchain_pg_embedding'::regclass AND attname='embedding'"
            ))).scalar()
            if col_type == "vector":
                # 从数据推断维度（配置可能过期，以实际数据为准）
                dim = (await conn.execute(text(
                    "SELECT array_length(embedding::real[], 1) "
                    "FROM langchain_pg_embedding LIMIT 1"
                ))).scalar()
                if dim:
                    await conn.execute(text(
                        f"ALTER TABLE langchain_pg_embedding "
                        f"ALTER COLUMN embedding TYPE vector({dim})"
                    ))
                    logger.info("Migrated embedding column to vector(%s)", dim)

            # 向量 HNSW 索引：把 O(n) 全表距离扫描降到对数级近邻搜索
            # （pgvector 0.5+；幂等，启动时自动补齐）
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_lpe_embedding_hnsw "
                "ON langchain_pg_embedding USING hnsw (embedding vector_cosine_ops)"
            ))
            # cmetadata GIN 索引：加速 WHERE cmetadata->>'group_id' = :gid 过滤
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_lpe_cmetadata_gin "
                "ON langchain_pg_embedding USING gin (cmetadata)"
            ))
        logger.info("PGVector table ensured: %s", COLLECTION_NAME)

    async def search(self, group_id: int, question: str, top_k: int = 50) -> List[VectorHit]:
        from app.dependencies import engine

        # Get query embedding
        vectors = await _embed_texts([question])
        query_vector = "[" + ",".join(str(v) for v in vectors[0]) + "]"

        async with engine.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT document, cmetadata,
                           1 - (embedding <=> CAST(:emb AS vector)) AS similarity
                    FROM langchain_pg_embedding
                    WHERE cmetadata->>'group_id' = :gid
                    ORDER BY embedding <=> CAST(:emb AS vector)
                    LIMIT :lim
                """),
                {"emb": query_vector, "gid": str(group_id), "lim": top_k},
            )
            rows = result.all()

        hits = []
        for row in rows:
            metadata = row.cmetadata or {}
            try:
                doc_id = int(metadata.get("document_id", 0))
                chunk_id = int(metadata.get("chunk_id", 0))
                chunk_index = int(metadata.get("chunk_index", 0))
            except (ValueError, TypeError):
                continue
            if not row.document:
                continue

            hits.append(VectorHit(
                document_id=doc_id,
                chunk_id=chunk_id,
                chunk_index=chunk_index,
                chunk_text=row.document.strip(),
                score=float(row.similarity),
            ))

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    async def add_documents(self, documents: list) -> List[str]:
        from app.dependencies import engine

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        collection_id = uuid.uuid4()

        # 批大小上限以模型卡片 batch_limit 为准（如 text-embedding-v4 限 10），
        # 兜底 settings.ingestion.vector_add_batch_size
        batch_limit = 10
        try:
            _, card = await _resolve_embedding()
            if card and card.batch_limit:
                batch_limit = card.batch_limit
        except Exception:
            pass
        batch_size = max(1, min(settings.ingestion.vector_add_batch_size, batch_limit))
        all_vectors = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_vectors = await _embed_texts(batch)
            all_vectors.extend(batch_vectors)

        async with engine.begin() as conn:
            for content, metadata, vector in zip(texts, metadatas, all_vectors):
                vector_str = "[" + ",".join(str(v) for v in vector) + "]"
                await conn.execute(
                    text("""
                        INSERT INTO langchain_pg_embedding
                            (collection_id, embedding, document, cmetadata)
                        VALUES
                            (:cid, CAST(:vec AS vector), :doc, CAST(:meta AS jsonb))
                    """),
                    {
                        "cid": collection_id,
                        "vec": vector_str,
                        "doc": content,
                        "meta": json.dumps(metadata),
                    },
                )

        logger.info("Added %d vectors to PGVector", len(documents))
        return [str(i) for i in range(len(documents))]

    async def delete_by_document_ids(self, document_ids: List[int]) -> None:
        from app.dependencies import engine
        # cmetadata stores document_id as a JSON string — quote to avoid
        # "operator does not exist: text = integer" (which used to silently
        # fail and leave orphan vectors behind)
        id_list = ", ".join(f"'{did}'" for did in document_ids)
        async with engine.begin() as conn:
            await conn.execute(
                text(f"DELETE FROM langchain_pg_embedding WHERE cmetadata->>'document_id' IN ({id_list})")
            )
        logger.info("Deleted vectors for documents: %s", document_ids)
