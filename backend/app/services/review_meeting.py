"""复盘会议领域服务：会议纪要登记、签认、下达，含跨模块派发诊改事项。

“下达”在旧版叫“分发”。动作契约把两者归一化为 review_meeting.dispatch：
第一次受理生成一项诊改事项并留下回执，重复请求（旧页面改名前发出的、
或另一个标签页用新编号发出的）直接复用同一份回执和同一项工作。
"""
from __future__ import annotations

from typing import Any

from app import receipts
from app.action_contract import resolve_action, spec_for
from app.provenance import attach_source, find_derived, marker, source_label
from app.services.base import BaseModuleService
from app.store import store

DISPATCH_ACTION_ID = "review_meeting.dispatch"


class ReviewMeetingService(BaseModuleService):
    MODULE = "review_meeting"
    ENTITY = "会议纪要"
    OPERATION_TERM = "签认纪要"
    LIST_FIELDS = ["会议主题", "参会人员", "召开日期", "决议事项", "分歧观点", "记录人员", "下次会议", "备注说明"]
    REQUIRED_FIELDS = ["会议主题", "参会人员", "召开日期"]
    STATUS_ORDER = ["草稿", "待签认", "已签认", "已分发"]
    # 服务内部仍按旧原词分派；对外统一走 action_contract 的稳定编号。
    ACTION_RULES = {"签认纪要": "已签认", "提出异议": "草稿", "分发给教师": "已分发"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含跨模块联动：下达时派发诊改事项。"""
        action = resolve_action(self.MODULE, action) or action
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 签认纪要先通过待签认状态
        if action == "签认纪要":
            if entry.get("status") not in ("待签认", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可签认"

        # 下达（旧称分发）：必须先签认；重复下达由受理回执统一兜住。
        if action == "分发给教师":
            if entry.get("status") == "已分发":
                # 旧服务已经下达过、但没有留下回执时，补一份并沿用已派发的事项。
                self._maybe_create_improve_task(entry, entry_id)
                return entry, f"{self.ENTITY}已{self._action_label(action)}，沿用首次受理结果"
            if entry.get("status") != "已签认":
                return None, f"{self.ENTITY} {entry_id} 必须先签认纪要，才能下达"

        result_entry, message = super()._execute_action(entry_id, action)

        if result_entry is not None:
            message = f"{self.ENTITY}已{self._action_label(action)}"

        # 下达时，检查决议事项是否需要派发诊改事项
        if result_entry and action == "分发给教师":
            self._maybe_create_improve_task(entry, entry_id)

        return result_entry, message

    def _maybe_create_improve_task(
        self, entry: dict[str, Any], meeting_id: int
    ) -> None:
        """根据会议决议派发诊改事项：幂等保护，不重复创建。"""
        resolution = str(entry.get("决议事项", "") or "")
        if not resolution or "任务" not in resolution:
            return

        receipt = receipts.get(self.MODULE, meeting_id, DISPATCH_ACTION_ID)
        receipt_key = (
            (receipt or {}).get("receipt_id")
            or receipts.receipt_id(self.MODULE, meeting_id, DISPATCH_ACTION_ID)
        )
        existing = find_derived(
            "improve_task", "review_meeting", meeting_id,
            marker_fields=("任务描述", "备注说明"),
        )
        if existing is not None:
            existing.setdefault("来源受理回执", receipt_key)
            self._record_derived_task(existing, meeting_id, receipt)
            return

        task_rows = store.rows("improve_task")
        new_id = max((int(r.get("id", 0)) for r in task_rows), default=0) + 1
        label = source_label("review_meeting", meeting_id, entry)
        task = {
            "id": new_id,
            "任务描述": f"会议决议：{entry.get('会议主题', '')} {marker('review_meeting', meeting_id)}",
            "承接方案": resolution,
            "执行人员": "",
            "起止日期": "",
            "验收标准": "",
            "督办人员": "",
            "任务权重": "",
            "备注说明": "由复盘会议决议自动生成",
            "status": "待认领",
            "pending": True,
            "abnormal": False,
        }
        attach_source(
            task, "review_meeting", meeting_id,
            source_text=label,
            receipt=receipt_key,
        )
        task_rows.append(task)
        self._record_derived_task(task, meeting_id, receipt)

    def _record_derived_task(
        self,
        task: dict[str, Any],
        meeting_id: int,
        receipt: dict[str, Any] | None,
    ) -> None:
        """把实际派发的诊改事项写进受理回执，供两个页面查回同一结果。"""
        receipts.stage_result(
            self.MODULE, meeting_id, DISPATCH_ACTION_ID,
            {
                "module": "improve_task",
                "entry_id": int(task.get("id", 0)),
                "task_no": f"improve_task:{task.get('id')}",
                "status": str(task.get("status", "")),
                "label": str(task.get("来源标签", "")),
                "receipt_id": (receipt or {}).get(
                    "receipt_id",
                    receipts.receipt_id(self.MODULE, meeting_id, DISPATCH_ACTION_ID),
                ),
            },
        )

    def pending_items(self) -> list[dict[str, Any]]:
        """返回“已签认待下达”的纪要待办，教师据此回到原会议。"""
        spec = spec_for(self.MODULE, DISPATCH_ACTION_ID)
        rows: list[dict[str, Any]] = []
        for row in store.rows(self.MODULE):
            if row.get("status") != "已签认":
                continue
            entry_id = int(row.get("id", 0))
            rows.append({
                "module": self.MODULE,
                "entity": self.ENTITY,
                "entry_id": entry_id,
                "title": str(row.get("会议主题", "")),
                "status": row.get("status"),
                "action": {
                    "action_id": spec.action_id if spec else DISPATCH_ACTION_ID,
                    "label": spec.label if spec else "下达",
                    "legacy": spec.legacy if spec else "分发给教师",
                },
                "receipt": receipts.get(self.MODULE, entry_id, DISPATCH_ACTION_ID),
                "source": {
                    "module": self.MODULE,
                    "entry_id": entry_id,
                    "label": str(row.get("会议主题", "")),
                },
            })
        return rows
