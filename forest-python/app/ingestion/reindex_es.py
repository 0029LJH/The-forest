"""ES 索引重建维护脚本。

场景：ik 分词插件迁移（换镜像后删旧索引重建）、索引损坏/误删后，
从数据库 document_chunks 重建 ES 检索数据（文档无需重新上传）。

用法（在 forest-backend 目录）：
    conda run -n forest python -m app.ingestion.reindex_es              # 全部 READY 文档
    conda run -n forest python -m app.ingestion.reindex_es --doc 5      # 单个文档
    conda run -n forest python -m app.ingestion.reindex_es --dry-run    # 只预览不写入
"""
import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("reindex")


async def reindex(doc_id: int | None = None, dry_run: bool = False) -> None:
    from app.dependencies import async_session_factory
    from app.document.models import Document
    from app.ingestion.models import DocumentChunk
    from app.engine.es_service import es_service
    from sqlalchemy import select

    # 确保索引存在（新索引带 ik 分词 settings/mapping）
    await es_service.ensure_index()

    async with async_session_factory() as s:
        stmt = select(Document).where(
            Document.deleted == False,  # noqa: E712
            Document.status == "READY",
        ).order_by(Document.id)
        if doc_id is not None:
            stmt = stmt.where(Document.id == doc_id)
        docs = (await s.execute(stmt)).scalars().all()

        if not docs:
            logger.info("没有找到可重索引的 READY 文档")
            return

        total_chunks = 0
        for doc in docs:
            chunks = (await s.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index)
            )).scalars().all()
            if not chunks:
                logger.warning("文档 %s (%s) 无 chunks，跳过", doc.id, doc.file_name)
                continue
            if dry_run:
                logger.info("[dry-run] 文档 %s (%s): %d chunks", doc.id, doc.file_name, len(chunks))
            else:
                await es_service.index_chunks(doc.file_name, chunks)
                logger.info("✓ 文档 %s (%s): %d chunks 已写入 ES", doc.id, doc.file_name, len(chunks))
            total_chunks += len(chunks)

        logger.info("完成：%d 文档 / %d chunks%s", len(docs), total_chunks,
                    "（dry-run 未写入）" if dry_run else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="从 DB 重建 ES 检索索引")
    parser.add_argument("--doc", type=int, default=None, help="只重索引指定文档 ID")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入 ES")
    args = parser.parse_args()
    asyncio.run(reindex(doc_id=args.doc, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
