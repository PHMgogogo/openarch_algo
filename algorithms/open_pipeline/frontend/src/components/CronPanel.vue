<script setup lang="ts">
import { ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { _ } from '@/i18n'
import { ElMessage } from 'element-plus'
import { getPipeline, savePipeline, getCronNext, getCronContexts, getCronContext, generateCron as generateCronRequest } from '@/requests'

const props = defineProps<{
  pipelineId: string
}>()

const emit = defineEmits<{
  'show-context': [data: any]
}>()

const cronEnabled = ref(false)
const cronExpr = ref('')
const cronNext = ref<string | null>(null)
const cronContexts = ref<{ filename: string; executed_at: string | null }[]>([])

const cronPromptVisible = ref(false)
const cronPrompt = ref('')
const cronGenerating = ref(false)

async function fetchCronStatus() {
  if (!props.pipelineId) return
  try {
    const pipeline = await getPipeline(props.pipelineId)
    cronEnabled.value = pipeline.cron_enable ?? false
    cronExpr.value = pipeline.cron_expr ?? ''
  } catch { /* ignore */ }
}

async function fetchCronNext() {
  if (!props.pipelineId) return
  try {
    const data = await getCronNext(props.pipelineId)
    cronNext.value = data.next ?? null
  } catch { /* ignore */ }
}

async function fetchCronContexts() {
  if (!props.pipelineId) return
  try {
    const result = await getCronContexts(props.pipelineId)
    cronContexts.value = result.data ?? []
  } catch { /* ignore */ }
}

async function fetchAll() {
  await Promise.all([fetchCronStatus(), fetchCronNext(), fetchCronContexts()])
}

watch(() => props.pipelineId, () => {
  fetchAll()
}, { immediate: true })

async function generateCron() {
  if (!cronPrompt.value.trim()) return
  cronGenerating.value = true
  try {
    const data = await generateCronRequest(cronPrompt.value)
    if (data.cron) {
      cronExpr.value = data.cron
      cronPrompt.value = ''
      cronPromptVisible.value = false
      saveCron()
    } else {
      ElMessage.error(_('Failed to generate cron expression'))
    }
  } catch {
    ElMessage.error(_('Failed to generate cron expression'))
  } finally {
    cronGenerating.value = false
  }
}

async function saveCron() {
  try {
    const pipeline = await getPipeline(props.pipelineId)
    pipeline.cron_enable = cronEnabled.value
    pipeline.cron_expr = cronExpr.value
    await savePipeline(pipeline)
    await fetchCronNext()
  } catch { /* ignore */ }
}

function onToggleCron() {
  saveCron()
}

function onExprInput(e: Event) {
  const input = e.target as HTMLInputElement
  input.blur()
}

function onExprBlur() {
  saveCron()
}

async function viewContext(filename: string) {
  try {
    emit('show-context', await getCronContext(props.pipelineId, filename))
  } catch { /* ignore */ }
}
</script>

<template>
  <div class="cron-panel">
    <h4 class="cron-title">
      <span>{{ _('Cron') }}</span>
      <el-switch v-model="cronEnabled" size="small" @change="onToggleCron" />
    </h4>

    <div class="cron-settings">
      <div class="cron-row">
        <span class="cron-label">{{ _('Cron Expression') }}</span>
        <el-popover
          v-model:visible="cronPromptVisible"
          :width="280"
          trigger="click"
          placement="bottom"
        >
          <template #reference>
            <el-input
              v-model="cronExpr"
              size="small"
              :disabled="!cronEnabled"
              placeholder="*/5 * * * *"
              @keyup.enter="onExprInput"
              @blur="onExprBlur"
            />
          </template>
          <div class="cron-prompt-popover">
            <div class="cron-prompt-title">{{ _('Describe your schedule in natural language') }}</div>
            <el-input
              v-model="cronPrompt"
              type="textarea"
              :rows="3"
              :placeholder="_('e.g. Run every Monday at 9 AM')"
              size="small"
            />
            <div class="cron-prompt-actions">
              <el-button size="small" @click="cronPromptVisible = false">{{ _('Cancel') }}</el-button>
              <el-button size="small" type="primary" :loading="cronGenerating" @click="generateCron">
                {{ _('Generate') }}
              </el-button>
            </div>
          </div>
        </el-popover>
      </div>
    </div>

    <div class="cron-section">
      <div class="cron-section-header">
        <span class="cron-section-title">{{ _('Next Run') }}</span>
        <el-button size="small" text @click="fetchCronNext">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
      <div class="cron-next">
        {{ cronNext ? cronNext : (_('Not enabled') + ' / --') }}
      </div>
    </div>

    <div class="cron-section cron-history">
      <div class="cron-section-header">
        <span class="cron-section-title">{{ _('Cron History') }}</span>
        <el-button size="small" text @click="fetchCronContexts">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
      <div v-if="cronContexts.length === 0" class="cron-empty">
        {{ _('No history') }}
      </div>
      <div
        v-for="ctx in cronContexts"
        :key="ctx.filename"
        class="cron-history-item"
        @click="viewContext(ctx.filename)"
      >
        <span class="cron-history-time">{{ ctx.executed_at ?? ctx.filename }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cron-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.cron-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  color: #606266;
  margin: 0;
  padding: 12px 16px 8px;
  border-top: 1px solid #ebeef5;
  border-bottom: 1px solid #ebeef5;
}

.cron-settings {
  padding: 8px 12px;
  border-bottom: 1px solid #ebeef5;
}

.cron-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cron-label {
  font-size: 14px;
  color: #606266;
  flex-shrink: 0;
  min-width: 80px;
}

.cron-section {
  padding: 8px 12px;
  border-bottom: 1px solid #ebeef5;
}

.cron-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.cron-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #909399;
}

.cron-next {
  font-size: 14px;
  color: #303133;
  word-break: break-all;
}

.cron-history {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.cron-empty {
  font-size: 14px;
  color: #c0c4cc;
  padding: 8px 0;
}

.cron-history-item {
  font-size: 14px;
  color: #409eff;
  cursor: pointer;
  padding: 2px 0;
  border-bottom: 1px dotted #ebeef5;
}

.cron-history-item:hover {
  color: #66b1ff;
}

.cron-history-time {
  word-break: break-all;
}

.cron-prompt-popover {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cron-prompt-title {
  font-size: 13px;
  color: #606266;
}

.cron-prompt-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
