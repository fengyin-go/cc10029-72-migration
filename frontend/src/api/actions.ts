/** 动作契约：按钮文字可以改，提交的稳定编号不变。
 *
 * 新版页面优先从后端 /api/actions/catalog 读取“展示名 + 稳定编号”，
 * 请求时两者一起发送；旧工作台已经打开、仍按中文原词提交的请求，
 * 由服务端归一化到同一编号，落到同一份受理回执上。
 */

export type ActionSpec = {
  action_id: string
  action_no?: number
  label: string
  legacy: string
}

/** 契约加载失败时的兜底：与后端 action_contract 保持一致。 */
const FALLBACK: Record<string, ActionSpec[]> = {
  review_meeting: [
    { action_id: 'review_meeting.sign', action_no: 1, label: '签认纪要', legacy: '签认纪要' },
    { action_id: 'review_meeting.object', action_no: 2, label: '提出异议', legacy: '提出异议' },
    { action_id: 'review_meeting.dispatch', action_no: 3, label: '下达', legacy: '分发给教师' },
  ],
}

const catalog = new Map<string, ActionSpec[]>(Object.entries(FALLBACK))
let loaded = false

export async function loadActionCatalog(): Promise<void> {
  if (loaded) return
  loaded = true
  try {
    const response = await fetch('/api/actions/catalog')
    if (!response.ok) return
    const payload = (await response.json()) as {
      modules: { module: string; actions: ActionSpec[] }[]
    }
    for (const item of payload.modules) {
      catalog.set(item.module, item.actions)
    }
  } catch {
    // 目录拿不到时沿用兜底契约，页面仍可正常提交稳定编号。
  }
}

export function actionsFor(moduleKey: string): ActionSpec[] {
  return catalog.get(moduleKey) ?? []
}

/** 用旧原词调用某个模块的动作，兼容尚未升级的旧后端。 */
export function legacyLabel(moduleKey: string, label: string): string {
  return actionSpec(moduleKey, label)?.legacy ?? label
}

/** 找到某个动作的展示名对应的契约；兼容用旧原词调用的情况。 */
export function actionSpec(moduleKey: string, label: string): ActionSpec | undefined {
  const specs = actionsFor(moduleKey)
  return (
    specs.find((item) => item.label === label) ??
    specs.find((item) => item.legacy === label) ??
    specs.find((item) => item.action_id === label)
  )
}

/** 页面展示用的动作文字：有契约用当前展示名，没有就沿用模块配置。 */
export function actionLabels(moduleKey: string, configured: string[]): string[] {
  const specs = actionsFor(moduleKey)
  if (!specs.length) return configured
  return specs.map((item) => item.label)
}
