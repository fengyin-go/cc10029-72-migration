"""通用接口契约；模块字段由领域服务持有，不再为每个模块复制一份模型类。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    # 前三个字段是旧客户端读取的原格式，保持不变；后三个字段是新增旁路信息。
    ok: bool
    message: str
    entry: dict[str, Any] | None = None
    action_id: str | None = None
    action_label: str | None = None
    receipt: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    # 新客户端可以只带稳定编号；旧客户端只发 action 也能被归一化。
    action: str = ""
    action_id: str | None = None
    remark: str | None = None
