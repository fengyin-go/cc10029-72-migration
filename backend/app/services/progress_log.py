"""实施进展领域服务：进展记录、确认、延期，含跨模块关联方案与任务联动。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services.cross_module import require_entity


class ProgressLogService(BaseModuleService):
    MODULE = "progress_log"
    ENTITY = "进展记录"
    OPERATION_TERM = "确认进展"
    LIST_FIELDS = ["关联方案", "当前阶段", "完成情况", "遇到困难", "汇报日期", "汇报人员", "下一节点", "备注说明"]
    REQUIRED_FIELDS = ["关联方案", "当前阶段", "完成情况"]
    STATUS_ORDER = ["进行中", "待确认", "已确认", "已延期"]
    ACTION_RULES = {"确认进展": "已确认", "申请延期": "已延期", "标记完成": "已确认"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """创建进展记录：关联方案引用必须是已审核通过的改进方案。"""
        plan_ref = str(values.get("关联方案", "") or "").strip()
        if plan_ref.startswith("plan:"):
            plan_id_str = plan_ref.split(":", 1)[1]
            try:
                plan_id = int(plan_id_str)
                require_entity("improve_plan", plan_id, "进展记录的关联方案")
            except ValueError:
                pass

        return super().create_entry(values)

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含幂等与跨模块联动。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 确认进展的幂等保护
        if action == "确认进展":
            if entry.get("status") == "已确认":
                return None, f"{self.ENTITY} {entry_id} 已是已确认状态，无需重复确认"

        # 申请延期：已确认的不可延期
        if action == "申请延期":
            if entry.get("status") == "已确认":
                return None, f"{self.ENTITY} {entry_id} 已经确认，不可再申请延期"

        return super()._execute_action(entry_id, action)