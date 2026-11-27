"""统一资源接口：查询、导出、登记和动作按模块 key 分派到领域服务。"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app import receipts
from app.action_contract import action_catalog
from app.provenance import describe_source, source_of_row
from app.schemas import ActionPayload, ActionResult, EntryPayload, PageResult
from app.services import SERVICES, service_for

router = APIRouter(prefix="/api", tags=["业务资源"])


def require_service(module: str):
    service = service_for(module)
    if service is None:
        raise HTTPException(status_code=404, detail=f"未知业务模块：{module}")
    return service


# 固定路径的 GET 必须注册在 /{module} 之前，否则会被动态路径抢先匹配。


@router.get("/actions/catalog")
def list_actions() -> dict[str, object]:
    """动作目录：稳定编号、当前展示名和旧原词的对照表。

    新版前端从这里取展示名和编号；旧客户端不需要调用，仍按原词直接提交。
    """
    return {"modules": action_catalog()}


@router.get("/todos", response_model=list[dict])
def list_todos(module: str | None = Query(default=None)) -> list[dict[str, Any]]:
    """教师待办：从收到的待办直接查到原会议/原备课以及已有回执。

    待办里的动作同时给出稳定编号和旧原词，新旧页面都能用自己认识的写法回填。
    """
    if module is not None and service_for(module) is None:
        raise HTTPException(status_code=404, detail=f"未知业务模块：{module}")
    services = [service_for(module)] if module else list(SERVICES.values())

    todos: list[dict[str, Any]] = []
    for service in services:
        if service is None:
            continue
        provider = getattr(service, "pending_items", None)
        if callable(provider):
            todos.extend(provider())
    return todos


@router.get("/receipts/{receipt_id}", response_model=dict)
def get_receipt(receipt_id: str) -> dict[str, Any]:
    receipt = receipts.find_by_id(receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail=f"受理回执 {receipt_id} 不存在")
    return receipt


@router.get("/{module}", response_model=PageResult[dict])
def list_entries(
    module: str,
    request: Request,
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
) -> PageResult[dict]:
    service = require_service(module)
    filters = {
        key: value.strip()
        for key, value in request.query_params.items()
        if key in service.LIST_FIELDS and value.strip()
    }
    items, total = service.list_entries(
        filters=filters, keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{module}/export")
def export_entries(
    module: str,
    request: Request,
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> StreamingResponse:
    service = require_service(module)
    filters = {
        key: value.strip()
        for key, value in request.query_params.items()
        if key in service.LIST_FIELDS and value.strip()
    }
    items, _ = service.list_entries(
        filters=filters, keyword=keyword, status=status, page=1, size=1_000_000)
    output = io.StringIO()
    output.write("﻿")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["id", *service.LIST_FIELDS, "status"])
    for item in items:
        values = [item.get("id"), *(item.get(field, "") for field in service.LIST_FIELDS),
                  item.get("status", "")]
        writer.writerow([
            "'" + str(value) if str(value or "").startswith(("=", "+", "-", "@")) else value
            for value in values
        ])
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{module}.csv"'},
    )


@router.get("/{module}/{entry_id}/receipts", response_model=list[dict])
def list_receipts(
    module: str,
    entry_id: int,
    action_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """查回某个业务对象上的受理回执；新旧页面都读同一份。"""
    require_service(module)
    return receipts.list_for(module=module, entry_id=entry_id, action_id=action_id)


@router.get("/{module}/{entry_id}/source", response_model=dict)
def get_entry_source(module: str, entry_id: int) -> dict[str, Any]:
    """派生对象（诊改事项、评议邀请）回查原会议/原备课的出处。"""
    service = require_service(module)
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{service.ENTITY} {entry_id} 不存在或已归档")
    source = None
    if entry.get("来源类型"):
        source = describe_source(str(entry["来源类型"]), int(entry.get("来源编号") or 0))
    if source is None:
        # 旧数据没有结构化来源字段时，从文本标记里还原。
        source = source_of_row(module, entry)
    return {"entry_id": entry_id, "source": source}


@router.get("/{module}/{entry_id}", response_model=dict)
def get_entry(module: str, entry_id: int) -> dict[str, Any]:
    service = require_service(module)
    entry = service.detail_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{service.ENTITY} {entry_id} 不存在或已归档")
    return entry


@router.post("/{module}", response_model=ActionResult)
def create_entry(module: str, payload: EntryPayload) -> ActionResult:
    service = require_service(module)
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message=f"{service.ENTITY}已登记", entry=entry)


@router.post("/{module}/{entry_id}/actions", response_model=ActionResult)
def run_action(module: str, entry_id: int, payload: ActionPayload) -> ActionResult:
    service = require_service(module)
    # 旧客户端只发 action（原词）；新客户端发 action_id（稳定编号）并附带原词。
    entry, message, spec, receipt = service.perform_action(
        entry_id, payload.action.strip(), payload.action_id,
    )
    return ActionResult(
        ok=entry is not None,
        message=message,
        entry=entry,
        action_id=spec.action_id if spec else None,
        action_label=spec.label if spec else None,
        receipt=receipt,
    )
