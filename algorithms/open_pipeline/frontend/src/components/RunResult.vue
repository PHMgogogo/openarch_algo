<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { _ } from '@/i18n'

const md = MarkdownIt().use(texmath, {
  engine: katex,
  delimiters: ['dollars', 'brackets', 'doxygen', 'gitlab'],
})

export interface RunResultData {
  output: string[]
  performance: { node: string; title: string; start_time: number; end_time: number; interval: number }[]
  data: Record<string, any[]>
  state: Record<string, any>
  alarm?: { cols: string[]; range: [number, number]; message: string; level: number; threshold: number }[]
}

export interface RunErrorData {
  error: string
  error_type: string
  traceback: string
}

const props = defineProps<{
  runResult: RunResultData | null
  runError: RunErrorData | null
  running: boolean
}>()

const elapsedSeconds = ref(0)
let animFrameId: number | null = null
let startTimestamp: number | null = null

function startTimer() {
  elapsedSeconds.value = 0
  startTimestamp = performance.now()

  function tick() {
    if (startTimestamp === null) return
    elapsedSeconds.value = (performance.now() - startTimestamp) / 1000
    animFrameId = requestAnimationFrame(tick)
  }

  animFrameId = requestAnimationFrame(tick)
}

function stopTimer() {
  if (animFrameId !== null) {
    cancelAnimationFrame(animFrameId)
    animFrameId = null
  }
  startTimestamp = null
}

watch(() => props.running, (val) => {
  if (val) {
    startTimer()
  } else {
    stopTimer()
  }
})

onUnmounted(() => {
  stopTimer()
})

const dataPage = ref(1)
const dataPageSize = 20

const dataTableKeys = computed(() => {
  if (!props.runResult?.data) return []
  return Object.keys(props.runResult.data)
})

const dataTableRowCount = computed(() => {
  let maxLen = 0
  for (const key of dataTableKeys.value) {
    const arr = props.runResult!.data[key]
    if (arr && arr.length > maxLen) maxLen = arr.length
  }
  return maxLen
})

const dataTableColumns = computed(() => {
  return dataTableKeys.value.map(key => ({
    key,
    dataKey: key,
    title: key,
    minWidth: Math.max(120, key.length * 12 + 40),
  }))
})

const dataTableRows = computed(() => {
  const keys = dataTableKeys.value
  if (!keys.length) return []
  const count = dataTableRowCount.value
  const rows: Record<string, any>[] = []
  for (let i = 0; i < count; i++) {
    const row: Record<string, any> = {}
    for (const key of keys) {
      const arr = props.runResult!.data[key]
      row[key] = (arr && i < arr.length) ? arr[i] : ''
    }
    rows.push(row)
  }
  return rows
})

const pagedDataRows = computed(() => {
  const rows = dataTableRows.value
  const start = (dataPage.value - 1) * dataPageSize
  return rows.slice(start, start + dataPageSize)
})

watch(() => props.runResult, () => {
  dataPage.value = 1
})

const activeTab = ref('data')

const outputViewMode = ref<'plain' | 'markdown'>('plain')

const markdownHTML = computed(() => {
  if (!props.runResult?.output?.length) return ''
  return md.render(props.runResult.output.join('\n'))
})
</script>

<template>
  <div class="result-content">
    <div v-if="running" class="running-indicator">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span class="running-text">{{ _('Running...') }}</span>
      <span class="running-timer">{{ elapsedSeconds.toFixed(1) }}s</span>
    </div>
    <el-alert
      v-if="runError"
      type="error"
      :title="_('Run Error')"
      :description="runError.error"
      show-icon
      :closable="false"
      style="margin-bottom: 10px"
    />
    <div v-if="runError" class="error-detail">
      <div class="error-type"><strong>{{ _('Error Type') }}:</strong> {{ runError.error_type }}</div>
      <pre class="error-traceback">{{ runError.traceback }}</pre>
    </div>
    <el-tabs v-if="runResult" v-model="activeTab" class="result-tabs">
      <el-tab-pane :label="_('Data')" name="data">
        <template v-if="dataTableKeys.length">
          <el-table :data="pagedDataRows" size="small" border stripe style="width: 100%">
            <el-table-column
              v-for="col in dataTableColumns"
              :key="col.key"
              :prop="col.dataKey"
              :label="col.title"
              :min-width="col.minWidth"
              show-overflow-tooltip
            />
          </el-table>
          <el-pagination
            v-if="dataTableRowCount > dataPageSize"
            style="margin-top: 10px; justify-content: flex-end"
            background
            layout="total, prev, pager, next"
            :total="dataTableRowCount"
            :page-size="dataPageSize"
            v-model:current-page="dataPage"
          />
        </template>
        <el-text v-else type="info">{{ _('No data') }}</el-text>
      </el-tab-pane>
      <el-tab-pane :label="_('State')" name="state">
        <el-table v-if="Object.keys(runResult.state ?? {}).length" :data="Object.entries(runResult.state ?? {}).map(([k, v]) => ({ key: k, value: v }))" size="small" border stripe style="width: 100%">
          <el-table-column prop="key" :label="_('Key')" />
          <el-table-column prop="value" :label="_('Value')" />
        </el-table>
        <el-text v-else type="info">{{ _('No state') }}</el-text>
      </el-tab-pane>
      <el-tab-pane :label="_('Alarm')" name="alarm">
        <el-table v-if="runResult.alarm?.length" :data="runResult.alarm" size="small" border stripe style="width: 100%">
          <el-table-column prop="cols" :label="_('Cols')" />
          <el-table-column prop="level" :label="_('Level')" width="80" />
          <el-table-column prop="threshold" :label="_('Threshold')" width="100" />
          <el-table-column prop="range" :label="_('Range')"
            :formatter="(r: any) => Array.isArray(r.range) ? r.range.join(' - ') : r.range" />
          <el-table-column prop="message" :label="_('Message')" show-overflow-tooltip />
        </el-table>
        <el-text v-else type="info">{{ _('No alarm') }}</el-text>
      </el-tab-pane>
      <el-tab-pane :label="_('Output')" name="output">
        <template v-if="runResult.output?.length">
          <div class="output-toolbar">
            <el-button-group size="small">
              <el-button :type="outputViewMode === 'plain' ? 'primary' : 'default'" @click="outputViewMode = 'plain'">{{ _('Plain') }}</el-button>
              <el-button :type="outputViewMode === 'markdown' ? 'primary' : 'default'" @click="outputViewMode = 'markdown'">{{ _('Markdown') }}</el-button>
            </el-button-group>
          </div>
          <pre v-if="outputViewMode === 'plain'" class="result-output">{{ runResult.output.join('\n') }}</pre>
          <div v-else class="result-output markdown-body" v-html="markdownHTML"></div>
        </template>
        <el-text v-else type="info">{{ _('No output') }}</el-text>
      </el-tab-pane>
      <el-tab-pane :label="_('Performance')" name="performance">
        <el-table v-if="runResult.performance?.length" :data="runResult.performance" size="small" border stripe style="width: 100%">
          <el-table-column prop="node" :label="_('Node')" />
          <el-table-column prop="title" :label="_('Name')" />
          <el-table-column prop="start_time" :label="_('Start(ms)')" :formatter="(r: any) => r.start_time.toFixed(3)" />
          <el-table-column prop="end_time" :label="_('End(ms)')" :formatter="(r: any) => r.end_time.toFixed(3)" />
          <el-table-column prop="interval" :label="_('Cost(ms)')" :formatter="(r: any) => r.interval.toFixed(3)" />
        </el-table>
        <el-text v-else type="info">{{ _('No performance data') }}</el-text>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style>
.result-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.result-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.result-tabs .el-tabs__content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

#pane-output {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.output-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.result-output {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  margin: 0;
}

.result-output.markdown-body {
  font-family: inherit;
  font-size: 14px;
  white-space: normal;
  word-break: normal;
}

.error-detail {
  margin-bottom: 10px;
}

.error-type {
  font-size: 13px;
  margin-bottom: 4px;
  color: #303133;
}

.error-traceback {
  background: #fef0f0;
  color: #f56c6c;
  padding: 10px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #fde2e2;
}

.running-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 10px;
  background: #ecf5ff;
  border: 1px solid #b3d8ff;
  border-radius: 4px;
  font-size: 14px;
  color: #409eff;
}

.running-text {
  font-weight: 500;
}

.running-timer {
  font-family: monospace;
  font-size: 15px;
  font-weight: 600;
}
</style>
