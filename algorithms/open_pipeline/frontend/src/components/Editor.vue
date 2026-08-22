<template>
    <el-text v-if="!formData" class="mx-1" size="large">{{ _('Select a node to edit') }}</el-text>
    <div v-if="formData" class="editor-header">
        <span class="node-type-name">{{ formData.node_type }}</span>
        <el-popover placement="bottom-end" :width="420" trigger="click">
            <template #reference>
                <el-button circle size="small" class="help-btn" @click="onHelpClick(formData.node_type)">
                    <el-icon><QuestionFilled /></el-icon>
                </el-button>
            </template>
            <div class="help-content markdown-body" v-if="helpContent" v-html="helpContent"></div>
            <div class="help-content help-loading" v-else-if="helpLoading">
                <el-icon class="is-loading"><Loading /></el-icon>
            </div>
            <div class="help-content help-empty" v-else>{{ _('Click to load help') }}</div>
        </el-popover>
    </div>
    <el-form v-if="formData && nodeSchema" :model="formData" :label-width="formData && nodeSchema ? 'auto' : '120px'"
        label-position="left">
        <el-form-item :label="_(nodeSchema?.properties.title.title)">
            <el-input v-model="formData.title" :placeholder="_('No Title')" />
        </el-form-item>
        <el-form-item :label="_(nodeSchema?.properties.id.title)">
            <el-input v-model="formData.id" :disabled="true" />
        </el-form-item>
        <el-form-item :label="_(nodeSchema?.properties.node_type.title)">
            <el-select v-model="formData.node_type" @change="getSchema">
                <el-option-group v-for="group in groupedNodeTypes" :key="group.category" :label="_(group.category)">
                    <el-option v-for="item in group.items" :key="item.node_type" :label="_(item.node_type)"
                        :value="item.node_type"></el-option>
                </el-option-group>
            </el-select>
        </el-form-item>
        <el-form-item :label="_(nodeSchema?.properties.read_data.title)"
            v-if="nodeSchema?.properties?.read_data?.maxItems !== 0">
            <el-dropdown @command="(cmd: string) => addTagTo(cmd, formData?.read_data)" style="width: 100%"
                :disabled="possibleReadData.length <= 0">
                <el-input-tag v-model="formData.read_data" draggable></el-input-tag>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item v-for="item in possibleReadData" :key="item" :label="item" :command="item">
                            {{ item }}</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </el-form-item>
        <el-form-item :label="_(nodeSchema?.properties.write_data.title)"
            v-if="nodeSchema?.properties?.write_data?.maxItems !== 0">
            <el-dropdown @command="(cmd: string) => addTagTo(cmd, formData?.write_data)" style="width: 100%"
                :disabled="possibleWriteData.length <= 0">
                <el-input-tag v-model="formData.write_data" draggable></el-input-tag>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item v-for="item in possibleWriteData" :key="item" :label="item" :command="item">
                            {{ item }}</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </el-form-item>
        <el-form-item :label="_(nodeSchema?.properties.read_state.title)"
            v-if="nodeSchema?.properties?.read_state?.maxItems !== 0">
            <el-dropdown @command="(cmd: string) => addTagTo(cmd, formData?.read_state)" style="width: 100%"
                :disabled="possibleReadState.length <= 0">
                <el-input-tag v-model="formData.read_state" draggable></el-input-tag>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item v-for="item in possibleReadState" :key="item" :label="item" :command="item">
                            {{ item }}</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </el-form-item>

        <el-form-item :label="_(nodeSchema?.properties.write_state.title)"
            v-if="nodeSchema?.properties?.write_state?.maxItems !== 0">
            <el-dropdown @command="(cmd: string) => addTagTo(cmd, formData?.write_state)" style="width: 100%"
                :disabled="possibleWriteState.length <= 0">
                <el-input-tag v-model="formData.write_state" draggable></el-input-tag>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item v-for="item in possibleWriteState" :key="item" :label="item" :command="item">
                            {{ item }}</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </el-form-item>
        <el-form-item :label="_(nodeSchema?.properties.prev.title)">
            <el-select v-model="formData.prev" multiple style="width:100%" :disabled="true" placeholder="">
                <el-option v-for="item in possibleNodeIds" :key="item" :label="item" :value="item"></el-option>
            </el-select>
        </el-form-item>
        <el-form-item :label="_(nodeSchema?.properties.next.title)">
            <el-select v-model="formData.next" multiple style="width:100%" :disabled="true" placeholder="">
                <el-option v-for="item in possibleNodeIds" :key="item" :label="item" :value="item"></el-option>
            </el-select>
        </el-form-item>
        <template v-if="nodeSchema" v-for="key in Object.keys(nodeSchema.$defs.Parameters.properties)" :key="key">
            <el-form-item v-if="['InferenceNode', 'TrainNode'].includes(formData.node_type) && key == 'instance'"
                :label="_(nodeSchema.$defs.Parameters.properties[key].title)">
                <el-select v-model="formData.parameters[key]"
                    :placeholder="nodeSchema.$defs.Parameters.properties[key].default">
                    <el-option v-for="instance in instances" :key="instance.id" :label="instance.id"
                        :value="instance.id" />
                </el-select>
            </el-form-item>
            <el-form-item v-if="key == 'jinja_prompt'"
                :label="_(nodeSchema.$defs.Parameters.properties[key].title)">
                <div class="jinja-editor">
                    <div class="jinja-toolbar">
                        <el-dropdown @command="(cmd: string) => insertJinjaVar('data', cmd)"
                            :disabled="possibleReadData.length <= 0">
                            <el-button size="small">{{ _('Insert Data') }}</el-button>
                            <template #dropdown>
                                <el-dropdown-menu>
                                    <el-dropdown-item v-for="item in possibleReadData" :key="item" :command="item">
                                        data.{{ item }}</el-dropdown-item>
                                </el-dropdown-menu>
                            </template>
                        </el-dropdown>
                        <el-dropdown @command="(cmd: string) => insertJinjaVar('state', cmd)"
                            :disabled="possibleReadState.length <= 0">
                            <el-button size="small">{{ _('Insert State') }}</el-button>
                            <template #dropdown>
                                <el-dropdown-menu>
                                    <el-dropdown-item v-for="item in possibleReadState" :key="item" :command="item">
                                        state.{{ item }}</el-dropdown-item>
                                </el-dropdown-menu>
                            </template>
                        </el-dropdown>
                    </div>
                    <el-input ref="jinjaTextareaRef" v-model="formData.parameters[key]" type="textarea" :rows="8"
                        :placeholder="String(nodeSchema.$defs.Parameters.properties[key].default ?? '')" />
                </div>
            </el-form-item>
            <el-form-item v-else-if="nodeSchema.$defs.Parameters.properties[key].type === 'boolean'"
                :label="_(nodeSchema.$defs.Parameters.properties[key].title)">
                <el-checkbox v-model="formData.parameters[key]" />
            </el-form-item>
            <el-form-item v-else-if="nodeSchema.$defs.Parameters.properties[key].type === 'number'"
                :label="_(nodeSchema.$defs.Parameters.properties[key].title)">
                <el-input-number v-model="formData.parameters[key]"
                    :placeholder="String(nodeSchema.$defs.Parameters.properties[key].default)" />
            </el-form-item>
            <el-form-item v-else-if="nodeSchema.$defs.Parameters.properties[key].type === 'array'"
                :label="_(nodeSchema.$defs.Parameters.properties[key].title)">
                <el-input-tag v-model="formData.parameters[key]" draggable></el-input-tag>
            </el-form-item>
            <el-form-item v-else-if="nodeSchema.$defs.Parameters.properties[key].enum"
                :label="_(nodeSchema.$defs.Parameters.properties[key].title)">
                <el-select v-model="formData.parameters[key]">
                    <el-option v-for="opt in nodeSchema.$defs.Parameters.properties[key].enum" :key="opt"
                        :label="_(opt)" :value="opt" />
                </el-select>
            </el-form-item>
            <el-form-item v-else :label="_(nodeSchema.$defs.Parameters.properties[key].title)">
                <el-input v-model="formData.parameters[key]"
                    :type="inputTypeMapping(nodeSchema.$defs.Parameters.properties[key].type)"
                    :placeholder="String(nodeSchema.$defs.Parameters.properties[key].default)" />
            </el-form-item>
        </template>

    </el-form>
</template>
<script lang="ts" setup>
import { computed, onMounted, ref, toRaw, watch, nextTick, inject } from 'vue'
import { NodeData } from './NodeData';
import LogicFlow from '@logicflow/core'
import { getInstances, getNodeTypes, getNodeSchema } from '@/requests';
import { ElInput } from 'element-plus';
import { _ } from '@/i18n'
import { QuestionFilled, Loading } from '@element-plus/icons-vue'
const props = defineProps<{
    data?: NodeData
    graphConfigData?: LogicFlow.GraphConfigData
}>()

const selectNodeHelp = inject<(nodeType: string) => void>('selectNodeHelp', () => {})
const helpContent = inject('nodeHelpContent', ref(''))
const helpLoading = inject('nodeHelpLoading', ref(false))

function onHelpClick(nodeType: string) {
    selectNodeHelp(nodeType)
}

const emit = defineEmits<{
    (e: 'save', data: { id: string; properties: Record<string, any> }): void
}>()

const formData = ref<NodeData>()
class NodeType {
    node_type: string = ""
    category: string = ""
}
let bindingNodeId: string
function snakeToPascal(str: string): string {
    return str
        .split("_")
        .filter(Boolean)
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join("");
}
const nodeTypes = ref<NodeType[]>()
const nodeSchema = ref<any>()
const groupedNodeTypes = computed(() => {
    const groups: Record<string, NodeType[]> = {}
    for (const item of nodeTypes.value ?? []) {
        const cat = item.category || _('Other')
        if (!groups[cat]) groups[cat] = []
        groups[cat].push(item)
    }
    return Object.entries(groups).map(([category, items]) => ({ category, items }))
})
const possibleReadData = computed(() => {
    if (!props.graphConfigData?.nodes) return []
    const prevIds = formData.value?.prev ?? []
    const columns = new Set<string>()
    for (const node of props.graphConfigData.nodes) {
        const data = node?.properties?.data
        if (data && prevIds.includes(data.id)) {
            for (const col of data.write_data ?? []) {
                columns.add(col)
            }
        }
    }
    return [...columns]
})
const possibleNodeIds = computed(() => {
    if (!props.graphConfigData?.nodes) return []
    const nodeIds = new Set<string>()
    for (const node of props.graphConfigData.nodes) {
        if (node.id) {
            nodeIds.add(node.id)
        }
    }
    return [...nodeIds]
})
const possibleReadState = computed(() => {
    if (!props.graphConfigData?.nodes) return []
    const prevIds = formData.value?.prev ?? []
    const states = new Set<string>()
    for (const node of props.graphConfigData.nodes) {
        const data = node?.properties?.data
        if (data && prevIds.includes(data.id)) {
            for (const state of data.write_state ?? []) {
                states.add(state)
            }
        }
    }
    return [...states]
})

const possibleWriteData = computed(() => {
    if (!props.graphConfigData?.nodes) return []
    const nextIds = formData.value?.next ?? []
    const columns = new Set<string>()
    for (const node of props.graphConfigData.nodes) {
        const data = node?.properties?.data
        if (data && nextIds.includes(data.id)) {
            for (const col of data.read_data ?? []) {
                columns.add(col)
            }
        }
    }
    return [...columns]
})

const possibleWriteState = computed(() => {
    if (!props.graphConfigData?.nodes) return []
    const nextIds = formData.value?.next ?? []
    const states = new Set<string>()
    for (const node of props.graphConfigData.nodes) {
        const data = node?.properties?.data
        if (data && nextIds.includes(data.id)) {
            for (const state of data.read_state ?? []) {
                states.add(state)
            }
        }
    }
    return [...states]
})
onMounted(async () => {
    nodeTypes.value = await getNodeTypes()
})
async function getSchema(node_type: string) {
    nodeSchema.value = await getNodeSchema(node_type)
}
function inputTypeMapping(type: string): string {
    return {
        string: "textarea",
        integer: "number",
        number: "number"
    }[type] ?? "textarea"
}
const instances = ref<any[]>()
async function updateNode(data: NodeData | null) {
    if (data) {
        await getSchema(data.node_type)
        if (["InferenceNode", "TrainNode"].includes(data.node_type)) {
            instances.value = await getInstances()
        }
        // 为新节点填充 schema 中定义的参数默认值
        const paramDefaults = nodeSchema.value?.$defs?.Parameters?.properties
        if (paramDefaults) {
            for (const key of Object.keys(paramDefaults)) {
                if (!(key in data.parameters)) {
                    data.parameters[key] = paramDefaults[key].default
                }
            }
        }
        // 为顶层字段填充默认值（如 read_data, write_data 等数组字段）
        const topDefaults = nodeSchema.value?.properties
        if (topDefaults) {
            for (const key of Object.keys(topDefaults)) {
                const prop = topDefaults[key]
                if (prop.default !== undefined && data[key] === undefined) {
                    data[key] = prop.default
                }
            }
        }
    }
    bindingNodeId = data?.id
    formData.value = data ?? undefined
}
function addTagTo(command: string, target?: string[]) {
    target?.push(command)
}
const jinjaTextareaRef = ref<InstanceType<typeof ElInput>[]>()
async function insertJinjaVar(prefix: string, key: string) {
    const el = jinjaTextareaRef.value?.[0]?.textarea
    if (!el) return
    const text = `{{ ${prefix}.${key} }}`
    const start = el.selectionStart ?? 0
    const end = el.selectionEnd ?? 0
    const current = formData.value?.parameters?.['jinja_prompt'] ?? ''
    formData.value!.parameters!['jinja_prompt'] = current.slice(0, start) + text + current.slice(end)
    await nextTick()
    const el2 = jinjaTextareaRef.value?.[0]?.textarea
    if (el2) {
        const pos = start + text.length
        el2.setSelectionRange(pos, pos)
        el2.focus()
    }
}
watch(formData, (newVal) => {
    if (!newVal || !bindingNodeId) return
    const node = props.graphConfigData?.nodes?.find(n => n.id === bindingNodeId)
    if (!node) return
    node.properties = { ...node.properties, data: { ...newVal } }
    emit('save', { id: bindingNodeId, properties: node.properties })
}, { deep: true })
defineExpose({ updateNode, formData })
</script>

<style>
.jinja-editor {
    width: 100%;
}

.jinja-toolbar {
    display: flex;
    gap: 6px;
    margin-bottom: 6px;
}

.editor-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    margin-bottom: 12px;
    background: #f5f7fa;
    border-radius: 6px;
    border: 1px solid #e4e7ed;
}

.node-type-name {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
}

.help-btn {
    flex-shrink: 0;
}

.help-content {
    padding: 4px;
    font-size: 13px;
    line-height: 1.7;
    min-height: 1.7em;
}

.help-content.markdown-body {
    max-height: 60vh;
    overflow-y: auto;
}

.help-content.help-loading,
.help-content.help-empty {
    color: #909399;
    max-height: none;
    overflow-y: visible;
    display: flex;
    align-items: center;
    min-height: 1.7em;
}

.help-content.help-loading .el-icon {
    font-size: 16px;
}

.help-content.markdown-body h1 { font-size: 1.3em; }
.help-content.markdown-body h2 { font-size: 1.15em; }
.help-content.markdown-body h3 { font-size: 1.05em; }
.help-content.markdown-body code {
    font-size: 12px;
    background: #f0f2f5;
    padding: 1px 4px;
    border-radius: 3px;
}
.help-content.markdown-body pre code {
    display: block;
    padding: 10px;
    overflow-x: auto;
}
</style>