/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 前端部署前缀（反代场景），如 /ops/，默认根路径 */
  readonly VITE_BASE?: string
  /** API 前缀，可为空（同源/同前缀）、路径前缀或完整地址，如 http://127.0.0.1:8008 */
  readonly VITE_API_BASE_URL?: string
  /** 业务接口基础路径，如 /api/pipelines */
  readonly VITE_API_PIPELINES?: string
}

declare module 'markdown-it-texmath' {
  import type MarkdownIt from 'markdown-it'
  import type katex from 'katex'

  interface TexmathOptions {
    engine: typeof katex
    delimiters?: string[]
  }

  function texmath(md: MarkdownIt, options: TexmathOptions): void
  export = texmath
}
