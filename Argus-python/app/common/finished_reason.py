"""统一的流式结束原因，贯通 QA 与助手链路（借鉴 AgentScope 的 FinishedReason）。

流式端点的 done 事件统一携带 reason 字段；QA 落库复用 qa_messages.reason_code
列，助手落库写入 structured_payload.interrupted。
"""
from enum import StrEnum


class FinishedReason(StrEnum):
    COMPLETED = "completed"
    """正常完成。"""
    INTERRUPTED = "interrupted"
    """用户主动停止或客户端断开（部分内容已保留）。"""
    NO_EVIDENCE = "no_evidence"
    """检索无证据，QA 拒答。"""
    ERROR = "error"
    """LLM 调用失败。"""
