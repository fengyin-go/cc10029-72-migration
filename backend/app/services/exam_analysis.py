"""试卷分析领域服务：分析记录登记、审核、存档，含跨模块触发改进方案。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class ExamAnalysisService(BaseModuleService):
    MODULE = "exam_analysis"
    ENTITY = "分析记录"
    OPERATION_TERM = "审核分析"
    LIST_FIELDS = ["考试名称", "任课教师", "参考人数", "平均得分", "难度系数", "区分度", "分析日期", "备注说明"]
    REQUIRED_FIELDS = ["考试名称", "任课教师", "参考人数"]
    STATUS_ORDER = ["草稿", "待审核", "审核通过", "已存档"]
    ACTION_RULES = {"审核分析": "审核通过", "退回重填": "草稿", "存档分析": "已存档"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含跨模块联动：审核通过时检查是否需要触发改进方案。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 审核分析：只在待审核时可以
        if action == "审核分析":
            if entry.get("status") not in ("待审核", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可审核"

        result_entry, message = super()._execute_action(entry_id, action)

        # 审核通过后发现薄弱点，触发改进方案
        if result_entry and action == "审核分析":
            difficulty = entry.get("难度系数", "")
            notes = entry.get("备注说明", "")
            try:
                diff_val = float(str(difficulty)) if difficulty else 0
                if diff_val > 0.5:
                    self._maybe_create_improve_plan(entry, diff_val, entry_id)
            except (ValueError, TypeError):
                pass

        return result_entry, message

    def _maybe_create_improve_plan(
        self, exam_entry: dict[str, Any], difficulty: float, analysis_id: int
    ) -> None:
        """试卷难度过高时，自动触发改进方案创建。"""
        plan_rows = store.rows("improve_plan")
        # 幂等检查
        for row in plan_rows:
            existing_source = str(row.get("关联反馈", ""))
            if f"exam:{analysis_id}" in existing_source:
                return

        new_id = max((int(r.get("id", 0)) for r in plan_rows), default=0) + 1
        teacher = exam_entry.get("任课教师", "")
        exam_name = exam_entry.get("考试名称", "")
        plan_rows.append({
            "id": new_id,
            "关联反馈": f"exam:{analysis_id}",
            "改进目标": f"降低{exam_name}难度系数至合理范围",
            "改进措施": f"当前难度系数{difficulty}偏大，需调整教学策略和考核方式",
            "预期产出": "",
            "负责教师": teacher,
            "启动日期": "",
            "完成期限": "",
            "备注说明": "由试卷分析审核通过后自动生成",
            "status": "待审核",
            "pending": True,
            "abnormal": False,
        })