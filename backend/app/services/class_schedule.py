"""排课编排领域服务：排课单登记、确认、调整，含教师时段冲突检测。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class ClassScheduleService(BaseModuleService):
    MODULE = "class_schedule"
    ENTITY = "排课单"
    OPERATION_TERM = "确认排课"
    LIST_FIELDS = ["课程名称", "授课教师", "上课时间", "上课地点", "授课班级", "起止周次", "课时数量", "备注说明"]
    REQUIRED_FIELDS = ["课程名称", "授课教师", "上课时间"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已调整"]
    ACTION_RULES = {"确认排课": "已确认", "申请调整": "已调整", "执行调整": "已确认"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """创建排课单：检测教师和教室在同一时段的冲突。"""
        teacher = str(values.get("授课教师", "") or "").strip()
        time_slot = str(values.get("上课时间", "") or "").strip()
        classroom = str(values.get("上课地点", "") or "").strip()

        if teacher and time_slot:
            for row in store.rows("class_schedule"):
                if (str(row.get("授课教师", "")).strip() == teacher
                        and str(row.get("上课时间", "")).strip() == time_slot
                        and row.get("status") == "已确认"):
                    raise ValueError(
                        f"排课冲突：教师 {teacher} 在 {time_slot} 时段已有已确认的排课"
                    )

        if classroom and time_slot:
            for row in store.rows("class_schedule"):
                if (str(row.get("上课地点", "")).strip() == classroom
                        and str(row.get("上课时间", "")).strip() == time_slot
                        and row.get("status") == "已确认"):
                    raise ValueError(
                        f"教室冲突：{classroom} 在 {time_slot} 时段已被占用"
                    )

        return super().create_entry(values)

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 确认排课：必须是待确认
        if action == "确认排课":
            if entry.get("status") not in ("待确认", "草稿", "已调整"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可确认"

        return super()._execute_action(entry_id, action)