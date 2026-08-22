<template>
  <div class="pipeline-chat">
    <div class="chat-header">
      <el-icon><ChatDotRound /></el-icon>
      <span>{{ _('Pipeline AI Assistant') }}</span>
      <el-button class="clear-btn" text size="small" @click="clearChat" :disabled="messages.length === 0">
        {{ _('Clear') }}
      </el-button>
    </div>
    <div class="chat-messages" ref="messagesRef">
      <div v-if="messages.length === 0 && !streaming" class="chat-hint">
        {{ _('Describe what you want to change in the pipeline, e.g. "add a TextCsvInputNode with id input1"') }}
      </div>

      <!-- Historical messages -->
      <template v-for="(msg, i) in messages" :key="'m'+i">
        <div v-if="msg.role === 'user'" class="chat-message user">
          <div class="message-role">{{ _('You') }}</div>
          <div class="message-content">{{ msg.content }}</div>
        </div>

        <div v-else-if="msg.assistantType === 'reasoning'" class="chat-message reasoning">
          <div class="message-role">{{ _('Thinking') }}</div>
          <div class="message-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
        </div>

        <div v-else-if="msg.assistantType === 'tool_call' && msg.toolCall" class="chat-message tool-call-msg">
          <div class="message-role">
            <el-tag size="small" :type="msg.toolCall.output !== undefined ? 'success' : 'warning'">
              {{ msg.toolCall.name }}
            </el-tag>
          </div>
          <div class="tool-call-detail">
            <div class="tool-call-section">
              <div class="tool-call-label">{{ _('Arguments') }}:</div>
              <pre class="tool-call-json">{{ formatJson(msg.toolCall.arguments) }}</pre>
            </div>
            <div v-if="msg.toolCall.output !== undefined" class="tool-call-section">
              <div class="tool-call-label">{{ _('Output') }}:</div>
              <pre class="tool-call-json">{{ msg.toolCall.output }}</pre>
            </div>
          </div>
        </div>

        <div v-else class="chat-message assistant">
          <div class="message-role">{{ _('AI') }}</div>
          <div class="message-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
        </div>
      </template>

      <!-- Streaming items (rendered in arrival order) -->
      <template v-for="(item, idx) in streamingItems" :key="'s'+item._key">
        <div v-if="item.type === 'reasoning'" class="chat-message reasoning">
          <div class="message-role">{{ _('Thinking') }}</div>
          <div class="message-content markdown-body" v-html="renderMarkdown(item.text!)"></div>
        </div>

        <div v-else-if="item.type === 'tool_call' && item.toolCall" class="chat-message tool-call-msg">
          <div class="message-role">
            <el-tag size="small" :type="item.toolCall.output !== undefined ? 'success' : 'warning'">
              {{ item.toolCall.name }}
            </el-tag>
            <span v-if="item.toolCall.output === undefined" class="tool-call-label">{{ _('Executing...') }}</span>
            <span v-else class="tool-call-label">{{ _('Done') }}</span>
          </div>
          <div class="tool-call-detail">
            <div class="tool-call-section">
              <div class="tool-call-label">{{ _('Arguments') }}:</div>
              <pre class="tool-call-json">{{ formatJson(item.toolCall.arguments) }}</pre>
            </div>
            <div v-if="item.toolCall.output !== undefined" class="tool-call-section">
              <div class="tool-call-label">{{ _('Output') }}:</div>
              <pre class="tool-call-json">{{ item.toolCall.output }}</pre>
            </div>
          </div>
        </div>

        <div v-else-if="item.type === 'output'" class="chat-message assistant">
          <div class="message-role">{{ _('AI') }}</div>
          <div class="message-content markdown-body" v-html="renderMarkdown(item.text!)"></div>
          <span v-if="idx === streamingItems.length - 1" class="cursor">|</span>
        </div>
      </template>
    </div>
    <div class="chat-input">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        :placeholder="_('Describe pipeline changes...')"
        :disabled="streaming"
        @keydown.enter.exact.prevent="sendMessage"
      />
      <el-button
        type="primary"
        :disabled="!inputText.trim() || streaming"
        :loading="streaming"
        @click="sendMessage"
        :icon="Promotion"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { ChatDotRound, Promotion } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { _ } from '@/i18n'
import { chatAgent } from '@/requests'

const md = MarkdownIt().use(texmath, {
  engine: katex,
  delimiters: ['dollars', 'brackets', 'doxygen', 'gitlab'],
})

// --- Types ---

interface ToolCallEntry {
  name: string
  arguments: Record<string, any>
  output?: string
}

type AssistantType = 'output' | 'reasoning' | 'tool_call'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  assistantType?: AssistantType
  toolCall?: ToolCallEntry
}

type StreamItemType = 'reasoning' | 'output' | 'tool_call'

interface StreamItem {
  _key: number
  type: StreamItemType
  text?: string
  toolCall?: ToolCallEntry
  _callId?: string
}

interface ContextItem {
  role?: string
  content?: any
  type?: string
  name?: string
  arguments?: string | Record<string, any>
  call_id?: string
  output?: string
}

// --- Props & Emits ---

const props = defineProps<{
  pipelineJson: object
  pipelineId?: string
}>()

const emit = defineEmits<{
  (e: 'update:pipelineJson', data: object): void
}>()

// --- State ---

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const streaming = ref(false)
const messagesRef = ref<HTMLElement>()
const context = ref<ContextItem[]>([])
const streamingItems = ref<StreamItem[]>([])
let _nextKey = 0

// --- Helpers ---

function renderMarkdown(text: string): string {
  return md.render(text)
}

function formatJson(obj: any): string {
  if (typeof obj === 'string') {
    try {
      return JSON.stringify(JSON.parse(obj), null, 2)
    } catch {
      return obj
    }
  }
  return JSON.stringify(obj, null, 2)
}

function scrollToBottom() {
  nextTick(() => {
    const el = messagesRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function clearChat() {
  messages.value = []
  context.value = []
  inputText.value = ''
  streamingItems.value = []
}

function parseToolCallArgs(args: any): Record<string, any> {
  if (typeof args === 'string') {
    try { return JSON.parse(args) } catch { return { raw: args } }
  }
  return args || {}
}

// --- Pipeline switch clears context ---

watch(() => props.pipelineId, (newId, oldId) => {
  // Only clear when switching between different pipelines (not on mount/unmount)
  if (oldId && newId && oldId !== newId) {
    clearChat()
  }
})

// --- Send message ---

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  streaming.value = true
  streamingItems.value = []
  _nextKey = 0
  scrollToBottom()

  try {
    const response = await chatAgent({
      user_input: text,
      history: context.value,
      pipeline: props.pipelineJson,
    })

    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || `HTTP ${response.status}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))

          switch (data.event) {
            case 'output': {
              const items = streamingItems.value
              const last = items[items.length - 1]
              if (last && last.type === 'output') {
                last.text! += data.value
              } else {
                items.push({ _key: _nextKey++, type: 'output', text: data.value })
              }
              scrollToBottom()
              break
            }

            case 'reasoning': {
              const items = streamingItems.value
              const last = items[items.length - 1]
              if (last && last.type === 'reasoning') {
                last.text! += data.value
              } else {
                items.push({ _key: _nextKey++, type: 'reasoning', text: data.value })
              }
              scrollToBottom()
              break
            }

            case 'content': {
              const val = data.value as ContextItem
              if (val.type === 'function_call' && val.name && val.call_id) {
                streamingItems.value.push({
                  _key: _nextKey++,
                  type: 'tool_call',
                  toolCall: {
                    name: val.name,
                    arguments: parseToolCallArgs(val.arguments),
                    output: undefined,
                  },
                  _callId: val.call_id,
                })
              } else if (val.type === 'function_call_output' && val.call_id) {
                const item = streamingItems.value.find(
                  s => s.type === 'tool_call' && s._callId === val.call_id
                )
                if (item && item.toolCall && val.output !== undefined) {
                  item.toolCall.output = val.output
                }
              } else if (data.data_type === 'exception') {
                // Agent exception (e.g. a failed tool call) — surface it as an error message
                messages.value.push({
                  role: 'assistant',
                  content: String((val as any)?.content ?? JSON.stringify(val)),
                  assistantType: 'output',
                })
              }
              // reasoning_item_created / message_output_created are ignored:
              // their text is already captured via reasoning/output delta events
              scrollToBottom()
              break
            }

            case 'context':
              // Emitted whenever the agent modified the pipeline through a tool.
              // data.value is the full Pipeline object — push it back to the editor.
              if (data.value && typeof data.value === 'object') {
                emit('update:pipelineJson', data.value)
              }
              scrollToBottom()
              break

            case 'history':
              // Full conversation history to send with the next request
              context.value = data.value as ContextItem[]
              scrollToBottom()
              break
          }
        } catch {
          // skip malformed SSE
        }
      }
    }

    // Convert streaming items to final messages
    for (const item of streamingItems.value) {
      if (item.type === 'reasoning' && item.text) {
        messages.value.push({ role: 'assistant', content: item.text, assistantType: 'reasoning' })
      } else if (item.type === 'output' && item.text) {
        messages.value.push({ role: 'assistant', content: item.text, assistantType: 'output' })
      } else if (item.type === 'tool_call' && item.toolCall) {
        messages.value.push({ role: 'assistant', content: '', assistantType: 'tool_call', toolCall: item.toolCall })
      }
    }
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: `Error: ${e.message}`, assistantType: 'output' })
  } finally {
    streaming.value = false
    streamingItems.value = []
    scrollToBottom()
  }
}
</script>

<style scoped>
.pipeline-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-left: 1px solid #ebeef5;
  background: #fafafa;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
  color: #303133;
}

.chat-header .el-icon {
  color: #409eff;
}

.clear-btn {
  margin-left: auto;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-hint {
  text-align: center;
  color: #909399;
  font-size: 12px;
  padding: 20px;
}

.chat-message {
  max-width: 90%;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.5;
}

.chat-message.user {
  align-self: flex-end;
  background: #409eff;
  color: #fff;
}

.chat-message.assistant {
  align-self: flex-start;
  background: #fff;
  color: #303133;
  border: 1px solid #e4e7ed;
}

.chat-message.reasoning {
  align-self: flex-start;
  background: #f0f4ff;
  color: #606266;
  border: 1px solid #d4dff7;
  font-size: 12px;
  font-style: italic;
}

.chat-message.tool-call-msg {
  align-self: flex-start;
  background: #fffaeb;
  color: #303133;
  border: 1px solid #f5dab1;
  max-width: 85%;
}

.message-role {
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 2px;
  opacity: 0.7;
  display: flex;
  align-items: center;
  gap: 6px;
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-content.markdown-body {
  white-space: normal;
}

.message-content.markdown-body :deep(p) {
  margin: 0 0 4px;
}

.message-content.markdown-body :deep(pre) {
  margin: 4px 0;
  padding: 6px 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
}

.message-content.markdown-body :deep(code) {
  font-size: 12px;
  background: rgba(0,0,0,0.04);
  padding: 1px 4px;
  border-radius: 2px;
}

.message-content.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}

.cursor {
  animation: blink 1s step-end infinite;
  color: #409eff;
}

@keyframes blink {
  50% { opacity: 0; }
}

.tool-call-detail {
  margin-top: 2px;
}

.tool-call-label {
  font-size: 11px;
  color: #909399;
}

.tool-call-section {
  margin-top: 2px;
}

.tool-call-section .tool-call-label {
  font-size: 11px;
  color: #909399;
  margin-bottom: 2px;
}

.tool-call-json {
  margin: 0;
  padding: 4px 8px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 3px;
  font-size: 11px;
  line-height: 1.4;
  overflow-x: auto;
  white-space: pre;
  max-height: 120px;
  overflow-y: auto;
}

.chat-input {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-top: 1px solid #ebeef5;
  flex-shrink: 0;
  align-items: flex-end;
}

.chat-input .el-textarea {
  flex: 1;
}
</style>
