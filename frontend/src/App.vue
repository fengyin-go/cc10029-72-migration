<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">教学诊改协同台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">教师、教研室主任和教务处在课堂观摩后填写教学反馈、制定改进方案、跟踪实施进度并在学期末完成复盘归档。</span>
        <span class="head-user">当前值班：应用开发组</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
const navItems = [{ label: "运营概览", path: "/" }, { label: "教师待办", path: "/todos" }, { label: "课堂观摩", path: "/observation" }, { label: "教学反馈", path: "/feedback" }, { label: "改进方案", path: "/improve_plan" }, { label: "实施进展", path: "/progress_log" }, { label: "同行评议", path: "/peer_review" }, { label: "教学档案", path: "/teach_record" }, { label: "学期目标", path: "/semester_goal" }, { label: "复盘会议", path: "/review_meeting" }, { label: "诊改任务", path: "/improve_task" }, { label: "外部评估", path: "/external_eval" }, { label: "课程组编排", path: "/course_group" }, { label: "大纲修订", path: "/syllabus_rev" }, { label: "教学成果申报", path: "/teach_award" }, { label: "集体备课", path: "/lesson_prep" }, { label: "师徒结对", path: "/mentor_pair" }, { label: "试卷分析", path: "/exam_analysis" }, { label: "排课编排", path: "/class_schedule" }, { label: "教学资源申请", path: "/resource_apply" }, { label: "质量简报", path: "/quality_report" }, { label: "教材选用", path: "/textbook_select" }]
</script>
