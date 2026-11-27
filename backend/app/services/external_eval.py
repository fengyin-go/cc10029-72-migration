"""外部评估领域服务：评估报告登记、接收、转办，含跨模块关联学期目标和教学档案。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class ExternalEvalService(BaseModuleService):
    MODULE = "external_eval"
    ENTITY = "评估报告"
    OPERATION_TERM = "接收报告"
    LIST_FIELDS = ["评估机构", "评估指标", "评估结论", "出具日期", "接收部门", "整改要求", "有效期至", "备注说明"]
    REQUIRED_FIELDS = ["评估机构", "评估指标", "评估结论"]
    STATUS_ORDER = ["草稿", "待接收", "已接收", "已转办"]
    ACTION_RULES = {"接收报告": "已接收", "退回补充": "草稿", "转办整改": "已转办"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含跨模块联动。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 接收报告：必须是待接收
        if action == "接收报告":
            if entry.get("status") not in ("待接收", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可接收"

        # 转办整改：必须先接收
        if action == "转办整改":
            if entry.get("status") != "已接收":
                return None, f"{self.ENTITY} {entry_id} 必须先接收报告，才能转办"

        return super()._execute_action(entry_id, action)