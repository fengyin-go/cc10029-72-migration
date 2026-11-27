"""课程组编排领域服务：课程组登记、确认、解散，含成员变动约束。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService


class CourseGroupService(BaseModuleService):
    MODULE = "course_group"
    ENTITY = "课程组"
    OPERATION_TERM = "确认建组"
    LIST_FIELDS = ["组名", "覆盖课程", "组长教师", "成员名单", "成立学期", "活动周期", "本期主题", "备注说明"]
    REQUIRED_FIELDS = ["组名", "覆盖课程", "组长教师"]
    STATUS_ORDER = ["草稿", "待确认", "已建组", "已解散"]
    ACTION_RULES = {"确认建组": "已建组", "调整成员": "已建组", "解散课程组": "已解散"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 解散课程组：已解散的不能再次解散
        if action == "解散课程组":
            if entry.get("status") == "已解散":
                return None, f"{self.ENTITY} {entry_id} 已是已解散状态"
            if entry.get("status") not in ("已建组", "草稿", "待确认"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可解散"

        return super()._execute_action(entry_id, action)