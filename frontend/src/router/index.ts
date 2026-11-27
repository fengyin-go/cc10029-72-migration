import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
import TodoView from '@/views/TodoView.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    { path: '/todos', name: 'todos', component: TodoView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
