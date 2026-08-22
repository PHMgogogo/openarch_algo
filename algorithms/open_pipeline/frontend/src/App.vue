<script setup lang="ts">
import { onMounted, ref, toRaw, provide } from 'vue'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import Canvas from './components/Canvas.vue';
import Menu from './components/Menu.vue';
import NodeList from './components/NodeList.vue';
import Navigator from './components/Navigator.vue';
import CronPanel from './components/CronPanel.vue';
import LogicFlow from '@logicflow/core'
import { NODE_WIDTH } from "./components/Node.vue"
import type { PipelineData } from './components/PipelineData.ts';
import Editor from './components/Editor.vue';
import RunResult from './components/RunResult.vue';
import JsonEditor from './components/JsonEditor.vue';
import PipelineChat from './components/PipelineChat.vue';
import { ElMessage, ElMessageBox } from 'element-plus'
import { _ } from './i18n'
import { getPipelineList, createPipeline, renamePipeline, deletePipeline, getPipeline, savePipeline, runPipeline, getNodeHelp } from './requests'

const graphConfigData = ref<LogicFlow.GraphConfigData>({
  nodes: [],
  edges: [
  ]
})
function buildNodesFromPipeline(
  nodesData: PipelineData["nodes"],
  autoLayout: boolean = true,
  cell_width: number = 300,
  cell_height: number = 100,
) {
  let orderGroups: Record<number, typeof nodesData> = {}
  for (let node_id in nodesData) {
    let node = nodesData[node_id]
    let order = node?.order ?? -1
    if (!orderGroups[order]) {
      orderGroups[order] = {}
    }
    orderGroups[order][node_id] = node
  }

  let nodes: any[] = []
  for (let order of Object.keys(orderGroups).map(Number).sort((a, b) => a - b)) {
    let group = orderGroups[order]
    let i = 0
    for (let node_id in group) {
      let node = group[node_id]
      let x = autoLayout ? order * cell_width : (node?.x ?? order * cell_width)
      let y = autoLayout ? i * cell_height : (node?.y ?? i * cell_height)
      nodes.push(
        {
          id: node_id,
          type: "node",
          x,
          y,
          properties: {
            data: node,
            width: NODE_WIDTH
          }
        }
      )
      i++
    }
  }
  return nodes
}

const pipelineList = ref<string[]>([])
const activePipeline = ref("")
const pipelineMeta = ref<Record<string, any>>({})

async function fetchPipelineList() {
  const result = await getPipelineList()
  pipelineList.value = result.data ?? []
}

async function onPipelineSelect(id: string | undefined) {
  if (!id) return
  if (id === activePipeline.value) return
  activePipeline.value = id
  selectedNode.value = null
  await editorRef.value?.updateNode(null)
  runResult.value = null
  runError.value = null
  await loadPipeline(id)
  if (viewMode.value === 'json') {
    pipelineJson.value = serializePipeline()
  }
}

async function onPipelineCreate() {
  try {
    const { value } = await ElMessageBox.prompt(_('Please enter pipeline name'), _('New Pipeline'), {
      confirmButtonText: _('OK'),
      cancelButtonText: _('Cancel'),
      inputPattern: /^[A-Za-z0-9_-]+$/,
      inputErrorMessage: _('Only letters, numbers, underscores and hyphens are allowed'),
    })
    if (!value) return
    await createPipeline(value)
    await fetchPipelineList()
    await onPipelineSelect(value)
    ElMessage.success(_('Pipeline created'))
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(_('Create failed') + ': ' + e.message)
    }
  }
}

async function onPipelineRename(oldId: string) {
  try {
    const { value } = await ElMessageBox.prompt(_('Please enter new pipeline name'), _('Rename Pipeline'), {
      confirmButtonText: _('OK'),
      cancelButtonText: _('Cancel'),
      inputValue: oldId,
      inputPattern: /^[A-Za-z0-9_-]+$/,
      inputErrorMessage: _('Only letters, numbers, underscores and hyphens are allowed'),
    })
    if (!value || value === oldId) return
    await renamePipeline(oldId, value)
    await fetchPipelineList()
    if (activePipeline.value === oldId) {
      activePipeline.value = value
      await loadPipeline(value)
    }
    ElMessage.success(_('Pipeline renamed'))
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(_('Rename failed') + ': ' + e.message)
    }
  }
}

async function onPipelineDelete(id: string) {
  try {
    await deletePipeline(id)
    await fetchPipelineList()
    if (activePipeline.value === id) {
      activePipeline.value = ''
      if (pipelineList.value.length > 0) {
        await onPipelineSelect(pipelineList.value[0])
      } else {
        graphConfigData.value = { nodes: [], edges: [] }
        canvasRef.value?.render(graphConfigData)
      }
    }
    ElMessage.success(_('Pipeline deleted'))
  } catch (e: any) {
    ElMessage.error(_('Delete failed') + ': ' + e.message)
  }
}

async function loadPipeline(id: string) {
  let data = await getPipeline<PipelineData>(id)
  pipelineMeta.value = { ...data }
  delete pipelineMeta.value.nodes
  let nodes = buildNodesFromPipeline(data.nodes)
  let edges: any[] = []
  let edgeSet = new Set<string>()

  for (let node_id in data.nodes) {
    let node = data.nodes[node_id]
    for (let targetId of [...(node?.next ?? []), ...(node?.prev ?? [])]) {
      let sourceId: string
      if ((node?.next ?? []).includes(targetId)) {
        sourceId = node_id
      } else {
        sourceId = targetId
        targetId = node_id
      }
      let key = `${sourceId}->${targetId}`
      if (!edgeSet.has(key)) {
        edgeSet.add(key)
        edges.push({
          id: key,
          type: "bezier",
          sourceNodeId: sourceId,
          targetNodeId: targetId,
          sourceAnchorId: `${sourceId}_1`,
          targetAnchorId: `${targetId}_3`,
        })
      }
    }
  }
  graphConfigData.value = { nodes, edges }
  canvasRef.value?.render(graphConfigData)
}
const canvasRef = ref<InstanceType<typeof Canvas>>()
const editorRef = ref<InstanceType<typeof Editor>>()
const selectedNode = ref<{ id: string; properties: Record<string, any> } | null>(null)

async function onNodeSelected(data: { id: string; properties: Record<string, any> } | null) {
  selectedNode.value = data
  await editorRef.value?.updateNode(data?.properties?.data)
}

function updateOrder() {
  const nodes = graphConfigData.value.nodes || []
  const edges = graphConfigData.value.edges || []

  const indegree: Record<string, number> = {}
  const adj: Record<string, string[]> = {}
  for (const node of nodes) {
    const id = node.id!
    indegree[id] = 0
    adj[id] = []
  }
  for (const edge of edges) {
    if (!edge.sourceNodeId || !edge.targetNodeId) continue
    if (!adj[edge.sourceNodeId]) adj[edge.sourceNodeId] = []
    adj[edge.sourceNodeId]!.push(edge.targetNodeId)
    indegree[edge.targetNodeId] = (indegree[edge.targetNodeId] || 0) + 1
  }

  const queue: string[] = []
  for (const id in indegree) {
    if (indegree[id] === 0) queue.push(id)
  }

  const orderMap: Record<string, number> = {}
  let order = 0
  while (queue.length > 0) {
    const nextQueue: string[] = []
    for (const id of queue) {
      orderMap[id] = order
      for (const nextId of adj[id]!) {
        indegree[nextId]!--
        if (indegree[nextId] === 0) {
          nextQueue.push(nextId)
        }
      }
    }
    queue.length = 0
    queue.push(...nextQueue)
    order++
  }

  for (const node of nodes) {
    const id = node.id!
    if (orderMap[id] !== undefined && node.properties?.data) {
      node.properties.data.order = orderMap[id]
    }
  }
}

function onEdgeAdded(data: LogicFlow.EdgeData) {
  graphConfigData.value.edges = [...((graphConfigData.value.edges) || []), data]

  const sourceNode = graphConfigData.value.nodes?.find(n => n.id === data.sourceNodeId)
  const targetNode = graphConfigData.value.nodes?.find(n => n.id === data.targetNodeId)
  if (!sourceNode || !targetNode) return

  const srcData = sourceNode.properties?.data
  const tgtData = targetNode.properties?.data

  if (!srcData.next) srcData.next = []
  if (!tgtData.prev) tgtData.prev = []
  if (!srcData.next.includes(data.targetNodeId)) {
    srcData.next.push(data.targetNodeId)
  }
  if (!tgtData.prev.includes(data.sourceNodeId)) {
    tgtData.prev.push(data.sourceNodeId)
  }
  updateOrder()
  canvasRef.value?.updateNodeProperties(data.sourceNodeId, sourceNode.properties || {})
  canvasRef.value?.updateNodeProperties(data.targetNodeId, targetNode.properties || {})
}

function onEdgeDeleted(data: LogicFlow.EdgeData) {
  const sourceNode = graphConfigData.value.nodes?.find(n => n.id === data.sourceNodeId)
  const targetNode = graphConfigData.value.nodes?.find(n => n.id === data.targetNodeId)
  if (!sourceNode || !targetNode) return

  graphConfigData.value.edges = graphConfigData.value.edges?.filter(e => e.id !== data.id)

  const srcData = sourceNode.properties?.data
  const tgtData = targetNode.properties?.data

  if (srcData.next) {
    srcData.next = srcData.next.filter((id: string) => id !== data.targetNodeId)
  }
  if (tgtData.prev) {
    tgtData.prev = tgtData.prev.filter((id: string) => id !== data.sourceNodeId)
  }
  updateOrder()
  canvasRef.value?.updateNodeProperties(data.sourceNodeId, sourceNode.properties || {})
  canvasRef.value?.updateNodeProperties(data.targetNodeId, targetNode.properties || {})
}

function onNodeDragged({ id, x, y }: { id: string; x: number; y: number }) {
  const node = graphConfigData.value.nodes?.find(n => n.id === id)
  if (node) {
    node.x = x
    node.y = y
  }
}

function onNodeAdded(data: LogicFlow.NodeData) {
  graphConfigData.value.nodes = [...toRaw(graphConfigData.value.nodes || []), data]
}

async function onNodeDeleted(data: LogicFlow.NodeData) {
  const deletedId = data.id!

  for (const node of (graphConfigData.value.nodes || [])) {
    const nodeData = node.properties?.data
    if (!nodeData) continue
    if (nodeData.next) {
      nodeData.next = nodeData.next.filter((id: string) => id !== deletedId)
    }
    if (nodeData.prev) {
      nodeData.prev = nodeData.prev.filter((id: string) => id !== deletedId)
    }
  }

  graphConfigData.value.nodes = (graphConfigData.value.nodes || []).filter(n => n.id !== deletedId)
  graphConfigData.value.edges = (graphConfigData.value.edges || []).filter(
    e => e.sourceNodeId !== deletedId && e.targetNodeId !== deletedId
  )

  if (selectedNode.value?.id === deletedId) {
    selectedNode.value = null
    await editorRef.value?.updateNode(null)
  }
}

function onNodeSaved(data: { id: string; properties: Record<string, any> }) {
  canvasRef.value?.updateNodeProperties(data.id, data.properties)
}

const runResult = ref<{ output: string[]; performance: any[]; data: Record<string, any[]>; state: Record<string, any> } | null>(null)
const runError = ref<{ error: string; error_type: string; traceback: string } | null>(null)
const cronExecutedAt = ref<string | null>(null)
const running = ref(false)
const saving = ref(false)

async function onRun() {
  running.value = true
  runResult.value = null
  runError.value = null
  cronExecutedAt.value = null

  const nodes: Record<string, any> = {}
  for (const node of (graphConfigData.value.nodes || [])) {
    nodes[node.id ?? ""] = { ...node.properties?.data, x: node.x, y: node.y }
  }

  const pipeline = {
    id: activePipeline.value,
    nodes,
  }

  try {
    runResult.value = await runPipeline(pipeline)
    ElMessage.success(_('Pipeline run success'))
  } catch (e: any) {
    runError.value = e?.data ?? null
    ElMessage.error(_('Run failed') + ': ' + e.message)
  } finally {
    running.value = false
  }
}

async function onSave() {
  saving.value = true

  const nodes: Record<string, any> = {}
  for (const node of (graphConfigData.value.nodes || [])) {
    nodes[node.id ?? ""] = { ...node.properties?.data, x: node.x, y: node.y }
  }

  const pipeline = {
    id: activePipeline.value,
    nodes,
  }

  try {
    await savePipeline(pipeline)
    ElMessage.success(_('Pipeline save success'))
  } catch (e: any) {
    ElMessage.error(_('Save failed') + ': ' + e.message)
  } finally {
    saving.value = false
  }
}

function onGraphUpdated(data: LogicFlow.GraphConfigData) {
  graphConfigData.value = data
}

function onCronShowContext(data: any) {
  runResult.value = data
  runError.value = null
  cronExecutedAt.value = data.executed_at ?? null
}

function onAutoLayout() {
  updateOrder()
  const nodesData: Record<string, any> = {}
  for (const node of (graphConfigData.value.nodes || [])) {
    nodesData[node.id ?? ""] = { ...node.properties?.data, x: node.x, y: node.y }
  }
  const nodes = buildNodesFromPipeline(nodesData as PipelineData["nodes"], true)
  const edges = (graphConfigData.value.edges || []).map((edge: any) => ({
    id: edge.id,
    type: edge.type || "bezier",
    sourceNodeId: edge.sourceNodeId,
    targetNodeId: edge.targetNodeId,
    sourceAnchorId: edge.sourceAnchorId,
    targetAnchorId: edge.targetAnchorId,
  }))
  graphConfigData.value = { nodes, edges }
  canvasRef.value?.render(graphConfigData)
}

const viewMode = ref<'graph' | 'json'>('graph')
const pipelineJson = ref<object>({})

function serializePipeline(): object {
  const nodes: Record<string, any> = {}
  for (const node of (graphConfigData.value.nodes || [])) {
    nodes[node.id ?? ""] = { ...node.properties?.data, x: node.x, y: node.y }
  }
  return { ...pipelineMeta.value, nodes }
}

function deserializePipeline(json: any) {
  const nodesData = (json?.nodes as Record<string, any>) ?? json ?? {}
  if (json?.nodes) {
    const { nodes, ...meta } = json
    pipelineMeta.value = meta
  }
  const nodes = buildNodesFromPipeline(nodesData as PipelineData["nodes"], false)
  const edges: any[] = []
  const edgeSet = new Set<string>()

  for (const node_id in nodesData) {
    const node = nodesData[node_id]
    for (let targetId of [...(node?.next ?? []), ...(node?.prev ?? [])]) {
      let sourceId: string
      if ((node?.next ?? []).includes(targetId)) {
        sourceId = node_id
      } else {
        sourceId = targetId
        targetId = node_id
      }
      const key = `${sourceId}->${targetId}`
      if (!edgeSet.has(key)) {
        edgeSet.add(key)
        edges.push({
          id: key,
          type: "bezier",
          sourceNodeId: sourceId,
          targetNodeId: targetId,
          sourceAnchorId: `${sourceId}_1`,
          targetAnchorId: `${targetId}_3`,
        })
      }
    }
  }
  graphConfigData.value = { nodes, edges }
  canvasRef.value?.render(graphConfigData)
}

function onToggleView() {
  if (viewMode.value === 'graph') {
    pipelineJson.value = serializePipeline()
    viewMode.value = 'json'
  } else {
    deserializePipeline(pipelineJson.value)
    viewMode.value = 'graph'
  }
}

function onJsonUpdate(val: object) {
  pipelineJson.value = val
}

function onChatPipelineUpdate(val: object) {
  pipelineJson.value = val
  deserializePipeline(val)
}

const md = MarkdownIt().use(texmath, {
  engine: katex,
  delimiters: ['dollars', 'brackets', 'doxygen', 'gitlab'],
})

const nodeHelpCache = new Map<string, string>()
const nodeHelpContent = ref('')
const nodeHelpLoading = ref(false)

async function selectNodeHelp(nodeType: string) {
  if (nodeHelpCache.has(nodeType)) {
    nodeHelpContent.value = md.render(nodeHelpCache.get(nodeType)!)
    return
  }

  nodeHelpLoading.value = true
  nodeHelpContent.value = ''

  try {
    const response = await getNodeHelp(nodeType)
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullText = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.delta) {
              fullText += data.delta
              nodeHelpContent.value = md.render(fullText)
            } else if (data.full) {
              fullText = data.full
              nodeHelpContent.value = md.render(fullText)
              nodeHelpCache.set(nodeType, fullText)
            }
          } catch { /* skip malformed SSE line */ }
        }
      }
    }
  } catch (e: any) {
    nodeHelpContent.value = md.render(`**${_('Request failed')}**: ${e.message}`)
  } finally {
    nodeHelpLoading.value = false
  }
}

provide('selectNodeHelp', selectNodeHelp)
provide('nodeHelpContent', nodeHelpContent)
provide('nodeHelpLoading', nodeHelpLoading)

onMounted(async () => {
  await fetchPipelineList()
  if (pipelineList.value.length > 0) {
    await onPipelineSelect(pipelineList.value[0])
  }
})

</script>

<template>
  <div class="app-layout">
    <Menu @run="onRun" @save="onSave" @auto-layout="onAutoLayout" @toggle-view="onToggleView"
      :running="running" :saving="saving" :view-mode="viewMode" />
    <div class="main-area">
      <div class="left-panel">
        <div class="nav-sidebar">
          <Navigator :pipelines="pipelineList" :active-id="activePipeline" @select="onPipelineSelect"
            @create="onPipelineCreate" @rename="onPipelineRename" @delete="onPipelineDelete" />
        </div>
        <div class="cron-panel">
          <CronPanel :pipeline-id="activePipeline" @show-context="onCronShowContext" />
        </div>
      </div>
      <div class="editor-area">
        <el-container class="editor-top">
          <template v-if="viewMode === 'graph'">
            <el-aside width="15%">
              <NodeList :canvas-ref="canvasRef" />
            </el-aside>
            <el-main><Canvas ref="canvasRef" :graph-config-data="graphConfigData" @node-selected="onNodeSelected"
                @edge-added="onEdgeAdded" @edge-deleted="onEdgeDeleted" @node-dragged="onNodeDragged"
                @node-added="onNodeAdded" @node-deleted="onNodeDeleted" @graph-updated="onGraphUpdated" /></el-main>
            <el-aside width="25%">
              <Editor ref="editorRef" :data="selectedNode?.properties?.data" :graph-config-data="graphConfigData"
                @save="onNodeSaved"></Editor>
            </el-aside>
          </template>
          <template v-else>
            <el-main>
              <JsonEditor :json="pipelineJson" @update:json="onJsonUpdate" />
            </el-main>
            <el-aside width="25%">
              <PipelineChat :pipeline-json="pipelineJson" :pipeline-id="activePipeline" @update:pipeline-json="onChatPipelineUpdate" />
            </el-aside>
          </template>
        </el-container>
        <div class="run-result">
          <el-divider />
          <h3>
            {{ _('Running Result') }}
            <span v-if="cronExecutedAt" class="cron-executed-at">{{ cronExecutedAt }}</span>
          </h3>
          <RunResult :run-result="runResult" :run-error="runError" :running="running" />
        </div>
      </div>
    </div>
  </div>
</template>

<style>
* {
  margin: 0;
  box-sizing: border-box;
}

.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-area {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.left-panel {
  width: 10%;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #ebeef5;
  overflow: hidden;
}

.nav-sidebar {
  flex: 0 0 60%;
  min-height: 0;
  overflow-y: auto;
}

.cron-panel {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border-top: 1px solid #ebeef5;
}

.editor-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-top {
  height: 60%;
  min-height: 0;
}

.editor-top .el-aside {
  overflow-y: auto;
  height: 100%;
}

.editor-top .el-main {
  overflow: hidden;
  padding: 0 8px;
}

.run-result {
  height: 40%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 15px 10px;
  overflow: hidden;
}

.run-result .el-divider {
  margin: 4px 0;
}

.run-result h3 {
  margin-bottom: 6px;
  flex-shrink: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.cron-executed-at {
  font-size: 13px;
  font-weight: 400;
  color: #909399;
}
</style>
