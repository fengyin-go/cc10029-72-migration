"""教学反馈领域服务：反馈单登记、签收、办结，含跨模块校验。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services.cross_module import check_entity_status, require_entity


class FeedbackService(BaseModuleService):
    MODULE = "feedback"
    ENTITY = "反馈单"
    OPERATION_TERM = "签收反馈"
    LIST_FIELDS = ["反馈对象", "反馈要点", "改进建议", "反馈来源", "接收教师", "反馈日期", "处理期限", "备注说明"]
    REQUIRED_FIELDS = ["反馈对象", "反馈要点", "改进建议"]
    STATUS_ORDER = ["草稿", "待签收", "已签收", "已办结"]
    ACTION_RULES = {"签收反馈": "已签收", "退回重提": "草稿", "确认办结": "已办结"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """创建反馈单，并校验跨模块引用：若反馈来源包含观摩ID，验证观摩记录存在。"""
        # 如果反馈来源引用了具体的观摩记录ID，需要验证
        feedback_source = str(values.get("反馈来源", "") or "")
        if feedback_source.startswith("observation:"):
            obs_id_str = feedback_source.split(":", 1)[1]
            try:
                obs_id = int(obs_id_str)
                require_entity("observation", obs_id, "反馈单的观摩来源")
            except ValueError:
                pass  # 非数字ID不校验

        return super().create_entry(values)

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含幂等和跨模块校验。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 签收反馈的幂等保护：已签收的不再重复签收
        if action == "签收反馈":
            if entry.get("status") == "已签收":
                return None, f"{self.ENTITY} {entry_id} 已是已签收状态，无需重复签收"
            if entry.get("status") == "已办结":
                return None, f"{self.ENTITY} {entry_id} 已办结，不可再签收"

        # 退回重提：已签收后不能退回
        if action == "退回重提":
            if entry.get("status") in ("已签收", "已办结"):
                return None, f"{self.ENTITY} {entry_id} 已经{entry.get('status')}，不可退回重提"

        # 确认办结：必须先签收
        if action == "确认办结":
            if entry.get("status") != "已签收":
                return None, f"{self.ENTITY} {entry_id} 必须先签收反馈，才能确认办结"

        return super()._execute_action(entry_id, action)