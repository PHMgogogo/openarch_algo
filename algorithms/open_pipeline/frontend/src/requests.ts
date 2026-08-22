// 统一管理前端的所有 HTTP 请求
// 支持通过 .env 配置接口地址前缀与业务基础路径

// API 前缀（如 http://127.0.0.1:8008 或 /ops），从 .env 的 VITE_API_BASE_URL 读取；
// 未配置时回退到部署前缀 VITE_BASE，为空则使用同源地址
const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_BASE ?? '').replace(/\/+$/, '')
// 业务接口基础路径（如 /api/pipelines），从 .env 的 VITE_API_PIPELINES 读取
const API_PIPELINES: string = import.meta.env.VITE_API_PIPELINES ?? '/api/pipelines'

function apiUrl(path: string): string {
  return `${API_BASE_URL}${API_PIPELINES}${path}`
}

/** 请求异常，携带后端返回的错误信息 */
export class ApiError extends Error {
  data: any
  constructor(message: string, data?: any) {
    super(message)
    this.data = data
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), options)
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(data?.detail || data?.error || `HTTP ${response.status}`, data)
  }
  return response.json()
}

// ---- 流水线 ----

export function getPipelineList() {
  return request<{ data: string[] }>('/pipeline')
}

export function createPipeline(id: string) {
  return request<unknown>('/pipeline', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  })
}

export function renamePipeline(oldId: string, newId: string) {
  return request<unknown>(`/${oldId}/rename`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_id: newId }),
  })
}

export function deletePipeline(id: string) {
  return request<unknown>(`/pipeline/${id}`, { method: 'DELETE' })
}

export function getPipeline<T = any>(id: string) {
  return request<T>(`/pipeline/${id}`)
}

export function savePipeline(pipeline: any) {
  return request<unknown>(`/pipeline/${pipeline.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(pipeline),
  })
}

export function runPipeline(pipeline: any) {
  return request<any>(`/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pipeline }),
  })
}

// ---- 节点 ----

export function getNodeTypes() {
  return request<any>('/node/types')
}

export function getNodeSchema(nodeType: string) {
  return request<any>(`/node/schema/${nodeType}`)
}

export function getInstances() {
  return request<any[]>('/instance/list')
}

// ---- AI 对话 ----

// SSE 流式接口，返回原始 Response 供调用方读取流
export function chatAgent(payload: { user_input: string; history: any[]; pipeline: any }) {
  return fetch(apiUrl('/agent/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

// 节点帮助文档，SSE 流式返回
export function getNodeHelp(nodeType: string) {
  return fetch(apiUrl(`/node/help/${nodeType}`))
}

// ---- Cron ----

export function getCronNext(pipelineId: string) {
  return request<{ next: string | null }>(`/${pipelineId}/cron/next`)
}

export function getCronContexts(pipelineId: string) {
  return request<{ data: { filename: string; executed_at: string | null }[] }>(`/${pipelineId}/cron/contexts`)
}

export function getCronContext(pipelineId: string, filename: string) {
  return request<any>(`/${pipelineId}/cron/contexts/${filename}`)
}

export function generateCron(prompt: string) {
  return request<{ cron?: string }>('/cron/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  })
}
