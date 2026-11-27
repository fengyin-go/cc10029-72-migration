"""模块服务基类：共享查询、登记、动作和统计骨架，业务差异留在各模块文件。"""
from __future__ import annotations

from typing import Any

from app import receipts
from app.action_contract import resolve_action, spec_for
from app.store import store


def _requested_label(spec: Any, action: object, action_id: object | None) -> str:
    """按调用方实际使用的名字回话：旧客户端看旧词，新客户端看新展示名。"""
    primary = str(action_id if action_id not in (None, "") else action or "").strip()
    if primary.casefold() in {spec.action_id.casefold(), spec.label.casefold()}:
        return spec.label
    if primary.casefold() == spec.legacy.casefold():
        return spec.legacy
    return spec.label


def _say(message: str, spec: Any, requested: str) -> str:
    """按调用方使用的名字回话：旧客户端仍看到旧原词。

    服务内部消息用当前展示名生成；旧页面提交原词时替换回原词，
    保证旧客户端读到的说明与它认识的动作一致。
    """
    if not message or requested == spec.label:
        return message
    return message.replace(spec.label, requested)


class BaseModuleService:
    MODULE = ""
    ENTITY = ""
    LIST_FIELDS: list[str] = []
    REQUIRED_FIELDS: list[str] = []
    STATUS_ORDER: list[str] = []
    ACTION_RULES: dict[str, str] = {}
    NEGATIVE_ACTIONS: list[str] = []

    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = list(store.rows(self.MODULE))
        for field, expected in (filters or {}).items():
            if field in self.LIST_FIELDS:
                rows = [
                    row for row in rows
                    if expected.casefold() in str(row.get(field, "")).casefold()
                ]
        if keyword and self.LIST_FIELDS:
            field = self.LIST_FIELDS[0]
            rows = [row for row in rows if keyword.casefold() in str(row.get(field, "")).casefold()]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = (page - 1) * size
        return [
            self.decorate_row(row) for row in rows[start:start + size]
        ], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(self.MODULE, entry_id)

    def decorate_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """列表/详情返回前的旁路信息；默认原样返回，派生模块按需补充来源。"""
        return row

    def detail_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = self.get_entry(entry_id)
        return self.decorate_row(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [
            field for field in self.REQUIRED_FIELDS
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return None, missing
        rows = store.rows(self.MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in self.LIST_FIELDS})
        entry["status"] = self.STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    # ------------------------------------------------------------------
    # 动作入口：先归一化到稳定动作编号，再在同一把锁里执行和写回执。
    # run_action 保持旧签名（两元组），供业务代码和既有调用方继续使用；
    # perform_action 额外返回动作契约和受理回执，供 HTTP 层使用。
    # ------------------------------------------------------------------
    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry, message, _spec, _receipt = self.perform_action(entry_id, action)
        return entry, message

    def perform_action(
        self,
        entry_id: int,
        action: object,
        action_id: object | None = None,
    ) -> tuple[dict[str, Any] | None, str, Any, dict[str, Any] | None]:
        """执行一次动作，返回 (实体, 说明, 动作契约, 受理回执)。"""
        spec = spec_for(self.MODULE, action_id) or spec_for(self.MODULE, action)
        if spec is None:
            # 保留原词，让业务层的“不属于可执行范围”提示与旧版一致。
            entry, message = self._execute_action(entry_id, str(action or "").strip())
            return entry, message, None, None

        replayable = spec.replayable
        requested = _requested_label(spec, action, action_id)
        with receipts.action_lock():
            if replayable:
                existing = receipts.get(self.MODULE, entry_id, spec.action_id)
                if existing is not None:
                    entry = self.get_entry(entry_id)
                    receipt = receipts.accept(
                        self.MODULE, entry_id, spec,
                        entry=entry, message=str(existing.get("message", "")),
                        replay=True,
                    )
                    message = str(existing.get("message", ""))
                    return (
                        self.decorate_row(entry) if entry is not None else None,
                        _say(message, spec, requested), spec, receipt,
                    )

            entry, message = self._execute_action(entry_id, spec.legacy)
            if entry is None:
                return None, _say(message, spec, requested), spec, None

            receipt = receipts.accept(
                self.MODULE, entry_id, spec, entry=entry, message=message,
            )
            return (
                self.decorate_row(entry),
                _say(message, spec, requested),
                spec,
                receipt,
            )

    def _execute_action(
        self, entry_id: int, action: str
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"
        target = self.ACTION_RULES.get(action)
        if target is None:
            return None, f"动作「{action}」不属于{self.MODULE}可执行范围"
        entry["status"] = target
        entry["pending"] = target != self.STATUS_ORDER[-1]
        entry["abnormal"] = action in self.NEGATIVE_ACTIONS
        return entry, f"{self.ENTITY}已{self._action_label(action)}"

    def _action_label(self, action: str) -> str:
        """当前版本的展示名；没有改名的动作与原词一致。"""
        spec = spec_for(self.MODULE, action)
        return spec.label if spec is not None else action

    def domain_snapshot(self) -> dict[str, Any]:
        """返回本模块的状态统计与业务对象，供其他模块读取。"""
        rows = store.rows(self.MODULE)
        by_status = {
            status: sum(1 for row in rows if row.get("status") == status)
            for status in self.STATUS_ORDER
        }
        return {
            "module": self.MODULE,
            "entity": self.ENTITY,
            "artifact": f"{self.ENTITY}状态记录",
            "count": len(rows),
            "by_status": by_status,
            "abnormal": sum(1 for row in rows if row.get("abnormal")),
        }


def resolve_module_action(module: str, action: object) -> str | None:
    """兼容旧调用：把编号/展示名/原词归一化成服务内部动作名。"""
    return resolve_action(module, action)
