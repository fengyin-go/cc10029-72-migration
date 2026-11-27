"""学期目标领域服务：目标登记、审定、废止，含同学期冲突检测和师徒结对关联。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class SemesterGoalService(BaseModuleService):
    MODULE = "semester_goal"
    ENTITY = "学期目标"
    OPERATION_TERM = "审定目标"
    LIST_FIELDS = ["目标描述", "量化指标", "责任教师", "起始学期", "截止学期", "当前完成度", "上级目标", "备注说明"]
    REQUIRED_FIELDS = ["目标描述", "量化指标", "责任教师"]
    STATUS_ORDER = ["草稿", "待审定", "已审定", "已废止"]
    ACTION_RULES = {"审定目标": "已审定", "退回修订": "草稿", "废止目标": "已废止"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """创建学期目标：检查同一责任教师 + 同一学期是否有冲突的已审定目标。"""
        teacher = str(values.get("责任教师", "") or "").strip()
        semester = str(values.get("起始学期", "") or "").strip()

        if teacher and semester:
            existing = store.rows("semester_goal")
            for row in existing:
                if (str(row.get("责任教师", "")).strip() == teacher
                        and str(row.get("起始学期", "")).strip() == semester
                        and row.get("status") == "已审定"):
                    raise ValueError(
                        f"学期目标冲突：教师 {teacher} 在 {semester} 学期已有已审定的目标，"
                        f"不能重复创建同教师同学期的目标"
                    )

        return super().create_entry(values)

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含冲突检测。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 审定目标前再次检查冲突
        if action == "审定目标":
            teacher = entry.get("责任教师", "")
            semester = entry.get("起始学期", "")
            if teacher and semester:
                for row in store.rows("semester_goal"):
                    if (int(row.get("id", 0)) != entry_id
                            and str(row.get("责任教师", "")).strip() == str(teacher).strip()
                            and str(row.get("起始学期", "")).strip() == str(semester).strip()
                            and row.get("status") == "已审定"):
                        return None, (
                            f"学期目标冲突：教师 {teacher} 在 {semester} 学期已有另一个已审定的目标，"
                            f"不能同时审定 "
                        )

            if entry.get("status") not in ("待审定", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可审定"

        # 废止目标：必须是已审定
        if action == "废止目标":
            if entry.get("status") != "已审定":
                return None, f"{self.ENTITY} {entry_id} 必须先审定，才能废止"

        return super()._execute_action(entry_id, action)