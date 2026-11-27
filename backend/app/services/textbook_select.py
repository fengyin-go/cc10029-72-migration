"""教材选用领域服务：选用单登记、审核、订购，含跨学期教材冲突检测。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class TextbookSelectService(BaseModuleService):
    MODULE = "textbook_select"
    ENTITY = "选用单"
    OPERATION_TERM = "审核选用"
    LIST_FIELDS = ["教材名称", "主编", "出版社", "适用课程", "选用理由", "选用学期", "审批结果", "备注说明"]
    REQUIRED_FIELDS = ["教材名称", "主编", "出版社"]
    STATUS_ORDER = ["草稿", "待审核", "审核通过", "已订购"]
    ACTION_RULES = {"审核选用": "审核通过", "退回重选": "草稿", "确认订购": "已订购"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """创建选用单：同一课程 + 同一学期不能重复选用。"""
        course = str(values.get("适用课程", "") or "").strip()
        semester = str(values.get("选用学期", "") or "").strip()

        if course and semester:
            for row in store.rows("textbook_select"):
                if (str(row.get("适用课程", "")).strip() == course
                        and str(row.get("选用学期", "")).strip() == semester
                        and row.get("status") in ("审核通过", "待审核")):
                    raise ValueError(
                        f"教材冲突：{course} 在 {semester} 学期已有选用的教材"
                    )

        return super().create_entry(values)

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含状态约束。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 确认订购：必须先审核通过
        if action == "确认订购":
            if entry.get("status") != "审核通过":
                return None, f"{self.ENTITY} {entry_id} 必须先审核通过，才能订购"

        return super()._execute_action(entry_id, action)