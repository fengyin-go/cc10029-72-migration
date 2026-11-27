"""受理回执台账：同一业务对象上的同一动作，只受理一次并复用第一份回执。

“分发/下达”这类动作会派生新的业务对象（诊改事项），用户在两个标签页里
各点一次时，不能让两次请求各生成一项工作。台账以
(模块, 对象编号, 动作编号) 为键，第一次请求生成回执并记录实际产出的对象，
后续请求（无论来自旧页面中文原词还是新版稳定编号）都读回同一份回执。

台账目录只在单进程内存里，和示例数据仓库同一生命周期；接口契约保持
可查询、可重复读取，换成数据库时替换这一层即可。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.action_contract import ActionSpec

_LOCK = threading.RLock()
_RECEIPTS: dict[str, dict[str, Any]] = {}
# 动作执行过程中先登记派生结果，动作成功返回后由 accept 合并进回执。
_STAGED_RESULTS: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def action_lock() -> threading.RLock:
    """把一次动作的校验、流转和回执写入放在同一把锁里。"""
    return _LOCK


def receipt_id(module: str, entry_id: int, action_id: str) -> str:
    return f"rcpt:{module}:{entry_id}:{action_id}"


def _key(module: str, entry_id: int, action_id: str) -> str:
    return receipt_id(module, entry_id, action_id)


def stage_result(
    module: str, entry_id: int, action_id: str, result: dict[str, Any]
) -> None:
    """登记本次动作实际派生的业务对象，供回执引用。"""
    with _LOCK:
        _STAGED_RESULTS[_key(module, entry_id, action_id)] = dict(result)


def get(module: str, entry_id: int, action_id: str) -> dict[str, Any] | None:
    with _LOCK:
        receipt = _RECEIPTS.get(_key(module, entry_id, action_id))
        return dict(receipt) if receipt else None


def find_by_id(value: str) -> dict[str, Any] | None:
    with _LOCK:
        for receipt in _RECEIPTS.values():
            if receipt["receipt_id"] == value:
                return dict(receipt)
    return None


def list_for(
    module: str | None = None,
    entry_id: int | None = None,
    action_id: str | None = None,
) -> list[dict[str, Any]]:
    with _LOCK:
        rows = [
            dict(receipt)
            for receipt in _RECEIPTS.values()
            if (module is None or receipt["module"] == module)
            and (entry_id is None or receipt["entry_id"] == entry_id)
            and (action_id is None or receipt["action_id"] == action_id)
        ]
    return sorted(rows, key=lambda item: item["first_request_at"])


def accept(
    module: str,
    entry_id: int,
    spec: ActionSpec,
    *,
    entry: dict[str, Any] | None = None,
    message: str = "",
    replay: bool = False,
) -> dict[str, Any]:
    """记录一次成功受理；只有重复请求复用回执时才标记 replayed。"""
    with _LOCK:
        key = _key(module, entry_id, spec.action_id)
        staged = _STAGED_RESULTS.pop(key, None)
        now = _now()
        receipt = _RECEIPTS.get(key)
        if receipt is None:
            result = staged or {
                "module": module,
                "entry_id": entry_id,
                "status": (entry or {}).get("status", ""),
            }
            receipt = {
                "receipt_id": key,
                "module": module,
                "entry_id": entry_id,
                "action_id": spec.action_id,
                "action_label": spec.label,
                "legacy_action": spec.legacy,
                "accepted": True,
                "replayed": False,
                "request_count": 1,
                "message": message,
                "result": result,
                "source": {
                    "module": module,
                    "entry_id": entry_id,
                },
                "first_request_at": now,
                "updated_at": now,
            }
            _RECEIPTS[key] = receipt
            return dict(receipt)

        receipt["request_count"] = int(receipt.get("request_count", 1)) + 1
        receipt["updated_at"] = now
        if replay:
            receipt["replayed"] = True
        if staged:
            # 第一次受理异常中断时，补齐实际派生对象；绝不覆盖已有结果。
            receipt.setdefault("result", staged)
        if message:
            receipt["message"] = message
        return dict(receipt)


def clear() -> None:
    """测试辅助：清空台账，不影响其他模块的示例数据。"""
    with _LOCK:
        _RECEIPTS.clear()
        _STAGED_RESULTS.clear()
