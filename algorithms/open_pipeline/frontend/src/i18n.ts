import { zhCN } from './locales/zh-CN'

type Locale = 'en' | 'zh-CN'

const messages: Record<Locale, Record<string, string>> = {
  'en': {},
  'zh-CN': zhCN,
}

let currentLocale: Locale = 'zh-CN'

export function setLocale(locale: Locale) {
  currentLocale = locale
}

export function getLocale(): Locale {
  return currentLocale
}

export function _(key: string): string {
  if (currentLocale === 'en') return key
  return messages[currentLocale]?.[key] ?? key
}
