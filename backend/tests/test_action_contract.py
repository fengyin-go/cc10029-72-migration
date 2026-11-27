"""动作契约与受理回执测试：改名、新旧客户端并行、重复下达只生成一项工作。"""
import concurrent.futures

import pytest

from app import receipts
from app.action_contract import resolve_action, spec_for
from app.services.improve_task import ImproveTaskService
from app.services.lesson_prep import LessonPrepService
from app.services.peer_review import PeerReviewService
from app.services.review_meeting import ReviewMeetingService
from app.store import store


MEETING_RESOLUTION = "需要成立专项教学改进任务组，针对程序设计课程实验环节制定改进方案"


def seed_meeting(meeting_id: int = 62) -> dict:
    store.rows("review_meeting").clear()
    row = {
        "id": meeting_id,
        "会议主题": f"M-{meeting_id} 程序设计课程期中复盘",
        "参会人员": "教研室主任、程序设计课程组",
        "召开日期": "2026-11-12",
        "决议事项": MEETING_RESOLUTION,
        "分歧观点": "",
        "记录人员": "周老师",
        "下次会议": "",
        "备注说明": "",
        "status": "已签认",
        "pending": True,
        "abnormal": False,
    }
    store.rows("review_meeting").append(row)
    return row


def seed_prep(prep_id: int = 52) -> dict:
    store.rows("lesson_prep").clear()
    row = {
        "id": prep_id,
        "备课章节": f"L-{prep_id} 程序设计实验课集体备课",
        "主备教师": "杨老师",
        "参与教师": "李老师、王老师",
        "备课日期": "2026-11-18",
        "研讨要点": "实验环节的分层任务设计",
        "教学资源": "实验指导书 v2",
        "课后反思": "实验分组需要改进，建议进行同行评议",
        "备注说明": "",
        "status": "待签阅",
        "pending": True,
        "abnormal": False,
    }
    store.rows("lesson_prep").append(row)
    return row


@pytest.fixture(autouse=True)
def clean_state():
    for module in ("review_meeting", "lesson_prep", "improve_task", "peer_review", "feedback"):
        store.rows(module).clear()
    receipts.clear()
    yield
    receipts.clear()


class TestActionContract:
    """改名不改契约：旧原词、新展示名和稳定编号都指向同一个动作。"""

    def test_dispatch_accepts_legacy_label_and_stable_id(self):
        assert resolve_action("review_meeting", "分发给教师") == "分发给教师"
        assert resolve_action("review_meeting", "下达") == "分发给教师"
        assert resolve_action("review_meeting", "review_meeting.dispatch") == "分发给教师"
        assert resolve_action("review_meeting", "dispatch") == "分发给教师"

    def test_dispatch_spec_keeps_label_and_legacy(self):
        spec = spec_for("review_meeting", "分发给教师")
        assert spec.action_id == "review_meeting.dispatch"
        assert spec.label == "下达"
        assert spec.legacy == "分发给教师"

    def test_unknown_action_is_not_silently_mapped(self):
        assert resolve_action("review_meeting", "彻底删除") is None

    def test_other_modules_keep_their_original_words(self):
        spec = spec_for("lesson_prep", "签阅记录")
        assert spec.action_id == "lesson_prep.sign"
        assert spec.label == "签阅记录"
        assert resolve_action("improve_task", "认领任务") == "认领任务"


class TestDispatchReceipt:
    """同一份纪要的一次下达：旧页面与新版标签页共用第一份回执和同一项工作。"""

    def test_legacy_then_new_client_share_one_receipt_and_one_task(self):
        seed_meeting(62)
        svc = ReviewMeetingService()

        old_entry, old_message, old_spec, old_receipt = svc.perform_action(62, "分发给教师")
        assert old_entry is not None
        assert old_message == "会议纪要已分发给教师"  # 旧客户端仍读到原词
        assert old_receipt["replayed"] is False

        new_entry, new_message, new_spec, new_receipt = svc.perform_action(
            62, "下达", "review_meeting.dispatch")
        assert new_entry is not None
        assert new_message == "会议纪要已下达"
        assert new_receipt["replayed"] is True
        assert new_receipt["receipt_id"] == old_receipt["receipt_id"]
        assert new_receipt["request_count"] == 2
        assert new_spec.action_id == old_spec.action_id

        tasks = store.rows("improve_task")
        assert len(tasks) == 1, "一份纪要的一次下达只能派发一项诊改事项"
        assert new_receipt["result"]["entry_id"] == tasks[0]["id"]
        assert old_receipt["receipt_id"] == new_receipt["receipt_id"]

    def test_concurrent_duplicate_dispatch_creates_single_task(self):
        seed_meeting(62)
        svc = ReviewMeetingService()

        def call(_index: int):
            return svc.perform_action(62, "下达", "review_meeting.dispatch")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(call, range(8)))

        assert all(item[0] is not None for item in results)
        ids = {item[3]["receipt_id"] for item in results}
        assert len(ids) == 1, "并发请求必须落到同一份受理回执"
        assert len(store.rows("improve_task")) == 1, "并发下达不能各派一项"
        assert results[0][3]["result"]["entry_id"] == results[-1][3]["result"]["entry_id"]

    def test_receipt_is_queryable_for_both_pages(self):
        seed_meeting(62)
        ReviewMeetingService().perform_action(62, "分发给教师")
        receipts_rows = receipts.list_for(
            module="review_meeting", entry_id=62, action_id="review_meeting.dispatch")
        assert len(receipts_rows) == 1
        receipt = receipts_rows[0]
        assert receipt["result"]["module"] == "improve_task"
        assert receipts.find_by_id(receipt["receipt_id"])["entry_id"] == 62

    def test_old_service_state_without_receipt_is_backfilled(self):
        row = seed_meeting(62)
        row["status"] = "已分发"
        store.rows("improve_task").append({
            "id": 7,
            "任务描述": "会议决议：旧数据 [meeting:62]",
            "承接方案": MEETING_RESOLUTION,
            "执行人员": "", "起止日期": "", "验收标准": "", "督办人员": "", "任务权重": "",
            "备注说明": "由复盘会议决议自动生成",
            "status": "待认领", "pending": True, "abnormal": False,
        })

        entry, message, _spec, receipt = ReviewMeetingService().perform_action(62, "下达")
        assert entry is not None
        assert "沿用首次受理结果" in message
        assert receipt["result"]["entry_id"] == 7
        assert len(store.rows("improve_task")) == 1


class TestProvenance:
    """接单教师从待办/诊改页回到原会议或原备课。"""

    def test_improve_task_keeps_legacy_marker_and_structured_source(self):
        seed_meeting(62)
        ReviewMeetingService().perform_action(62, "分发给教师")
        task = store.rows("improve_task")[0]

        # 旧代码按 [meeting:62] 搜索仍能找到。
        assert "[meeting:62]" in task["任务描述"]
        assert task["来源类型"] == "review_meeting"
        assert task["来源编号"] == 62
        assert task["来源标签"] == "M-62 程序设计课程期中复盘"

    def test_task_list_row_carries_source_for_claiming(self):
        seed_meeting(62)
        ReviewMeetingService().perform_action(62, "分发给教师")
        task_id = store.rows("improve_task")[0]["id"]

        svc = ImproveTaskService()
        items, _ = svc.list_entries(size=50)
        row = next(item for item in items if item["id"] == task_id)
        assert row["来源"]["module"] == "review_meeting"
        assert row["来源"]["entry_id"] == 62
        assert row["原业务对象"] == "M-62 程序设计课程期中复盘"

        claimed, message = svc.run_action(task_id, "认领任务")
        assert claimed["status"] == "执行中"
        assert claimed["来源"]["entry_id"] == 62

    def test_todo_list_links_back_to_meeting_for_old_and_new_pages(self):
        seed_meeting(62)
        todos = ReviewMeetingService().pending_items()
        assert len(todos) == 1
        item = todos[0]
        assert item["source"]["entry_id"] == 62
        assert item["action"]["action_id"] == "review_meeting.dispatch"
        assert item["action"]["legacy"] == "分发给教师"
        assert item["action"]["label"] == "下达"

    def test_lesson_prep_review_keeps_signature_source(self):
        seed_prep(52)
        entry, _, _spec, receipt = LessonPrepService().perform_action(52, "签阅记录")
        assert entry["status"] == "已签阅"
        assert receipt["result"]["module"] == "peer_review"

        reviews = store.rows("peer_review")
        assert len(reviews) == 1
        review = reviews[0]
        assert "[lesson_prep:52]" in review["评议意见"]
        assert review["签阅出处回执"] == receipt["receipt_id"]

        items, _ = PeerReviewService().list_entries(size=20)
        assert items[0]["签阅出处"] == "L-52 程序设计实验课集体备课"
        assert items[0]["原业务编号"] == "lesson_prep:52"

    def test_repeat_sign_does_not_create_second_review(self):
        seed_prep(52)
        LessonPrepService().perform_action(52, "签阅记录")
        # 已签阅状态再签一次被业务约束拦住，也不会多生成评议。
        entry, message = LessonPrepService().run_action(52, "签阅记录")
        assert entry is None
        assert "无需重复签阅" in message
        assert len(store.rows("peer_review")) == 1


class TestOldClientAfterRollback:
    """服务器回切旧版本后，旧客户端仍能完成认领与汇总。"""

    def test_claim_task_with_legacy_action_word(self):
        seed_meeting(62)
        ReviewMeetingService().perform_action(62, "分发给教师")
        task_id = store.rows("improve_task")[0]["id"]
        entry, message = ImproveTaskService().run_action(task_id, "认领任务")
        assert entry is not None
        assert entry["status"] == "执行中"
        assert message == "诊改任务已认领任务"

    def test_summarize_review_with_legacy_action_word(self):
        seed_prep(52)
        LessonPrepService().perform_action(52, "签阅记录")
        review_id = store.rows("peer_review")[0]["id"]
        entry, _ = PeerReviewService().run_action(review_id, "汇总评议")
        assert entry is not None
        assert entry["status"] == "已汇总"

    def test_new_data_keeps_statuses_and_markers_old_service_expects(self):
        """旧服务只认标准状态和 [meeting:id]/[lesson_prep:id] 标记。"""
        seed_meeting(62)
        seed_prep(52)
        ReviewMeetingService().perform_action(62, "分发给教师")
        LessonPrepService().perform_action(52, "签阅记录")

        task = store.rows("improve_task")[0]
        review = store.rows("peer_review")[0]
        assert task["status"] == "待认领" and isinstance(task["任务描述"], str)
        assert task["任务描述"].find("[meeting:62]") != -1
        assert review["status"] == "待汇总"
        assert review["评议意见"].find("[lesson_prep:52]") != -1
        # 旧服务会按这些字段判断能不能认领/汇总。
        assert set(task) >= {"id", "status", "pending", "任务描述", "承接方案", "执行人员"}
        assert set(review) >= {"id", "status", "pending", "被评教师", "评议维度", "评议意见"}

    def test_legacy_dedupe_still_prevents_duplicates_after_rollback_forward(self):
        """回切后再升级：旧标记仍被识别，不会补出第二项工作。"""
        seed_meeting(62)
        ReviewMeetingService().perform_action(62, "分发给教师")
        task = store.rows("improve_task")[0]
        # 模拟旧服务在回切期间补写的一行（只有文本标记，没有结构化来源）。
        legacy_task = {
            "id": task["id"] + 100,
            "任务描述": f"旧版补记 [meeting:62]",
            "承接方案": MEETING_RESOLUTION,
            "执行人员": "", "起止日期": "", "验收标准": "", "督办人员": "", "任务权重": "",
            "备注说明": "旧版补记", "status": "待认领", "pending": True, "abnormal": False,
        }
        store.rows("improve_task").append(legacy_task)

        # 再次请求下达时，回执复用第一次的实际结果，不产生第三项。
        _, _message, _spec, receipt = ReviewMeetingService().perform_action(62, "下达")
        assert receipt["result"]["entry_id"] == task["id"]
        assert len(store.rows("improve_task")) == 2

