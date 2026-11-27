"""教学档案领域服务：档案登记、审核归档、注销，含跨模块关联学期目标与外部评估。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services.cross_module import require_entity


class TeachRecordService(BaseModuleService):
    MODULE = "teach_record"
    ENTITY = "档案条目"
    OPERATION_TERM = "审核归档"
    LIST_FIELDS = ["教师姓名", "档案类型", "内容摘要", "存档日期", "关联学期", "录入人员", "保管期限", "备注说明"]
    REQUIRED_FIELDS = ["教师姓名", "档案类型", "内容摘要"]
    STATUS_ORDER = ["草稿", "待审核", "已归档", "已注销"]
    ACTION_RULES = {"审核归档": "已归档", "退回补正": "草稿", "注销档案": "已注销"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含业务约束与跨模块关联。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 审核归档：必须是待审核
        if action == "审核归档":
            if entry.get("status") not in ("待审核", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可归档"

        # 注销档案：必须先归档
        if action == "注销档案":
            if entry.get("status") != "已归档":
                return None, f"{self.ENTITY} {entry_id} 必须先审核归档，才能注销"

        # 退回补正：已归档后不能退回
        if action == "退回补正":
            if entry.get("status") in ("已归档", "已注销"):
                return None, f"{self.ENTITY} {entry_id} 已经{entry.get('status')}，不可退回补正"

        return super()._execute_action(entry_id, action)