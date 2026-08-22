<template>
  <div ref="containerRef" class="flow" :class="{ focused: canvasFocused }" tabindex="-1"></div>
</template>
<script setup lang="ts">
import { ref, onMounted, onUnmounted, toRaw } from 'vue'
import type { Ref } from 'vue'
import LogicFlow, { costByPoints } from '@logicflow/core'
import '@logicflow/core/dist/index.css'
import Node from "./Node.vue"
import { register, VueNodeModel } from '@logicflow/vue-node-registry'
import type { Model } from '@logicflow/core'

class PipelineNodeModel extends VueNodeModel {
  constructor(data: any, graphModel: any) {
    super(data, graphModel)
    this.sourceRules = [
      {
        message: '',
        validate: (_source, _target, sourceAnchor) => {
          return sourceAnchor?.id?.endsWith('_1')
        },
      },
    ]

    this.targetRules = [
      {
        message: '',
        validate: (_source, _target, _sourceAnchor, targetAnchor) => {
          return targetAnchor?.id?.endsWith('_3')
        },
      },
    ]
  }

  getDefaultAnchor(): Model.AnchorConfig[] {
    const { x, y, width, height } = this
    return [
      { x: x + width / 2, y: y, id: `${this.id}_1` },
      { x: x - width / 2, y: y, id: `${this.id}_3` },
    ]
  }
}

const props = defineProps<{
  graphConfigData: LogicFlow.GraphConfigData
}>()

const emit = defineEmits<{
  (e: 'node-selected', data: { id: string; properties: Record<string, any> } | null): void
  (e: 'edge-added', data: LogicFlow.EdgeData): void
  (e: 'edge-deleted', data: LogicFlow.EdgeData): void
  (e: 'node-dragged', data: { id: string; x: number; y: number }): void
  (e: 'node-added', data: LogicFlow.NodeData): void
  (e: 'node-deleted', data: LogicFlow.NodeData): void
  (e: 'graph-updated', data: LogicFlow.GraphConfigData): void
}>()

const containerRef = ref()
const canvasFocused = ref(false)
let lf: LogicFlow
let selectedEdge: { id: string } | null = null
let selectedNodeId: string | null = null
let mouseDownInCanvas = false

function handleKeydown(e: KeyboardEvent) {
  if (!containerRef.value || !containerRef.value.contains(document.activeElement)) return
  // Undo: Ctrl+Z
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
    e.preventDefault()
    lf.undo()
    // Force re-render so Vue node components reflect restored properties
    const data = lf.getGraphData() as LogicFlow.GraphConfigData
    lf.clearData()
    lf.render(data)
    selectedNodeId = null
    selectedEdge = null
    emit('node-selected', null)
    emit('graph-updated', data)
    return
  }

  // Redo: Ctrl+Y or Ctrl+Shift+Z
  if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) {
    e.preventDefault()
    lf.redo()
    const data = lf.getGraphData() as LogicFlow.GraphConfigData
    lf.clearData()
    lf.render(data)
    selectedNodeId = null
    selectedEdge = null
    emit('node-selected', null)
    emit('graph-updated', data)
    return
  }

  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedNodeId) {
      const nodeData = lf.getNodeModelById(selectedNodeId)?.getData()
      const graphData = lf.getGraphData() as LogicFlow.GraphConfigData
      const connectedEdges = (graphData.edges || []).filter(
        edge => edge.sourceNodeId === selectedNodeId || edge.targetNodeId === selectedNodeId
      )
      for (const edge of connectedEdges) {
        lf.deleteEdge(edge.id!)
        emit('edge-deleted', edge as LogicFlow.EdgeData)
      }
      lf.deleteNode(selectedNodeId)
      if (nodeData) {
        emit('node-deleted', nodeData as LogicFlow.NodeData)
      }
      selectedNodeId = null
      return
    }
    if (selectedEdge) {
      const edgeData = lf.getEdgeModelById(selectedEdge.id)?.getData()
      lf.deleteEdge(selectedEdge.id)
      if (edgeData) {
        emit('edge-deleted', edgeData as LogicFlow.EdgeData)
      }
      selectedEdge = null
    }
  }
}

function handleMouseDown() {
  mouseDownInCanvas = true
  canvasFocused.value = true
  containerRef.value?.focus()
}

function handleDocumentMouseDown(e: MouseEvent) {
  if (!containerRef.value?.contains(e.target as Node)) {
    canvasFocused.value = false
  }
}

function handleMouseUp() {
  mouseDownInCanvas = false
}

onMounted(() => {
  lf = new LogicFlow({
    container: containerRef.value,
    grid: true,
    edgeType: "bezier",
    textEdit: false,
    adjustEdge: false,
    stopZoomGraph: false,
    history: true
  })
  register({
    type: "node", component: Node, model: PipelineNodeModel as any,
  }, lf)
  lf.render(props.graphConfigData)
  const initialNodes = props.graphConfigData.nodes ?? []
  if (initialNodes.length > 0) {
    const xs = initialNodes.map(n => n.x ?? 0)
    const ys = initialNodes.map(n => n.y ?? 0)
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2
    lf.focusOn({ coordinate: { x: cx, y: cy } })
  }

  lf.on('node:click', ({ data }: any) => {
    selectedNodeId = data.id
    selectedEdge = null
    let emit_data = { id: data.id, properties: { ...data.properties, x: data.x, y: data.y } }
    emit('node-selected', emit_data)
  })

  lf.on('blank:click', () => {
    if (!mouseDownInCanvas) return
    selectedNodeId = null
    emit('node-selected', null)
    selectedEdge = null
  })
  lf.on('node:drag', ({ data }: any) => {
    emit('node-dragged', { id: data.id, x: data.x, y: data.y })
  })

  lf.on('edge:add', ({ data }: any) => {
    data.id = `${data.sourceNodeId}->${data.targetNodeId}`
    emit('edge-added', data)
  })

  lf.on('edge:click', ({ data }: any) => {
    selectedEdge = { id: data.id }
    selectedNodeId = null
  })

  lf.on('node:dnd-add', ({ data }: any) => {
    emit('node-added', data)
    emit('node-selected', data)
  })

  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('mousedown', handleDocumentMouseDown, true)

  containerRef.value.addEventListener('mousedown', handleMouseDown)
  document.addEventListener('mouseup', handleMouseUp)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('mousedown', handleDocumentMouseDown, true)
  document.removeEventListener('mouseup', handleMouseUp)
})

function updateNodeProperties(nodeId: string, properties: LogicFlow.PropertiesType) {
  if (lf) {
    delete properties.height
    lf.setProperties(nodeId, properties)
  }
}

function startDrag(nodeConfig: Record<string, unknown>) {
  if (lf) {
    lf.dnd.startDrag(nodeConfig as any)
  }
}
function render(data: Ref<LogicFlow.GraphConfigData>) {
  lf.clearData()
  lf?.render(data.value)

  const nodes = data.value.nodes ?? []
  if (nodes.length > 0) {
    const xs = nodes.map(n => n.x ?? 0)
    const ys = nodes.map(n => n.y ?? 0)
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2
    lf?.focusOn({ coordinate: { x: cx, y: cy } })
  }
}
defineExpose({ startDrag, updateNodeProperties, render })
</script>
<style>
.flow {
  width: 100%;
  height: 100%;
  outline: none;
  border: 2px solid transparent;
  border-radius: 4px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.flow.focused {
  border-color: #409eff;
  box-shadow: 0 0 8px rgba(64, 158, 255, 0.5);
}
</style>
