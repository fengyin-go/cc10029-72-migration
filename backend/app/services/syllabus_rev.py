"""大纲修订领域服务：修订稿登记、审批、否决，含跨模块影响集体备课。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class SyllabusRevService(BaseModuleService):
    MODULE = "syllabus_rev"
    ENTITY = "修订稿"
    OPERATION_TERM = "审批修订"
    LIST_FIELDS = ["课程名称", "修订章节", "原内容", "修订内容", "修订理由", "提出教师", "提交日期", "备注说明"]
    REQUIRED_FIELDS = ["课程名称", "修订章节", "原内容"]
    STATUS_ORDER = ["草稿", "待审批", "已通过", "已否决"]
    ACTION_RULES = {"审批修订": "已通过", "提交审批": "待审批", "否决修订": "已否决"}
    NEGATIVE_ACTIONS = []

    def _execute_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """执行动作，含跨模块联动：审批通过后更新相关集体备课记录。"""
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        # 审批修订：必须在待审批状态
        if action == "审批修订":
            if entry.get("status") not in ("待审批", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可审批"

        # 否决修订：必须是待审批
        if action == "否决修订":
            if entry.get("status") not in ("待审批", "草稿"):
                return None, f"{self.ENTITY} {entry_id} 当前状态为'{entry.get('status')}'，不可否决"

        result_entry, message = super()._execute_action(entry_id, action)

        # 审批通过后，标记相关集体备课记录为待签阅
        if result_entry and action == "审批修订":
            syllabus_chapter = entry.get("修订章节", "")
            course_name = entry.get("课程名称", "")
            if syllabus_chapter and course_name:
                self._flag_related_lesson_prep(course_name, syllabus_chapter, entry_id)

        return result_entry, message

    def _flag_related_lesson_prep(
        self, course_name: str, chapter: str, syllabus_id: int
    ) -> None:
        """大纲修订通过后，标记相关章节的备课记录通知备课教师签阅。"""
        prep_rows = store.rows("lesson_prep")
        for row in prep_rows:
            existing_chapter = str(row.get("备课章节", ""))
            # 章节相关且处于已签阅/已存档的备课记录打上备注
            if (course_name.casefold() in existing_chapter.casefold()
                    or chapter.casefold() in existing_chapter.casefold()):
                existing_note = str(row.get("备注说明", ""))
                new_note = f"{existing_note} [大纲修订{syllabus_id}已通过，需复核备课内容]".strip()
                row["备注说明"] = new_note
                # 如果已存档，改为待签阅
                if row.get("status") == "已存档":
                    row["status"] = "待签阅"
                    row["pending"] = True