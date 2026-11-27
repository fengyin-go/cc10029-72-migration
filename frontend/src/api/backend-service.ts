import { request } from './client'
import { moduleMeta } from '@/data/modules'
import type {
  ActionResult,
  EntryRow,
  EntrySource,
  OverviewResult,
  PageResult,
  Receipt,
  TodoItem,
} from '@/data/types'

export { moduleMeta }

export async function listEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<PageResult> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}?${query}`)
  if (!response.ok) throw new Error('业务数据读取失败')
  return await response.json()
}

export async function createEntry(
  key: string,
  values: Record<string, string>,
): Promise<ActionResult> {
  const response = await request(`/api/${key}`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return await response.json()
}

export async function runAction(
  key: string,
  id: number,
  action: string,
  actionId?: string,
): Promise<ActionResult> {
  // 新客户端把展示名和稳定编号一起发；旧服务只认 action，新服务优先认 action_id。
  const body: Record<string, string> = { action }
  if (actionId) body.action_id = actionId
  const response = await request(`/api/${key}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  return await response.json()
}

export async function loadTodos(): Promise<TodoItem[]> {
  const response = await request('/api/todos')
  if (!response.ok) throw new Error('待办读取失败')
  return await response.json()
}

export async function loadReceipts(key: string, id: number): Promise<Receipt[]> {
  const response = await request(`/api/${key}/${id}/receipts`)
  if (!response.ok) throw new Error('受理回执读取失败')
  return await response.json()
}

export async function loadSource(
  key: string,
  id: number,
): Promise<{ entry_id: number; source: EntrySource | null }> {
  const response = await request(`/api/${key}/${id}/source`)
  if (!response.ok) throw new Error('来源读取失败')
  return await response.json()
}

export async function downloadEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<void> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}/export?${query}`)
  if (!response.ok) throw new Error('业务数据导出失败')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${key}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export async function loadOverview(): Promise<OverviewResult> {
  const response = await request('/api/overview')
  if (!response.ok) throw new Error('运营概览读取失败')
  return await response.json()
}
