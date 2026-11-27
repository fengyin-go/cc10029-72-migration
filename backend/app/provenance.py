"""来源溯源：派生对象（诊改事项、同行评议）始终能回到发起它的原业务对象。

派生行同时写入结构化的来源字段和旧格式的标记文本：
- 结构化字段（来源类型/来源编号/来源标签）给新页面和接口直接读取；
- 标记文本（如 [meeting:62]）保留在原有描述/意见字段里，旧页面和旧代码
  仍按原样搜索，不改读取方式。
"""
from __future__ import annotations

from typing import Any

from app.store import store

SOURCE_ENTITY = {
    "review_meeting": ("会议纪要", "会议主题"),
    "lesson_prep": ("备课记录", "备课章节"),
    "peer_review": ("评议表", "评议维度"),
    "feedback": ("反馈单", "反馈要点"),
    "improve_plan": ("改进方案", "改进目标"),
    "quality_report": ("质量简报", "覆盖学期"),
    "exam_analysis": ("分析记录", "考试名称"),
    "observation": ("观摩记录", "课程名称"),
}

# 旧版本写进文本里的标记词。新版本继续沿用，保证回切旧服务后仍能按原样去重。
LEGACY_TOKEN = {"review_meeting": "meeting"}


def marker_tokens(source_type: str) -> tuple[str, ...]:
    legacy = LEGACY_TOKEN.get(source_type)
    return (source_type,) if not legacy else (legacy, source_type)


def marker(source_type: str, source_id: int) -> str:
    """旧格式的来源标记，写到原有文本字段里（沿用旧标记词）。"""
    legacy = LEGACY_TOKEN.get(source_type, source_type)
    return f"[{legacy}:{source_id}]"


def find_derived(
    module: str,
    source_type: str,
    source_id: int,
    *,
    marker_fields: tuple[str, ...],
) -> dict[str, Any] | None:
    """在派生模块中查找已存在的同一来源对象（兼容只有文本标记的旧数据）。"""
    stamps = [f"[{token}:{source_id}]" for token in marker_tokens(source_type)]
    for row in store.rows(module):
        if (str(row.get("来源类型", "")) == source_type
                and str(row.get("来源编号", "")) == str(source_id)):
            return row
        for field in marker_fields:
            text = str(row.get(field, ""))
            if any(stamp in text for stamp in stamps):
                return row
    return None


def source_label(source_type: str, source_id: int, row: dict[str, Any] | None = None) -> str:
    """取原业务对象上适合展示给教师的短标签。"""
    row = row if row is not None else store.find(source_type, source_id)
    if row is None:
        return ""
    if source_type == "review_meeting":
        theme = str(row.get("会议主题", "")).strip()
        return theme or f"会议纪要 #{source_id}"
    if source_type == "lesson_prep":
        chapter = str(row.get("备课章节", "")).strip()
        return chapter or f"备课记录 #{source_id}"
    _, field = SOURCE_ENTITY.get(source_type, ("", ""))
    return str(row.get(field, "")).strip() or f"{source_type} #{source_id}"


def describe_source(
    source_type: str, source_id: int, row: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """把来源整理成接口可直接返回的结构；原对象缺失时仍保留引用信息。"""
    if not source_type or source_id is None:
        return None
    row = row if row is not None else store.find(source_type, source_id)
    entity, _ = SOURCE_ENTITY.get(source_type, (source_type, ""))
    return {
        "module": source_type,
        "entry_id": source_id,
        "entity": entity,
        "label": source_label(source_type, source_id, row),
        "status": str((row or {}).get("status", "")),
        "found": row is not None,
    }


def source_of_row(module: str, row: dict[str, Any]) -> dict[str, Any] | None:
    """从一行派生数据里解析来源；新字段优先，旧文本标记兜底。"""
    source_type = str(row.get("来源类型", "")).strip()
    raw_id = row.get("来源编号")
    if source_type and raw_id not in (None, ""):
        try:
            return describe_source(source_type, int(raw_id))
        except (TypeError, ValueError):
            return describe_source(source_type, 0) if source_type else None

    # 旧数据没有结构化字段，从描述/意见里的 [type:id] 标记还原。
    text_fields = (
        "任务描述", "评议意见", "反馈来源", "关联反馈", "决议事项", "备注说明",
    )
    for field in text_fields:
        text = str(row.get(field, ""))
        for kind in SOURCE_ENTITY:
            for token in marker_tokens(kind):
                stamp = f"[{token}:"
                index = text.find(stamp)
                if index == -1:
                    continue
                tail = text[index + len(stamp):]
                digits = ""
                for char in tail:
                    if char.isdigit():
                        digits += char
                    else:
                        break
                if digits:
                    return describe_source(kind, int(digits))
    return None


def attach_source(
    row: dict[str, Any],
    source_type: str,
    source_id: int,
    *,
    source_text: str | None = None,
    receipt: str | None = None,
) -> None:
    """给派生行写入结构化来源字段，并保留旧标记文本。"""
    row["来源类型"] = source_type
    row["来源编号"] = source_id
    row["来源标签"] = source_text or source_label(source_type, source_id)
    if receipt:
        row["来源受理回执"] = receipt
