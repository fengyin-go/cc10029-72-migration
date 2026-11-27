"""质量简报领域服务：简报登记、签收、传达，含跨模块触发复盘会议。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class QualityReportService(BaseModuleService):
    MODULE = "quality_report"
    ENTITY = "质量简报"
    OPERATION_TERM = "签收简报"
    LIST_FIELDS = ["覆盖学期", "教学质量概况", "突出问题", "改进方向", "编制部门", "发布日期", "发放范围", "备注说明"]
    REQUIRED_FIELDS = ["覆盖学期", "教学质量概况", "突出问题"]
    STATUS_ORDER = ["草稿", "待签收", "已签收", "已传达"]
    ACTION_RULES = {"签收简报": "已签收", "补充说明": "草稿", "传达到教师": "已传达"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含跨模块联动：签收时检查突出问题触发复盘会议。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 签收简报的幂等保护
        if action == "签收简报":
            if entry.get("status") == "已签收":
                return None, f"{self.ENTITY} {entry_id} 已是已签收状态，无需重复签收"

        # 传达到教师：必须先签收
        if action == "传达到教师":
            if entry.get("status") != "已签收":
                return None, f"{self.ENTITY} {entry_id} 必须先签收简报，才能传达"

        result_entry, message = super()._execute_action(entry_id, action)

        # 签收简报后，如果突出问题中存在严重问题，触发复盘会议
        if result_entry and action == "签收简报":
            problem = entry.get("突出问题", "")
            semester = entry.get("覆盖学期", "")
            if problem and ("严重" in str(problem) or "预警" in str(problem)):
                self._maybe_create_review_meeting(semester, problem, entry_id)

        return result_entry, message

    def _maybe_create_review_meeting(
        self, semester: str, problem: str, report_id: int
    ) -> None:
        """简报中存在严重问题时，自动触发复盘会议。"""
        meeting_rows = store.rows("review_meeting")
        # 幂等检查
        for row in meeting_rows:
            existing_source = str(row.get("决议事项", ""))
            if f"quality_report:{report_id}" in existing_source:
                return

        new_id = max((int(r.get("id", 0)) for r in meeting_rows), default=0) + 1
        meeting_rows.append({
            "id": new_id,
            "会议主题": f"{semester}学期质量简报突出问题复盘",
            "参会人员": "教研室主任、相关教师",
            "召开日期": "",
            "决议事项": f"针对简报中问题制定整改决议 [quality_report:{report_id}]",
            "分歧观点": "",
            "记录人员": "",
            "下次会议": "",
            "备注说明": "由质量简报签收后自动生成",
            "status": "待签认",
            "pending": True,
            "abnormal": False,
        })