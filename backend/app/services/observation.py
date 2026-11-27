"""课堂观摩领域服务：观摩记录登记、提交、修改、归档，含状态联动和跨模块校验。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService


class ObservationService(BaseModuleService):
    MODULE = "observation"
    ENTITY = "观摩记录"
    OPERATION_TERM = "提交记录"
    LIST_FIELDS = ["教师姓名", "课程名称", "授课日期", "观摩节次", "教室编号", "观摩人员", "评分等级", "亮点摘要"]
    REQUIRED_FIELDS = ["教师姓名", "课程名称", "授课日期"]
    STATUS_ORDER = ["草稿", "待提交", "已提交", "已归档"]
    ACTION_RULES = {"提交记录": "已提交", "退回修改": "草稿", "归档记录": "已归档"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含状态联动约束。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 归档记录：必须是已提交的才能归档
        if action == "归档记录":
            if entry.get("status") not in ("已提交", "待提交"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，必须先提交再归档"
            if entry.get("status") == "已归档":
                return None, f"{self.ENTITY} {entry_id} 已是已归档状态，不可重复归档"

        # 退回修改：已归档后不能退回
        if action == "退回修改":
            if entry.get("status") in ("已提交", "已归档"):
                return None, f"{self.ENTITY} {entry_id} 已经{entry.get('status')}，不可退回修改"

        return super()._execute_action(entry_id, action)