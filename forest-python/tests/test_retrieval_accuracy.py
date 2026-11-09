"""
Embedding vs Embedding+Rerank retrieval accuracy benchmark.
Run: TEST_GROUP_ID=36 python tests/test_retrieval_accuracy.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import List

# Load .env from project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists(os.path.join(_PROJECT_ROOT, ".env")):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

sys.path.insert(0, _PROJECT_ROOT)

from app.engine.vector_store import PgVectorRetrievalAdapter
from app.qa.retrieval import HybridChunkRetrievalService
from app.config import settings


@dataclass
class TestQuery:
    question: str
    expected_keywords: List[str]
    description: str = ""
    expected_doc_name: str = ""


# AI Knowledge test set (Group 36)
TEST_QUERIES_AI = [
    TestQuery(
        question="什么是 RAG 工程化？",
        expected_keywords=["RAG", "检索", "增强", "生成"],
        description="AI知识-RAG概念",
        expected_doc_name="RAG工程化常见问题",
    ),
    TestQuery(
        question="AI Agent 落地有哪些常见问题？",
        expected_keywords=["Agent", "落地", "问题"],
        description="AI知识-Agent落地",
        expected_doc_name="AI_Agent落地实践问题",
    ),
    TestQuery(
        question="大模型生产部署需要考虑什么？",
        expected_keywords=["大模型", "部署", "生产"],
        description="AI知识-部署问题",
        expected_doc_name="大模型生产部署问题",
    ),
    TestQuery(
        question="向量数据库的数据处理流程是什么？",
        expected_keywords=["向量", "数据库", "处理"],
        description="AI知识-向量库",
        expected_doc_name="数据处理与向量库问题",
    ),
    TestQuery(
        question="AI产品化迭代的最佳实践有哪些？",
        expected_keywords=["产品化", "迭代", "体验"],
        description="AI知识-产品化",
        expected_doc_name="AI产品化体验与迭代问题",
    ),
]

# Company policy test set (Group 37)
TEST_QUERIES_COMPANY = [
    TestQuery(
        question="差旅费用报销需要什么条件？",
        expected_keywords=["差旅", "报销", "费用"],
        description="公司制度-差旅报销",
        expected_doc_name="差旅费用报销管理办法",
    ),
    TestQuery(
        question="绩效考核的周期和标准是什么？",
        expected_keywords=["绩效", "考核", "薪酬"],
        description="公司制度-绩效考核",
        expected_doc_name="绩效考核与薪酬管理制度",
    ),
    TestQuery(
        question="员工休假有哪些类型？",
        expected_keywords=["休假", "考勤", "假期"],
        description="公司制度-休假管理",
        expected_doc_name="考勤与休假管理制度",
    ),
    TestQuery(
        question="公司信息安全管理要求有哪些？",
        expected_keywords=["信息", "安全", "保密"],
        description="公司制度-信息安全",
        expected_doc_name="信息安全与保密管理制度",
    ),
    TestQuery(
        question="新员工入职需要办理哪些手续？",
        expected_keywords=["招聘", "入职", "制度"],
        description="公司制度-招聘入职",
        expected_doc_name="招聘与入职管理制度",
    ),
]

# Legal query test set (Group 38)
TEST_QUERIES_LAW = [
    TestQuery(
        question="解除劳动合同有哪些情形？",
        expected_keywords=["劳动", "合同", "解除"],
        description="法律-劳动合同法",
        expected_doc_name="劳动合同法常见问题",
    ),
    TestQuery(
        question="民法典合同编有哪些重要条款？",
        expected_keywords=["民法典", "合同", "条款"],
        description="法律-民法典",
        expected_doc_name="民法典合同编关键条款",
    ),
    TestQuery(
        question="消费者权益保护有哪些规定？",
        expected_keywords=["消费者", "权益", "保护"],
        description="法律-消法",
        expected_doc_name="消费者权益保护法实用查询",
    ),
    TestQuery(
        question="行政诉讼的起诉期限是多久？",
        expected_keywords=["行政", "诉讼", "期限"],
        description="法律-行政诉讼",
        expected_doc_name="刑事与行政诉讼法实用查询",
    ),
    TestQuery(
        question="知识产权包括哪些类型？",
        expected_keywords=["知识产权", "专利", "商标"],
        description="法律-知识产权",
        expected_doc_name="知识产权法速查",
    ),
]


async def test_retrieval(group_id: int, query: TestQuery, rerank: bool, top_k: int = 5) -> dict:
    vector_adapter = PgVectorRetrievalAdapter(settings.database_url)
    retrieval_service = HybridChunkRetrievalService(vector_adapter)
    bundle = await retrieval_service.retrieve(
        group_id=group_id,
        question=query.question,
        planned_queries=[query.question],
        top_k=top_k,
        rerank=rerank,
    )
    return evaluate_results(bundle.documents, query)


def evaluate_results(documents: list, query: TestQuery) -> dict:
    results = {
        "top1_hit": False,
        "top3_hit": False,
        "top5_hit": False,
        "total_docs": len(documents),
        "relevant_docs": 0,
        "matched_doc_name": None,
    }
    for i, doc in enumerate(documents):
        content = doc.content.lower()
        is_relevant = any(kw.lower() in content for kw in query.expected_keywords)
        if is_relevant:
            results["relevant_docs"] += 1
            if i == 0:
                results["top1_hit"] = True
            if i < 3:
                results["top3_hit"] = True
            if i < 5:
                results["top5_hit"] = True
        if query.expected_doc_name and query.expected_doc_name in doc.source_file:
            results["matched_doc_name"] = doc.source_file
    return results


async def run_benchmark(group_id: int, test_queries: List[TestQuery]):
    print("=" * 60)
    print(f"Retrieval Accuracy Benchmark (Group ID: {group_id})")
    print("=" * 60)
    print(f"Test queries: {len(test_queries)}")
    print()

    embedding_stats = {"top1": 0, "top3": 0, "top5": 0, "total": len(test_queries)}
    rerank_stats = {"top1": 0, "top3": 0, "top5": 0, "total": len(test_queries)}
    details = []

    for i, query in enumerate(test_queries, 1):
        print(f"[{i}/{len(test_queries)}] {query.description}")
        print(f"  Q: {query.question}")

        emb_result = await test_retrieval(group_id, query, rerank=False)
        embedding_stats["top1"] += int(emb_result["top1_hit"])
        embedding_stats["top3"] += int(emb_result["top3_hit"])
        embedding_stats["top5"] += int(emb_result["top5_hit"])

        rerank_result = await test_retrieval(group_id, query, rerank=True)
        rerank_stats["top1"] += int(rerank_result["top1_hit"])
        rerank_stats["top3"] += int(rerank_result["top3_hit"])
        rerank_stats["top5"] += int(rerank_result["top5_hit"])

        details.append({"question": query.question, "embedding": emb_result, "rerank": rerank_result})

        print(f"  Embedding: Top1={emb_result['top1_hit']}, relevant={emb_result['relevant_docs']}")
        print(f"  Rerank:    Top1={rerank_result['top1_hit']}, relevant={rerank_result['relevant_docs']}")
        print()

    print("=" * 60)
    print("Summary")
    print("=" * 60)
    total = len(test_queries)
    print(f"\n{'Metric':<15} {'Embedding-only':<15} {'Embedding+Rerank':<15} {'Delta'}")
    print("-" * 55)
    metrics = [
        ("Top-1 Hit Rate", embedding_stats["top1"], rerank_stats["top1"]),
        ("Top-3 Hit Rate", embedding_stats["top3"], rerank_stats["top3"]),
        ("Top-5 Hit Rate", embedding_stats["top5"], rerank_stats["top5"]),
    ]
    for name, emb_val, rr_val in metrics:
        emb_pct = emb_val / total * 100
        rr_pct = rr_val / total * 100
        improvement = rr_pct - emb_pct
        print(f"{name:<12} {emb_pct:>6.1f}%          {rr_pct:>6.1f}%           {improvement:+.1f}%")

    print("\nDetail:")
    for d in details:
        emb = d["embedding"]
        rr = d["rerank"]
        status = "Rerank improved!" if emb["top1_hit"] != rr["top1_hit"] and rr["top1_hit"] else ""
        print(f"  {d['question'][:30]:<30} | Emb:{emb['top1_hit']} Rer:{rr['top1_hit']} {status}")


async def main():
    group_id_str = os.environ.get("TEST_GROUP_ID")
    if not group_id_str:
        print("Error: please set TEST_GROUP_ID environment variable")
        print("Example: $env:TEST_GROUP_ID=36; python tests/test_retrieval_accuracy.py")
        sys.exit(1)
    group_id = int(group_id_str)
    print(f"Starting test, group_id={group_id}")
    print()

    if group_id == 36:
        test_queries = TEST_QUERIES_AI
    elif group_id == 37:
        test_queries = TEST_QUERIES_COMPANY
    elif group_id == 38:
        test_queries = TEST_QUERIES_LAW
    else:
        print(f"Warning: unknown group_id {group_id}, using AI knowledge set")
        test_queries = TEST_QUERIES_AI

    await run_benchmark(group_id, test_queries)


if __name__ == "__main__":
    asyncio.run(main())
