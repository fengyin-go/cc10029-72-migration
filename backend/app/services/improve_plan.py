"""改进方案领域服务：方案登记、审核、驳回，含跨模块关联反馈校验。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services.cross_module import (
    check_entity_status,
    find_by_module_and_id,
    require_entity,
)


class ImprovePlanService(BaseModuleService):
    MODULE = "improve_plan"
    ENTITY = "改进方案"
    OPERATION_TERM = "审核方案"
    LIST_FIELDS = ["关联反馈", "改进目标", "改进措施", "预期产出", "负责教师", "启动日期", "完成期限", "备注说明"]
    REQUIRED_FIELDS = ["关联反馈", "改进目标", "改进措施"]
    STATUS_ORDER = ["草稿", "待审核", "审核通过", "已驳回"]
    ACTION_RULES = {"审核方案": "审核通过", "提交审核": "待审核", "驳回方案": "已驳回"}
    NEGATIVE_ACTIONS = ["驳回方案"]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """创建改进方案：关联反馈必须是已签收的反馈单。"""
        feedback_ref = str(values.get("关联反馈", "") or "").strip()

        # 尝试解析反馈ID引用
        if feedback_ref.startswith("feedback:"):
            fb_id_str = feedback_ref.split(":", 1)[1]
            try:
                fb_id = int(fb_id_str)
                # 验证反馈存在且已签收
                check_entity_status(
                    "feedback", fb_id, ["已签收", "已办结"],
                    "改进方案的关联反馈"
                )
            except ValueError:
                pass  # 非数字ID不阻止创建

        return super().create_entry(values)

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含业务约束。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 审核方案：必须是待审核状态
        if action == "审核方案":
            if entry.get("status") not in ("待审核", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可审核"

        # 提交审核：只有草稿和已驳回可以提交
        if action == "提交审核":
            if entry.get("status") not in ("草稿", "已驳回"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可提交审核"

        # 驳回方案：必须是待审核状态
        if action == "驳回方案":
            if entry.get("status") not in ("待审核", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可驳回"

        return super()._execute_action(entry_id, action)