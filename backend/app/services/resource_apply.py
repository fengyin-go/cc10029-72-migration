"""教学资源申请领域服务：申请登记、审批、归还，含资源使用时段冲突检测。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class ResourceApplyService(BaseModuleService):
    MODULE = "resource_apply"
    ENTITY = "资源申请"
    OPERATION_TERM = "审批领用"
    LIST_FIELDS = ["申请资源", "用途说明", "使用时间", "归还时间", "申请教师", "审批状态", "领取地点", "备注说明"]
    REQUIRED_FIELDS = ["申请资源", "用途说明", "使用时间"]
    STATUS_ORDER = ["草稿", "待审批", "已批准", "已归还"]
    ACTION_RULES = {"审批领用": "已批准", "退回申请": "草稿", "确认归还": "已归还"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """创建资源申请：检测同一资源同时间段的冲突。"""
        resource = str(values.get("申请资源", "") or "").strip()
        use_time = str(values.get("使用时间", "") or "").strip()

        if resource and use_time:
            for row in store.rows("resource_apply"):
                if (str(row.get("申请资源", "")).strip() == resource
                        and str(row.get("使用时间", "")).strip() == use_time
                        and row.get("status") in ("已批准", "待审批")):
                    raise ValueError(
                        f"资源冲突：{resource} 在 {use_time} 已被申请或批准"
                    )

        return super().create_entry(values)

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含状态约束。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 审批领用：必须是待审批
        if action == "审批领用":
            if entry.get("status") not in ("待审批", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可审批"

        # 确认归还：必须是已批准状态
        if action == "确认归还":
            if entry.get("status") != "已批准":
                return None, f"{self.ENTITY} {entry_id} 必须已批准，才能确认归还"

        return super()._execute_action(entry_id, action)