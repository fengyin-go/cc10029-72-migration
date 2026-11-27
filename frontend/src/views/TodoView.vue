<template>
  <section class="page" data-module="todos">
    <header class="page-head">
      <div>
        <h2>教师待办</h2>
        <p class="page-desc">
          收到的待办都能回到原会议或原备课；同一份纪要重复下达时，两个页面看到的是同一条受理回执。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" data-testid="reload-todos" type="button" @click="reload">刷新待办</button>
      </div>
    </header>

    <table class="data-table">
      <thead>
        <tr>
          <th>来源模块</th>
          <th>待办事项</th>
          <th>原业务对象</th>
          <th>待处理动作</th>
          <th>受理回执</th>
          <th>查看</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in todos" :key="`${item.module}-${item.entry_id}`" :data-testid="`todo-${item.module}-${item.entry_id}`">
          <td>{{ item.module }}</td>
          <td>{{ item.title }}</td>
          <td>
            <span data-testid="todo-source">{{ todoSourceText(item) }}</span>
          </td>
          <td>{{ todoActionText(item) }}</td>
          <td>
            <span v-if="item.receipt" data-testid="todo-receipt">
              {{ item.receipt.receipt_id }}（第 {{ item.receipt.request_count }} 次请求）
            </span>
            <span v-else-if="item.receipt_id" data-testid="todo-receipt">{{ item.receipt_id }}</span>
            <span v-else>—</span>
          </td>
          <td>
            <RouterLink class="link" :to="todoRoute(item)" data-testid="todo-open">打开来源页</RouterLink>
          </td>
        </tr>
        <tr v-if="!todos.length">
          <td colspan="6" class="empty-state">暂无待办</td>
        </tr>
      </tbody>
    </table>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { loadTodos } from '@/api/backend-service'
import { todoActionText, todoRoute, todoSourceText } from '@/data/todos'
import type { TodoItem } from '@/data/types'

const todos = ref<TodoItem[]>([])
const errorMessage = ref('')

async function reload() {
  errorMessage.value = ''
  try {
    todos.value = await loadTodos()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '待办读取失败'
  }
}

onMounted(reload)
</script>
