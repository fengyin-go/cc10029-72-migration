import type { TodoItem } from '@/data/types'

/** 兼容旧数据仓库：TodoItem.receipt 里的 receipt 字段是自引用的，这里只取外层。 */

export function todoActionText(item: TodoItem): string {
  return item.action?.label ?? '处理'
}

export function todoSourceText(item: TodoItem): string {
  if (!item.source) return '—'
  const entity = item.source.entity ?? item.source.module
  return `${entity} ${item.source.label || `#${item.source.entry_id}`}`
}

export function todoRoute(item: TodoItem): string {
  return `/${item.source?.module ?? item.module}`
}
