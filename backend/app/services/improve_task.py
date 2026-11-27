"""诊改任务领域服务：任务分解、认领、执行、验收，含跨模块关联方案校验。"""
from __future__ import annotations

from typing import Any

from app import receipts
from app.action_contract import resolve_action
from app.provenance import describe_source, source_of_row
from app.services.base import BaseModuleService
from app.services.cross_module import check_entity_status
from app.store import store


class ImproveTaskService(BaseModuleService):
    MODULE = "improve_task"
    ENTITY = "诊改任务"
    OPERATION_TERM = "认领任务"
    LIST_FIELDS = ["任务描述", "承接方案", "执行人员", "起止日期", "验收标准", "督办人员", "任务权重", "备注说明"]
    REQUIRED_FIELDS = ["任务描述", "承接方案", "执行人员"]
    STATUS_ORDER = ["草稿", "待认领", "执行中", "已验收"]
    ACTION_RULES = {"认领任务": "执行中", "启动执行": "执行中", "申请验收": "已验收"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """创建诊改任务：承接方案引用必须是已审核通过的改进方案。"""
        source_plan = str(values.get("承接方案", "") or "").strip()

        # 尝试解析方案ID引用
        if source_plan.startswith("plan:"):
            plan_id_str = source_plan.split(":", 1)[1]
            try:
                plan_id = int(plan_id_str)
                check_entity_status(
                    "improve_plan", plan_id, ["审核通过"],
                    "诊改任务的承接方案"
                )
            except ValueError:
                pass

        return super().create_entry(values)

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含状态推进约束。"""
        action = resolve_action(self.MODULE, action) or action
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 认领任务：只能从待认领状态认领
        if action == "认领任务":
            if entry.get("status") not in ("待认领", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可认领"

        # 申请验收：必须已在执行中
        if action == "申请验收":
            if entry.get("status") != "执行中":
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，必须先执行再申请验收"

        return super()._execute_action(entry_id, action)

    def decorate_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """认领前就能看到原会议/原备课：列表和详情都带出处。"""
        enriched = dict(row)
        source = None
        if row.get("来源类型"):
            source = describe_source(str(row["来源类型"]), int(row.get("来源编号") or 0))
        if source is None:
            source = source_of_row(self.MODULE, row)
        if source is not None:
            enriched["来源"] = source
            # 外层字段给列表直接显示“来源会议/来源备课”。
            enriched["原业务对象"] = source.get("label", "")
            enriched["原业务编号"] = f"{source.get('module')}:{source.get('entry_id')}"
        return enriched

    def pending_items(self) -> list[dict[str, Any]]:
        """待认领的诊改事项待办，带上原会议/原备课。"""
        rows: list[dict[str, Any]] = []
        for row in store.rows(self.MODULE):
            if row.get("status") != "待认领":
                continue
            enriched = self.decorate_row(row)
            receipt = None
            if row.get("来源受理回执"):
                receipt = receipts.find_by_id(str(row["来源受理回执"]))
            rows.append({
                "module": self.MODULE,
                "entity": self.ENTITY,
                "entry_id": int(row.get("id", 0)),
                "title": str(row.get("任务描述", "")),
                "status": row.get("status"),
                "source": enriched.get("来源"),
                "receipt": receipt,
                "receipt_id": row.get("来源受理回执"),
            })
        return rows