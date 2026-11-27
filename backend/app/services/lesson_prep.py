"""集体备课领域服务：备课记录登记、签阅、存档，含跨模块触发同行评议。

签阅会派生评议邀请。重复签阅同样不能各生成一份邀请，因此这里用同一套
受理台账 + 来源标记保证幂等，并让评议邀请能回到发起它的原备课记录
（签阅出处），无论从旧页面还是新页面发起都能查回。
"""
from __future__ import annotations

from typing import Any

from app import receipts
from app.action_contract import resolve_action
from app.provenance import attach_source, find_derived, marker, source_label
from app.services.base import BaseModuleService
from app.store import store

SIGN_ACTION_ID = "lesson_prep.sign"


class LessonPrepService(BaseModuleService):
    MODULE = "lesson_prep"
    ENTITY = "备课记录"
    OPERATION_TERM = "签阅记录"
    LIST_FIELDS = ["备课章节", "主备教师", "参与教师", "备课日期", "研讨要点", "教学资源", "课后反思", "备注说明"]
    REQUIRED_FIELDS = ["备课章节", "主备教师", "参与教师"]
    STATUS_ORDER = ["草稿", "待签阅", "已签阅", "已存档"]
    ACTION_RULES = {"签阅记录": "已签阅", "补充意见": "草稿", "存档记录": "已存档"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含跨模块联动：签阅后可触发同行评议。"""
        action = resolve_action(self.MODULE, action) or action
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 签阅记录的幂等保护
        if action == "签阅记录":
            if entry.get("status") == "已签阅":
                return None, f"{self.ENTITY} {entry_id} 已是已签阅状态，无需重复签阅"

        result_entry, message = super()._execute_action(entry_id, action)

        # 签阅完成后，检查是否需要触发同行评议
        if result_entry and action == "签阅记录":
            self._maybe_create_peer_review(entry, entry_id)

        return result_entry, message

    def _maybe_create_peer_review(
        self, entry: dict[str, Any], prep_id: int
    ) -> None:
        """根据备课课后反思创建同行评议请求：幂等且可回溯原备课。"""
        reflection = str(entry.get("课后反思", "") or "")
        if not reflection or not ("改进" in reflection or "评议" in reflection):
            return

        receipt = receipts.get(self.MODULE, prep_id, SIGN_ACTION_ID)
        receipt_key = (
            (receipt or {}).get("receipt_id")
            or receipts.receipt_id(self.MODULE, prep_id, SIGN_ACTION_ID)
        )
        existing = find_derived(
            "peer_review", "lesson_prep", prep_id,
            marker_fields=("评议意见", "备注说明"),
        )
        if existing is not None:
            existing.setdefault("签阅出处回执", receipt_key)
            self._record_derived_review(existing, prep_id)
            return

        review_rows = store.rows("peer_review")
        new_id = max((int(r.get("id", 0)) for r in review_rows), default=0) + 1
        teacher = entry.get("主备教师", "")
        label = source_label("lesson_prep", prep_id, entry)
        review = {
            "id": new_id,
            "被评教师": teacher,
            "评议维度": "备课教学质量",
            "得分": "",
            "评议意见": (
                f"由备课记录 #{prep_id} 课后反思触发 {marker('lesson_prep', prep_id)}"
            ),
            "评议人员": "",
            "评议日期": "",
            "是否匿名": "否",
            "备注说明": "备课签阅后自动生成评议请求",
            "status": "待汇总",
            "pending": True,
            "abnormal": False,
            "签阅出处回执": receipt_key,
        }
        attach_source(
            review, "lesson_prep", prep_id,
            source_text=label,
            receipt=receipt_key,
        )
        review_rows.append(review)
        self._record_derived_review(review, prep_id)

    def _record_derived_review(self, review: dict[str, Any], prep_id: int) -> None:
        """签阅回执记下实际派生的评议邀请，两个页面都查回同一个结论。"""
        receipts.stage_result(
            self.MODULE, prep_id, SIGN_ACTION_ID,
            {
                "module": "peer_review",
                "entry_id": int(review.get("id", 0)),
                "review_no": f"peer_review:{review.get('id')}",
                "status": str(review.get("status", "")),
                "label": str(review.get("来源标签", "")),
                "receipt_id": review.get(
                    "签阅出处回执",
                    receipts.receipt_id(self.MODULE, prep_id, SIGN_ACTION_ID),
                ),
            },
        )

    def decorate_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """备课记录列表带出签阅回执，教师点开就能看到派生的评议邀请。"""
        enriched = dict(row)
        receipt = receipts.get(self.MODULE, int(row.get("id", 0)), SIGN_ACTION_ID)
        if receipt is not None:
            enriched["签阅回执"] = receipt["receipt_id"]
        return enriched

    def pending_items(self) -> list[dict[str, Any]]:
        """返回“待签阅”的备课待办。"""
        rows: list[dict[str, Any]] = []
        for row in store.rows(self.MODULE):
            if row.get("status") != "待签阅":
                continue
            entry_id = int(row.get("id", 0))
            rows.append({
                "module": self.MODULE,
                "entity": self.ENTITY,
                "entry_id": entry_id,
                "title": str(row.get("备课章节", "")),
                "status": row.get("status"),
                "receipt": receipts.get(self.MODULE, entry_id, SIGN_ACTION_ID),
                "source": {
                    "module": self.MODULE,
                    "entry_id": entry_id,
                    "label": str(row.get("备课章节", "")),
                },
            })
        return rows
