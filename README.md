# 教学诊改协同台

教师、教研室主任和教务处在课堂观摩后填写教学反馈、制定改进方案、跟踪实施进度并在学期末完成复盘归档。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/WorkbenchView.vue|tsx  全部模块共享工作台
│   ├── src/data/modules.ts              18个业务模块配置
│   ├── src/api/              统一请求封装
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/resource.py  通用查询/导出/登记/动作接口
│   ├── app/services/<key>.py    每个模块独立领域逻辑
│   ├── app/services/base.py     共享服务骨架
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

### 前端

```bash
cd frontend
npm ci
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 课堂观摩 | `observation` | 观摩记录 | 教师姓名、课程名称、授课日期 |
| 教学反馈 | `feedback` | 反馈单 | 反馈对象、反馈要点、改进建议 |
| 改进方案 | `improve_plan` | 改进方案 | 关联反馈、改进目标、改进措施 |
| 实施进展 | `progress_log` | 进展记录 | 关联方案、当前阶段、完成情况 |
| 同行评议 | `peer_review` | 评议表 | 被评教师、评议维度、得分 |
| 教学档案 | `teach_record` | 档案条目 | 教师姓名、档案类型、内容摘要 |
| 学期目标 | `semester_goal` | 学期目标 | 目标描述、量化指标、责任教师 |
| 复盘会议 | `review_meeting` | 会议纪要 | 会议主题、参会人员、召开日期 |
| 诊改任务 | `improve_task` | 诊改任务 | 任务描述、承接方案、执行人员 |
| 外部评估 | `external_eval` | 评估报告 | 评估机构、评估指标、评估结论 |
| 课程组编排 | `course_group` | 课程组 | 组名、覆盖课程、组长教师 |
| 大纲修订 | `syllabus_rev` | 修订稿 | 课程名称、修订章节、原内容 |
| 教学成果申报 | `teach_award` | 成果申报 | 成果名称、完成团队、成果概要 |
| 集体备课 | `lesson_prep` | 备课记录 | 备课章节、主备教师、参与教师 |
| 师徒结对 | `mentor_pair` | 结对记录 | 指导教师、青年教师、结对目标 |
| 试卷分析 | `exam_analysis` | 分析记录 | 考试名称、任课教师、参考人数 |
| 排课编排 | `class_schedule` | 排课单 | 课程名称、授课教师、上课时间 |
| 教学资源申请 | `resource_apply` | 资源申请 | 申请资源、用途说明、使用时间 |
| 质量简报 | `quality_report` | 质量简报 | 覆盖学期、教学质量概况、突出问题 |
| 教材选用 | `textbook_select` | 选用单 | 教材名称、主编、出版社 |

## 约定

- 全部模块共享`frontend/src/views/WorkbenchView.vue|tsx`和一套资源路由。
- 每个模块仍保留独立`backend/app/services/<模块>.py`；纯前端保留
  `frontend/src/domain/<模块>.ts`，用于承载真实业务差异并维持36题位容量。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

## 动作契约与受理回执

界面按钮上的文字只是展示名，动作真正依赖的是稳定编号（如
`review_meeting.dispatch`）。改名不改契约：新版把“分发”显示为“下达”，
旧工作台继续发送原词“分发给教师”，服务端都归一化到同一个动作。

- `backend/app/action_contract.py`：每个动作的 `action_id`、当前展示名、
  旧原词和模块内序号；`GET /api/actions/catalog` 对外给出对照表。
- 动作请求体可以是旧格式 `{ "action": "分发给教师" }`，也可以是新格式
  `{ "action": "分发给教师", "action_id": "review_meeting.dispatch" }`。
  新前端同时发送原词和编号，旧后端、新后端都能处理，可并行上线。
- 动作响应保持原来的 `ok / message / entry`，另加 `action_id`、`action_label`
  和 `receipt`；旧客户端忽略新增字段即可。
- 会派生业务对象的动作（如纪要“下达”）带受理回执：同一
  (模块, 对象编号, 动作编号) 只受理一次，重复请求（旧页面迟到的回执、
  另一个标签页的新请求）读回第一份回执和同一个派生对象。
  `GET /api/{module}/{id}/receipts`、`GET /api/receipts/{receipt_id}` 可查。
- 派生对象（诊改事项、同行评议邀请）同时写入结构化来源字段
  （`来源类型`/`来源编号`/`来源标签`）和旧格式文本标记（`[meeting:62]`、
  `[lesson_prep:52]`），旧服务回切后仍能按原样去重和读取。
  `GET /api/{module}/{id}/source` 可从派生对象回到原会议/原备课。
- `GET /api/todos` 汇总教师待办，每条都带原业务对象和已有回执，
  新旧页面都能从待办回到发起页。

## 验收演练

示例数据带两条演练记录：纪要 `M-62`（已签认）与备课 `L-52`（待签阅）。

```bash
# 旧页面按原词分发；另一个标签页用新编号下达同一份纪要
curl -s -X POST localhost:8000/api/review_meeting/62/actions \
  -H 'Content-Type: application/json' -d '{"action":"分发给教师"}'
curl -s -X POST localhost:8000/api/review_meeting/62/actions \
  -H 'Content-Type: application/json' \
  -d '{"action":"分发给教师","action_id":"review_meeting.dispatch"}'
# 两次拿到的 receipt_id 相同，诊改事项只有一项
curl -s localhost:8000/api/review_meeting/62/receipts
```

领域：应用开发
子方向：web前端/全栈开发
