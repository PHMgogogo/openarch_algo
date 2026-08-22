<script lang="ts">
export const NODE_WIDTH = 250
</script>

<script setup lang="ts">
import { ElCard } from 'element-plus'
import { inject, onMounted, onUnmounted, ref } from 'vue'
import { EventType } from '@logicflow/core'
import type { NodeData } from './NodeData';
import { _ } from '@/i18n'

const props = defineProps<{
    node: {
        properties: {
            data: NodeData
        }
    }
}>()

const getNode = inject<() => any>('getNode')
const getGraph = inject<() => any>('getGraph')

const displayData = ref<NodeData>({ ...props.node.properties.data })

let cleanup: (() => void) | null = null

onMounted(() => {
    const node = getNode?.()
    const graph = getGraph?.()
    if (!node || !graph) return

    const handler = (eventData: any) => {
        if (eventData.id === node.id && eventData.properties?.data) {
            displayData.value = { ...eventData.properties.data }
        }
    }
    graph.eventCenter.on(EventType.NODE_PROPERTIES_CHANGE, handler)

    cleanup = () => {
        graph.eventCenter.off(EventType.NODE_PROPERTIES_CHANGE, handler)
    }
})

onUnmounted(() => {
    cleanup?.()
})
</script>
<template>
    <ElCard shadow="hover" style="width: 250px; min-width: 250px; max-width: 250px;" class="node-card">
        <div v-if="displayData.order >= 0" class="node-order">{{ displayData.order + 1 }}</div>
        <div class="node-type">{{ _(displayData.node_type) }}</div>
        <div class="title">{{ displayData.title || displayData.id }}</div>
    </ElCard>
</template>
<style scoped>
.node-card {
  position: relative;
}

.node-order {
  position: absolute;
  top: 4px;
  right: 8px;
  background: #409eff;
  color: #fff;
  font-size: 11px;
  font-weight: bold;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.title {
    font-weight: bold;
}

.node-type {
    color: gray;
    font-size: small;
}

.content {
    font-size: medium;
}

.node-id {
    color: gray;
    font-size: x-small;
    text-align: right;
}
</style>