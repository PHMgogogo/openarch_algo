<template>
  <div ref="containerRef" class="json-editor-container"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import JSONEditor from 'jsoneditor'
import 'jsoneditor/dist/jsoneditor.css'

const props = defineProps<{
  json: object
}>()

const emit = defineEmits<{
  (e: 'update:json', data: object): void
}>()

const containerRef = ref<HTMLElement>()
let editor: JSONEditor | null = null
let internalChange = false

onMounted(() => {
  editor = new JSONEditor(containerRef.value!, {
    mode: 'code',
    modes: ['code', 'tree', 'view', 'form'],
    onChange: () => {
      try {
        internalChange = true
        const updated = editor!.get()
        emit('update:json', updated)
      } catch {
        // JSON parse error, ignore
      }
    },
  })
  editor.set(props.json)
})

watch(() => props.json, (val) => {
  if (internalChange) {
    internalChange = false
    return
  }
  if (editor) {
    editor.set(val)
  }
}, { deep: true })

onUnmounted(() => {
  if (editor) {
    editor.destroy()
    editor = null
  }
})
</script>

<style scoped>
.json-editor-container {
  width: 100%;
  height: 100%;
}

.json-editor-container :deep(.jsoneditor-poweredBy) {
  display: none;
}
</style>
