"""教学成果申报领域服务：申报登记、初审、上报，含申报等级和审核进度约束。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService


class TeachAwardService(BaseModuleService):
    MODULE = "teach_award"
    ENTITY = "成果申报"
    OPERATION_TERM = "初审申报"
    LIST_FIELDS = ["成果名称", "完成团队", "成果概要", "佐证材料", "申报等级", "申报日期", "审核进度", "备注说明"]
    REQUIRED_FIELDS = ["成果名称", "完成团队", "成果概要"]
    STATUS_ORDER = ["草稿", "待初审", "初审通过", "已上报"]
    ACTION_RULES = {"初审申报": "初审通过", "退回补全": "草稿", "上报评审": "已上报"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含状态约束。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 初审申报：必须是待初审
        if action == "初审申报":
            if entry.get("status") not in ("待初审", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可初审"

        # 上报评审：必须先初审通过
        if action == "上报评审":
            if entry.get("status") != "初审通过":
                return None, f"{self.ENTITY} {entry_id} 必须先初审通过，才能上报"

        # 退回补全：不能退回已上报的
        if action == "退回补全":
            if entry.get("status") in ("初审通过", "已上报"):
                return None, f"{self.ENTITY} {entry_id} 已经{entry.get('status')}，不可退回补全"

        return super()._execute_action(entry_id, action)