/** 纯前端数据层的公共类型：与全栈版后端返回的结构保持一致，换回后端时页面不用改。 */

export type EntryRow = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  [field: string]: string | number | boolean | null | EntrySource | undefined
}

/** 派生对象（诊改事项、评议邀请）回到原会议/原备课的出处。 */
export type EntrySource = {
  module: string
  entry_id: number
  entity?: string
  label: string
  status?: string
  found?: boolean
}

/** 一次动作的受理回执；重复请求读回的是同一份。 */
export type Receipt = {
  receipt_id: string
  module: string
  entry_id: number
  action_id: string
  action_label: string
  legacy_action: string
  accepted: boolean
  replayed: boolean
  request_count: number
  message: string
  result?: Record<string, string | number>
  receipt?: Receipt
  source?: { module: string; entry_id: number }
}

/** 教师待办：可以从这里回到原会议/原备课。 */
export type TodoItem = {
  module: string
  entity: string
  entry_id: number
  title: string
  status?: string
  action?: { action_id: string; label: string; legacy: string }
  source?: EntrySource | null
  receipt?: Receipt | null
  receipt_id?: string | null
}

export type ModuleMeta = {
  key: string
  name: string
  entity: string
  desc: string
  fields: string[]
  statuses: string[]
  actions: string[]
  actionTargets: Record<string, string>
  metrics: string[]
}

export type PageResult = {
  items: EntryRow[]
  total: number
  page: number
  size: number
}

export type ActionResult = {
  ok: boolean
  message: string
  action_id?: string | null
  action_label?: string | null
  receipt?: Receipt | null
}

export type OverviewResult = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}
