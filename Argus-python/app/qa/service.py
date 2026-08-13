import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select, update

from app.config import settings
from app.engine.vector_store import PgVectorRetrievalAdapter
from app.qa.models import QaSession, QaMessage
from app.qa.query_planning import QueryPlanningService, EvidenceLevel
from app.qa.retrieval import HybridChunkRetrievalService, RetrievedEvidenceBundle
from app.qa.citation import CitationAssembler
from app.metrics.collector import LlmUsageCollector, estimate_tokens, extract_usage_from_chunk

logger = logging.getLogger(__name__)


class QaService:
    def __init__(self):
        self._query_planning = QueryPlanningService()
        self._vector_adapter = PgVectorRetrievalAdapter(settings.database_url)

    async def ask(self, user_id: int, group_id: int, question: str,
                  session_id: Optional[int] = None) -> dict:
        start_time = time.perf_counter()

        # Query planning
        plan = await self._query_planning.plan(question, user_id)
        planned_queries = plan.get("queries", [question])
        logger.info("QA plan: strategy=%s, queries=%s", plan.get("strategy"), planned_queries)

        # Hybrid retrieval
        retrieval = HybridChunkRetrievalService(self._vector_adapter)
        bundle = await retrieval.retrieve(group_id, question, planned_queries)
        logger.info("Retrieved %d documents, level=%s", len(bundle.documents), bundle.evidence_level.value)

        # Assemble context
        citations = []
        for doc in bundle.documents:
            citations.append({"index": len(citations) + 1, "file_name": doc.source_file})

        MAX_EVIDENCE_CHARS = 4000
        evidence_text = ""
        for doc in bundle.documents:
            chunk = f"\n\n--- 证据 {doc.evidence_id} ---\n{doc.content}"
            if len(evidence_text) + len(chunk) > MAX_EVIDENCE_CHARS:
                remaining = MAX_EVIDENCE_CHARS - len(evidence_text)
                if remaining > 50:
                    evidence_text += chunk[:remaining] + "..."
                break
            evidence_text += chunk

        # LLM generation — use active model config if available
        from app.models_config.resolver import get_chat_config
        from app.models_config.fallback import build_chat_model_with_fallback
        chat_cfg = await get_chat_config(user_id)
        params = chat_cfg.get("parameters") or {}
        chat_model = await build_chat_model_with_fallback(
            user_id,
            streaming=False,
            temperature=params.get("temperature", settings.chat.temperature),
            max_tokens=params.get("max_tokens", 2048),
        )

        system_msg = """你是一个知识库智能助手，必须严格基于下方提供的证据内容回答问题。证据中的每条信息都是真实可靠的，直接引用证据中的具体内容来回答，不要自己编造或说"资料中没有"。不要在答案中写"证据E1"之类的编号。如果没有提供任何证据或证据等级为NONE，才可以说找不到相关信息。

回答规则：
1. 必须严格遵守下方"证据等级"和"证据指导"对应的回答策略：WEAK 只能谨慎回答并明确说明依据有限，不能给出确定性结论；PARTIAL 只能回答证据明确支持的部分，未覆盖部分必须明确说明不足；SUFFICIENT 可以正常回答但仍然不得超出证据臆测。
2. 如果问题包含多个子问题，只回答证据覆盖到的部分，未覆盖的子问题如实说明证据中没有相关内容。
3. 如果证据无法支持完整答案，优先保证准确，不要为了回答完整而编造。

用以下格式输出：
<<<ANSWER>>>
你的回答内容
<<<END>>>
<<<THINKING>>>
推理过程
<<<END>>>
<<<CITATIONS>>>
1,2
<<<END>>>"""

        user_msg = f"""证据等级：{bundle.evidence_level.value}
证据指导：{bundle.evidence_guidance}

证据内容：
{evidence_text}

问题：{question}

请基于证据回答问题。如果证据不足，请说明。"""

        response = await chat_model.ainvoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg),
        ])
        real_usage = extract_usage_from_chunk(response)

        # Parse delimiter-based response format
        raw = response.content.strip()
        logger.info("QA raw LLM response (first 200 chars): %s", raw[:200])
        answer, thinking, citation_nums = _parse_delimited_response(raw)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Build citations with actual snippets from retrieved evidence
        formatted_citations = []
        for i in citation_nums:
            idx = i - 1 if 0 <= i - 1 < len(bundle.documents) else -1
            if 0 <= idx < len(bundle.documents):
                doc = bundle.documents[idx]
                snippet = doc.content[:150] if len(doc.content) > 150 else doc.content
                formatted_citations.append({
                    "documentId": doc.document_id or None, "chunkId": doc.chunk_id or None,
                    "chunkIndex": doc.chunk_ids[0] if doc.chunk_ids else None,
                    "fileName": doc.source_file, "score": doc.rrf_score, "snippet": snippet.strip(),
                })

        if not answer or bundle.evidence_level == EvidenceLevel.NONE:
            reason_code = "NO_EVIDENCE" if bundle.evidence_level == EvidenceLevel.NONE else "LOW_CONFIDENCE"
            reason_message = "未检索到相关文档" if bundle.evidence_level == EvidenceLevel.NONE else "证据不足"
            await self._persist_session(user_id, group_id, question, "", [], reason_code, reason_message,
                                        session_id=session_id,
                                        evidence_level=bundle.evidence_level.value)
            await self._record_usage(user_id, group_id, "qa", "/api/qa/ask", 0, 0, True, is_estimated=False)
            return {
                "answered": False,
                "answer": None,
                "reasonCode": reason_code,
                "reasonMessage": reason_message,
                "citations": [],
            }

        await self._persist_session(user_id, group_id, question, answer, formatted_citations,
                                    None, None, thinking, session_id=session_id,
                                    evidence_level=bundle.evidence_level.value)
        if real_usage:
            await self._record_usage(user_id, group_id, "qa", "/api/qa/ask",
                real_usage["input_tokens"], real_usage["output_tokens"], True,
                model_name=chat_cfg["model_name"], is_estimated=False)
        else:
            await self._record_usage(user_id, group_id, "qa", "/api/qa/ask",
                estimate_tokens(evidence_text), estimate_tokens(answer), True,
                model_name=chat_cfg["model_name"])
        return {
            "answered": True,
            "answer": answer,
            "reasonCode": None,
            "reasonMessage": None,
            "citations": formatted_citations,
        }

    async def _persist_session(self, user_id: int, group_id: int, question: str,
                               answer: str, citations: list, reason_code: Optional[str],
                               reason_message: Optional[str], thinking: str = "",
                               session_id: Optional[int] = None,
                               evidence_level: Optional[str] = None) -> None:
        """Persist one Q&A round. With session_id, append to that session
        (verified to belong to the user); otherwise create a new one."""
        try:
            from app.dependencies import async_session_factory
            from app.common.time_utils import utcnow
            async with async_session_factory() as session:
                qa_session = None
                if session_id is not None:
                    result = await session.execute(
                        select(QaSession).where(
                            QaSession.id == session_id,
                            QaSession.user_id == user_id,
                        )
                    )
                    qa_session = result.scalar_one_or_none()

                if qa_session is None:
                    qa_session = QaSession(
                        user_id=user_id,
                        group_id=group_id,
                        title=question.strip()[:40],
                    )
                    session.add(qa_session)
                    await session.flush()
                else:
                    await session.execute(
                        update(QaSession)
                        .where(QaSession.id == qa_session.id)
                        .values(updated_at=utcnow())
                    )

                session.add(QaMessage(session_id=qa_session.id, role="USER", content=question))
                session.add(QaMessage(
                    session_id=qa_session.id,
                    role="ASSISTANT",
                    content=answer or "",
                    thinking=thinking or None,
                    citations=citations or None,
                    reason_code=reason_code,
                    reason_message=reason_message,
                    evidence_level=evidence_level,
                ))
                await session.commit()
        except Exception as e:
            # persistence must never break QA, but silent loss must not either
            logger.exception("QA session persistence failed: %s", e)

    async def _record_usage(self, user_id: int, group_id: int, module: str,
                            endpoint: str, prompt_tokens: int, completion_tokens: int,
                            success: bool, model_name: Optional[str] = None,
                            is_estimated: bool = True):
        from app.dependencies import async_session_factory
        try:
            async with async_session_factory() as session:
                collector = LlmUsageCollector(session)
                await collector.record(
                    user_id=user_id, group_id=group_id, module=module,
                    endpoint=endpoint, prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    success=success, is_estimated=is_estimated,
                    model_name=model_name or settings.chat.model_name,
                )
                await session.commit()
        except Exception as e:
            logger.exception("QA usage record failed: %s", e)

    async def ask_stream(self, user_id: int, group_id: int,
                         question: str, session_id: Optional[int] = None) -> AsyncIterator[dict]:
        start_time = time.perf_counter()

        # Query planning
        plan = await self._query_planning.plan(question, user_id)
        planned_queries = plan.get("queries", [question])
        logger.info("QA timing: plan done in %.0fms, queries=%s",
                    (time.perf_counter() - start_time) * 1000, planned_queries)

        # Hybrid retrieval
        retrieval = HybridChunkRetrievalService(self._vector_adapter)
        bundle = await retrieval.retrieve(group_id, question, planned_queries)
        logger.info("QA timing: retrieve done in %.0fms",
                    (time.perf_counter() - start_time) * 1000)

        # Assemble citations with snippets (only if evidence found)
        citations = []
        if bundle.evidence_level != EvidenceLevel.NONE:
            for doc in bundle.documents:
                snippet = doc.content[:150] if len(doc.content) > 150 else doc.content
                citations.append({
                    "index": len(citations) + 1,
                    "file_name": doc.source_file,
                    "snippet": snippet.strip(),
                    "chunkIndex": doc.chunk_ids[0] if doc.chunk_ids else None,
                    "score": doc.rrf_score,
                    "documentId": doc.document_id or None,
                    "chunkId": doc.chunk_id or None,
                })

        # Limit total evidence text to avoid overflowing model context window
        MAX_EVIDENCE_CHARS = 4000
        evidence_text = ""
        for doc in bundle.documents:
            chunk = f"\n\n--- 证据 {doc.evidence_id} ---\n{doc.content}"
            if len(evidence_text) + len(chunk) > MAX_EVIDENCE_CHARS:
                remaining = MAX_EVIDENCE_CHARS - len(evidence_text)
                if remaining > 50:
                    evidence_text += chunk[:remaining] + "..."
                break
            evidence_text += chunk

        # No evidence — short-circuit and report refusal instead of calling the LLM
        if bundle.evidence_level == EvidenceLevel.NONE:
            await self._persist_session(user_id, group_id, question, "", [], "NO_EVIDENCE",
                                        "未检索到相关文档", session_id=session_id,
                                        evidence_level=bundle.evidence_level.value)
            await self._record_usage(user_id, group_id, "qa", "/api/qa/stream-ask", 0, 0, True, is_estimated=False)
            yield {"event": "citations", "data": json.dumps({
                "citations": [],
                "thinking": "",
                "reasonCode": "NO_EVIDENCE",
                "reasonMessage": "未检索到相关文档",
            })}
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            yield {"event": "done", "data": json.dumps({"elapsed_ms": elapsed_ms})}
            return

        # LLM generation with streaming — use active model config if available
        from app.models_config.resolver import get_chat_config
        from app.models_config.fallback import build_chat_model_with_fallback
        chat_cfg = await get_chat_config(user_id)
        params = chat_cfg.get("parameters") or {}
        chat_model = await build_chat_model_with_fallback(
            user_id,
            streaming=True,
            temperature=params.get("temperature", settings.chat.temperature),
            max_tokens=params.get("max_tokens", 2048),
        )

        system_msg = """你是一个知识库智能助手，必须严格基于下方提供的证据内容回答问题。证据中的每条信息都是真实可靠的，直接引用证据中的具体内容来回答，不要自己编造或说"资料中没有"。不要在答案中写"证据E1"之类的编号。如果没有提供任何证据或证据等级为NONE，才可以说找不到相关信息。

回答规则：
1. 必须严格遵守下方"证据等级"和"证据指导"对应的回答策略：WEAK 只能谨慎回答并明确说明依据有限，不能给出确定性结论；PARTIAL 只能回答证据明确支持的部分，未覆盖部分必须明确说明不足；SUFFICIENT 可以正常回答但仍然不得超出证据臆测。
2. 如果问题包含多个子问题，只回答证据覆盖到的部分，未覆盖的子问题如实说明证据中没有相关内容。
3. 如果证据无法支持完整答案，优先保证准确，不要为了回答完整而编造。

用以下格式输出（严格按照标记，不要遗漏）：
<<<ANSWER>>>
你的回答内容
<<<END>>>
<<<THINKING>>>
推理过程
<<<END>>>
<<<CITATIONS>>>
1,2
<<<END>>>"""

        user_msg = f"""证据等级：{bundle.evidence_level.value}
证据内容：
{evidence_text}

问题：{question}"""

        parser = StreamingAnswerParser()
        answer_text = ""
        full_content = ""
        tail_text = ""
        stream_failed = False
        interrupted = False
        thinking_text = ""
        persisted_citations = []
        real_usage = None
        try:
            async for chunk in chat_model.astream([
                SystemMessage(content=system_msg),
                HumanMessage(content=user_msg),
            ]):
                usage = extract_usage_from_chunk(chunk)
                if usage:
                    real_usage = usage  # 末 chunk（空 content）携带真实用量
                if chunk.content:
                    full_content += chunk.content
                    delta = parser.push(chunk.content)
                    if delta:
                        answer_text += delta
                        yield {"event": "token", "data": json.dumps({"text": delta})}
        except asyncio.CancelledError:
            # 用户主动停止（前端 AbortController）：部分答案仍要落库
            interrupted = True
        except Exception as e:
            # GeneratorExit (client disconnect) is a BaseException, so it does
            # not land here — it propagates and only runs the finally block.
            logger.exception("QA stream LLM call failed: %s", e)
            stream_failed = True
            yield {"event": "error", "data": json.dumps({"message": str(e)})}
        finally:
            # Persist the round and record usage no matter how the stream
            # ended — a client disconnect used to skip both silently.
            tail_text = parser.flush()
            if tail_text:
                answer_text += tail_text
            if not answer_text and full_content.strip():
                # Delimiter tags missing entirely — fall back to off-line parse
                answer_text, _, _ = _parse_delimited_response(full_content.strip())
            logger.info("QA stream parsed answer (first 200 chars): %s", answer_text[:200])

            _, thinking_text, citation_nums = _parse_delimited_response(full_content.strip())
            # Mirror the non-streaming endpoint: only cite evidence the LLM
            # actually referenced in its <<<CITATIONS>>> section.
            for i in citation_nums:
                if 1 <= i <= len(citations):
                    c = citations[i - 1]
                    persisted_citations.append({
                        "documentId": c.get("documentId"),
                        "chunkId": c.get("chunkId"),
                        "chunkIndex": c.get("chunkIndex"),
                        "fileName": c["file_name"],
                        "score": c.get("score", 1.0),
                        "snippet": c.get("snippet"),
                    })
            await self._persist_session(user_id, group_id, question, answer_text,
                                        persisted_citations,
                                        "INTERRUPTED" if interrupted else None,
                                        "已停止生成" if interrupted else None,
                                        thinking_text,
                                        session_id=session_id,
                                        evidence_level=bundle.evidence_level.value)
            if real_usage:
                await self._record_usage(user_id, group_id, "qa", "/api/qa/stream-ask",
                    real_usage["input_tokens"], real_usage["output_tokens"],
                    success=not stream_failed,
                    model_name=chat_cfg["model_name"], is_estimated=False)
            else:
                await self._record_usage(user_id, group_id, "qa", "/api/qa/stream-ask",
                    estimate_tokens(evidence_text), estimate_tokens(answer_text),
                    success=not stream_failed,
                    model_name=chat_cfg["model_name"])

        if stream_failed:
            return

        if interrupted:
            # 客户端可能已断开，done 发不出去就静默放弃（落库已完成）
            try:
                yield {"event": "done", "data": json.dumps({
                    "elapsed_ms": int((time.perf_counter() - start_time) * 1000),
                    "reason": "interrupted",
                })}
            except Exception:
                pass
            return

        if tail_text:
            yield {"event": "token", "data": json.dumps({"text": tail_text})}
        if answer_text:
            yield {"event": "answer", "data": json.dumps({"text": answer_text})}
        yield {"event": "citations",
               "data": json.dumps({
                   "citations": persisted_citations,
                   "thinking": thinking_text,
               })}

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        yield {"event": "done", "data": json.dumps({"elapsed_ms": elapsed_ms, "reason": "completed"})}


class StreamingAnswerParser:
    """Streaming parser for the <<<ANSWER>>>...<<<END>>> delimiter format.

    Emits answer text as tokens arrive; holds back a short tail so a
    multi-token <<<END>>> tag is detected instead of leaking into the answer.
    Content after the answer section (THINKING/CITATIONS) is discarded.
    """

    ANSWER_TAG = "<<<ANSWER>>>"
    END_TAG = "<<<END>>>"

    def __init__(self):
        self._buffer = ""
        self._in_answer = False
        self._done = False

    def push(self, text: str) -> str:
        if self._done:
            return ""
        self._buffer += text

        if not self._in_answer:
            idx = self._buffer.find(self.ANSWER_TAG)
            if idx == -1:
                # Keep only the tail: the tag may span multiple chunks
                self._buffer = self._buffer[-len(self.ANSWER_TAG):]
                return ""
            self._buffer = self._buffer[idx + len(self.ANSWER_TAG):]
            self._in_answer = True

        end_idx = self._buffer.find(self.END_TAG)
        if end_idx != -1:
            self._done = True
            emit, self._buffer = self._buffer[:end_idx], ""
            return emit

        if len(self._buffer) <= len(self.END_TAG):
            return ""
        emit, self._buffer = self._buffer[:-len(self.END_TAG)], self._buffer[-len(self.END_TAG):]
        return emit

    def flush(self) -> str:
        if self._done or not self._in_answer:
            return ""
        self._done = True
        emit, self._buffer = self._buffer, ""
        return emit


def _parse_delimited_response(text: str) -> tuple:
    """Parse LLM response with <<<TAG>>>...<<<END>>> delimiters.
    Returns (answer, thinking, citation_numbers)."""
    import re

    def _extract(tag: str) -> str:
        pattern = rf"<<<{tag}>>>\s*(.*?)\s*<<<END>>>"
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else ""

    answer = _extract("ANSWER")
    thinking = _extract("THINKING")
    citations_raw = _extract("CITATIONS")

    citation_nums = []
    for part in re.split(r"[,\s]+", citations_raw):
        part = part.strip()
        if part.isdigit():
            citation_nums.append(int(part))

    if not answer:
        # Fallback: if no delimiters found, try old JSON format
        try:
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
            clean = clean.removeprefix("json").strip().strip("`").strip()
            parsed = json.loads(clean)
            answer = parsed.get("answer", "") or ""
            thinking = parsed.get("thinking", "")
            citation_nums = parsed.get("citations", [])
        except Exception:
            answer = text  # raw fallback

    return answer, thinking, citation_nums
