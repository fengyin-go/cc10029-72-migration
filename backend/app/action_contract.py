"""动作契约：用稳定编号标识动作，中文只作为展示名和旧客户端兼容名。

前端按钮文字可以随时改（例如“分发”改成“下达”），但请求里的动作编号不变。
旧工作台已经打开、仍按中文原词提交时，服务端也按同一份契约归一化，
因此新旧客户端最终落到同一个业务动作和同一条受理记录上。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionSpec:
    """一个可执行动作的稳定契约。"""

    action_id: str      # 稳定编号，例如 review_meeting.dispatch
    label: str          # 当前界面展示名，可以随版本改名
    legacy: str         # 既有服务/旧客户端使用的原词，服务内部仍以它为准
    order: int          # 模块内稳定序号，兼容只传数字编号的调用
    replayable: bool = False  # 同一次动作的重复请求是否直接复用第一份回执


def _specs(module: str, entries: list[tuple[str, str, str]]) -> list[ActionSpec]:
    return [
        ActionSpec(action_id=f"{module}.{code}", label=label, legacy=legacy, order=index)
        for index, (code, label, legacy) in enumerate(entries, start=1)
    ]


# 会派生新对象、必须复用第一份受理回执的动作。
REPLAYABLE_ACTION_IDS = {"review_meeting.dispatch"}


def _mark_replayable(
    specs: dict[str, list[ActionSpec]],
) -> dict[str, list[ActionSpec]]:
    return {
        module: [
            ActionSpec(spec.action_id, spec.label, spec.legacy, spec.order, True)
            if spec.action_id in REPLAYABLE_ACTION_IDS else spec
            for spec in entries
        ]
        for module, entries in specs.items()
    }


# 模块 -> 动作契约。legacy 是旧页面会发送的原词；label 是新版展示名。
ACTION_SPECS: dict[str, list[ActionSpec]] = {
    "observation": _specs("observation", [
        ("submit", "提交记录", "提交记录"),
        ("return", "退回修改", "退回修改"),
        ("archive", "归档记录", "归档记录"),
    ]),
    "feedback": _specs("feedback", [
        ("sign", "签收反馈", "签收反馈"),
        ("return", "退回重提", "退回重提"),
        ("finish", "确认办结", "确认办结"),
    ]),
    "improve_plan": _specs("improve_plan", [
        ("approve", "审核方案", "审核方案"),
        ("submit", "提交审核", "提交审核"),
        ("reject", "驳回方案", "驳回方案"),
    ]),
    "progress_log": _specs("progress_log", [
        ("confirm", "确认进展", "确认进展"),
        ("postpone", "申请延期", "申请延期"),
        ("complete", "标记完成", "标记完成"),
    ]),
    "peer_review": _specs("peer_review", [
        ("summarize", "汇总评议", "汇总评议"),
        ("return", "退回评议", "退回评议"),
        ("publish", "公示结果", "公示结果"),
    ]),
    "teach_record": _specs("teach_record", [
        ("archive", "审核归档", "审核归档"),
        ("correct", "退回补正", "退回补正"),
        ("cancel", "注销档案", "注销档案"),
    ]),
    "semester_goal": _specs("semester_goal", [
        ("approve", "审定目标", "审定目标"),
        ("return", "退回修订", "退回修订"),
        ("abolish", "废止目标", "废止目标"),
    ]),
    "review_meeting": _specs("review_meeting", [
        ("sign", "签认纪要", "签认纪要"),
        ("object", "提出异议", "提出异议"),
        # 新版把“分发”改名为“下达”，稳定编号保持不变。
        ("dispatch", "下达", "分发给教师"),
    ]),
    "improve_task": _specs("improve_task", [
        ("claim", "认领任务", "认领任务"),
        ("start", "启动执行", "启动执行"),
        ("request_acceptance", "申请验收", "申请验收"),
    ]),
    "external_eval": _specs("external_eval", [
        ("receive", "接收报告", "接收报告"),
        ("supplement", "退回补充", "退回补充"),
        ("transfer", "转办整改", "转办整改"),
    ]),
    "course_group": _specs("course_group", [
        ("confirm", "确认建组", "确认建组"),
        ("adjust", "调整成员", "调整成员"),
        ("dissolve", "解散课程组", "解散课程组"),
    ]),
    "syllabus_rev": _specs("syllabus_rev", [
        ("approve", "审批修订", "审批修订"),
        ("submit", "提交审批", "提交审批"),
        ("reject", "否决修订", "否决修订"),
    ]),
    "teach_award": _specs("teach_award", [
        ("review", "初审申报", "初审申报"),
        ("complete", "退回补全", "退回补全"),
        ("report", "上报评审", "上报评审"),
    ]),
    "lesson_prep": _specs("lesson_prep", [
        ("sign", "签阅记录", "签阅记录"),
        ("comment", "补充意见", "补充意见"),
        ("archive", "存档记录", "存档记录"),
    ]),
    "mentor_pair": _specs("mentor_pair", [
        ("accept", "验收结对", "验收结对"),
        ("adjust", "调整计划", "调整计划"),
        ("terminate", "终止结对", "终止结对"),
    ]),
    "exam_analysis": _specs("exam_analysis", [
        ("review", "审核分析", "审核分析"),
        ("refill", "退回重填", "退回重填"),
        ("archive", "存档分析", "存档分析"),
    ]),
    "class_schedule": _specs("class_schedule", [
        ("confirm", "确认排课", "确认排课"),
        ("request_change", "申请调整", "申请调整"),
        ("execute_change", "执行调整", "执行调整"),
    ]),
    "resource_apply": _specs("resource_apply", [
        ("approve", "审批领用", "审批领用"),
        ("return", "退回申请", "退回申请"),
        ("return_resource", "确认归还", "确认归还"),
    ]),
    "quality_report": _specs("quality_report", [
        ("sign", "签收简报", "签收简报"),
        ("supplement", "补充说明", "补充说明"),
        ("communicate", "传达到教师", "传达到教师"),
    ]),
    "textbook_select": _specs("textbook_select", [
        ("approve", "审核选用", "审核选用"),
        ("reselect", "退回重选", "退回重选"),
        ("order", "确认订购", "确认订购"),
    ]),
}

ACTION_SPECS = _mark_replayable(ACTION_SPECS)


def _short_id(action_id: str) -> str:
    return action_id.split(".", 1)[1] if "." in action_id else action_id


def resolve_action(module: str, value: object) -> str | None:
    """把稳定编号、新展示名或旧原词归一化成服务内部使用的动作名。

    无法识别时返回 None，由调用方保留原值交给业务服务报错，避免吞掉未知动作。
    """
    specs = ACTION_SPECS.get(module, [])
    text = str(value or "").strip()
    if not text:
        return None
    folded = text.casefold()
    normalized = folded.replace("-", "_")

    for spec in specs:
        names = {
            spec.action_id.casefold(),
            _short_id(spec.action_id).casefold(),
            spec.label.casefold(),
            spec.legacy.casefold(),
        }
        if folded in names or normalized in {name.replace("-", "_") for name in names}:
            return spec.legacy

    if text.isdigit():
        order = int(text)
        for spec in specs:
            if spec.order == order:
                return spec.legacy
    return None


def spec_for(module: str, action: object) -> ActionSpec | None:
    """按编号/展示名/旧原词取得完整动作契约。"""
    resolved = resolve_action(module, action)
    if resolved is None:
        return None
    for spec in ACTION_SPECS.get(module, []):
        if spec.legacy == resolved:
            return spec
    return None


def action_catalog() -> list[dict[str, object]]:
    """给前端/联调用的动作目录：展示名与稳定编号的对应关系。"""
    return [
        {
            "module": module,
            "actions": [
                {
                    "action_id": spec.action_id,
                    "action_no": spec.order,
                    "label": spec.label,
                    "legacy": spec.legacy,
                }
                for spec in specs
            ],
        }
        for module, specs in ACTION_SPECS.items()
    ]
