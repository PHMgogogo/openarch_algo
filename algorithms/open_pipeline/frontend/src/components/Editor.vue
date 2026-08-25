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
            <el-select v-model="formData.node_type" @change="onNodeTypeChange">
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
        <template v-if="nodeSchema" v-for="key in Object.keys(nodeSchema.$defs.InParameters.properties)" :key="key">
            <el-form-item v-if="['InferenceNode', 'TrainNode', 'SendAlarmNode'].includes(formData.node_type) && key == 'instance'"
                :label="paramLabel(key)">
                <el-select :model-value="formData.in_parameters[key]?.constant"
                    @change="(val: string) => setValueRefConstant(key, val)"
                    :placeholder="String(nodeSchema.$defs.InParameters.properties[key].default?.constant ?? '')">
                    <el-option v-for="instance in instances" :key="instance.id" :label="instance.id"
                        :value="instance.id" />
                </el-select>
            </el-form-item>
            <el-form-item v-else-if="key == 'jinja_prompt'"
                :label="paramLabel(key)">
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
                            :disabled="possibleInState.length <= 0">
                            <el-button size="small">{{ _('Insert State') }}</el-button>
                            <template #dropdown>
                                <el-dropdown-menu>
                                    <el-dropdown-item v-for="item in possibleInState" :key="item" :command="item">
                                        state.{{ item }}</el-dropdown-item>
                                </el-dropdown-menu>
                            </template>
                        </el-dropdown>
                    </div>
                    <el-input ref="jinjaTextareaRef" :model-value="formData.in_parameters[key]?.constant"
                        @update:model-value="(val: string) => setValueRefConstant(key, val)" type="textarea" :rows="8"
                        :placeholder="String(nodeSchema.$defs.InParameters.properties[key].default?.constant ?? '')" />
                </div>
            </el-form-item>
            <el-form-item v-else-if="nodeSchema.$defs.InParameters.properties[key].type === 'boolean'"
                :label="paramLabel(key)">
                <el-checkbox v-model="formData.in_parameters[key]" />
            </el-form-item>
            <el-form-item v-else-if="['number', 'integer'].includes(nodeSchema.$defs.InParameters.properties[key].type)"
                :label="paramLabel(key)">
                <el-input-number v-model="formData.in_parameters[key]"
                    :placeholder="String(nodeSchema.$defs.InParameters.properties[key].default)" />
            </el-form-item>
            <el-form-item v-else-if="isValueRefList(nodeSchema.$defs.InParameters.properties[key])"
                :label="paramLabel(key)">
                <el-dropdown @command="(cmd: string) => addValueRefState(key, cmd)" style="width: 100%"
                    :disabled="possibleInState.length <= 0">
                    <el-input-tag :model-value="valueRefListKeys(key)"
                        @change="(val: string[]) => setValueRefListKeys(key, val)" draggable></el-input-tag>
                    <template #dropdown>
                        <el-dropdown-menu>
                            <el-dropdown-item v-for="item in possibleInState" :key="item" :label="item"
                                :command="item">{{ item }}</el-dropdown-item>
                        </el-dropdown-menu>
                    </template>
                </el-dropdown>
            </el-form-item>
            <el-form-item v-else-if="nodeSchema.$defs.InParameters.properties[key].type === 'array'"
                :label="paramLabel(key)">
                <el-input-tag v-model="formData.in_parameters[key]" draggable></el-input-tag>
            </el-form-item>
            <el-form-item v-else-if="nodeSchema.$defs.InParameters.properties[key].enum"
                :label="paramLabel(key)">
                <el-select v-model="formData.in_parameters[key]">
                    <el-option v-for="opt in nodeSchema.$defs.InParameters.properties[key].enum" :key="opt"
                        :label="_(opt)" :value="opt" />
                </el-select>
            </el-form-item>
            <el-form-item v-else-if="isValueRef(nodeSchema.$defs.InParameters.properties[key])"
                :label="paramLabel(key)">
                <div class="value-ref-editor" v-if="formData.in_parameters[key]">
                    <el-radio-group :model-value="valueRefMode(key)" size="small"
                        @change="(mode: string) => onValueRefModeChange(key, mode)">
                        <el-radio-button value="constant">{{ _('Constant') }}</el-radio-button>
                        <el-radio-button value="state">{{ _('State Ref') }}</el-radio-button>
                    </el-radio-group>
                    <el-dropdown v-if="valueRefMode(key) === 'state'" @command="(cmd: string) => setValueRefState(key, cmd)"
                        style="width: 100%" :disabled="possibleInState.length <= 0">
                        <el-input v-model="formData.in_parameters[key].state"
                            :placeholder="_('Select state key')" />
                        <template #dropdown>
                            <el-dropdown-menu>
                                <el-dropdown-item v-for="item in possibleInState" :key="item" :label="item"
                                    :command="item">{{ item }}</el-dropdown-item>
                            </el-dropdown-menu>
                        </template>
                    </el-dropdown>
                    <el-select v-else-if="valueRefConstantEnum(key)?.length"
                        :model-value="formData.in_parameters[key]?.constant"
                        @change="(val: any) => setValueRefConstant(key, val)">
                        <el-option v-for="opt in valueRefConstantEnum(key)" :key="opt" :label="_(opt)"
                            :value="opt" />
                    </el-select>
                    <el-input-tag v-else-if="valueRefValueType(key) === 'array'"
                        v-model="formData.in_parameters[key].constant" draggable />
                    <el-checkbox v-else-if="valueRefValueType(key) === 'boolean'"
                        v-model="formData.in_parameters[key].constant" />
                    <el-input-number v-else-if="valueRefValueType(key) === 'number'"
                        v-model="formData.in_parameters[key].constant"
                        :placeholder="String(nodeSchema.$defs.InParameters.properties[key].default?.constant ?? '')" />
                    <el-input v-else v-model="formData.in_parameters[key].constant"
                        :placeholder="String(nodeSchema.$defs.InParameters.properties[key].default?.constant ?? '')" />
                </div>
            </el-form-item>
            <el-form-item v-else :label="paramLabel(key)">
                <el-input v-model="formData.in_parameters[key]"
                    :type="inputTypeMapping(nodeSchema.$defs.InParameters.properties[key].type)"
                    :placeholder="String(nodeSchema.$defs.InParameters.properties[key].default)" />
            </el-form-item>
        </template>

        <template v-if="hasOutParameters">
            <el-divider content-position="left">{{ _('Outputs (written to state)') }}</el-divider>
            <el-form-item v-for="key in Object.keys(nodeSchema.$defs.OutParameters.properties)" :key="'out_' + key"
                :label="outParamLabel(key)">
                <el-dropdown @command="(cmd: string) => setOutParam(key, cmd)" style="width: 100%"
                    :disabled="possibleOutState.length <= 0">
                    <el-input v-model="formData.out_parameters[key]" :placeholder="_('Select state key')" />
                    <template #dropdown>
                        <el-dropdown-menu>
                            <el-dropdown-item v-for="item in possibleOutState" :key="item" :label="item"
                                :command="item">{{ item }}</el-dropdown-item>
                        </el-dropdown-menu>
                    </template>
                </el-dropdown>
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
const possibleInState = computed(() => {
    if (!props.graphConfigData?.nodes) return []
    const states = new Set<string>()
    // inState：收集所有上游节点（沿 prev 链可达）输出的 outState
    const visited = new Set<string>()
    const stack = [...(formData.value?.prev ?? [])]
    while (stack.length) {
        const id = stack.pop()!
        if (visited.has(id)) continue
        visited.add(id)
        const node = props.graphConfigData.nodes.find(n => n.id === id)
        const data = node?.properties?.data
        if (data) {
            for (const key of Object.values(data.out_parameters ?? {})) {
                if (key) states.add(String(key))
            }
            stack.push(...(data.prev ?? []))
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

const possibleOutState = computed(() => {
    if (!props.graphConfigData?.nodes) return []
    const states = new Set<string>()
    // outState：收集所有下游节点（沿 next 链可达）需要的 inState
    const visited = new Set<string>()
    const stack = [...(formData.value?.next ?? [])]
    while (stack.length) {
        const id = stack.pop()!
        if (visited.has(id)) continue
        visited.add(id)
        const node = props.graphConfigData.nodes.find(n => n.id === id)
        const data = node?.properties?.data
        if (data) {
            for (const ref of Object.values(data.in_parameters ?? {})) {
                const r = ref as { state?: string } | null
                if (r && r.state) {
                    states.add(String(r.state))
                }
            }
            stack.push(...(data.next ?? []))
        }
    }
    return [...states]
})
const hasOutParameters = computed(() => {
    const props = nodeSchema.value?.$defs?.OutParameters?.properties
    return !!props && Object.keys(props).length > 0
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
function isValueRef(prop: any): boolean {
    return typeof prop?.$ref === "string" && prop.$ref.startsWith("#/$defs/ValueRef")
}
function paramLabel(key: string): string {
    const prop = nodeSchema.value?.$defs?.InParameters?.properties?.[key]
    const title = prop?.title
    return _(title ?? key)
}
function outParamLabel(key: string): string {
    const prop = nodeSchema.value?.$defs?.OutParameters?.properties?.[key]
    const title = prop?.title
    return _(title ?? key)
}
function isValueRefList(prop: any): boolean {
    return prop?.type === "array" && typeof prop?.items?.$ref === "string"
        && prop.items.$ref.startsWith("#/$defs/ValueRef")
}
function valueRefValueType(key: string): string {
    const prop = nodeSchema.value?.$defs?.InParameters?.properties?.[key]
    if (!prop?.$ref) return "string"
    const refName = prop.$ref.replace("#/$defs/", "")
    const valueSchema = nodeSchema.value?.$defs?.[refName]?.properties?.constant
    if (!valueSchema) return "string"
    let type = valueSchema.type
    if (!type) {
        // Optional[T] 生成 anyOf: [{type}, {type: null}]
        const types = (valueSchema.anyOf ?? []).map((t: any) => t.type).filter((t: string) => t !== "null")
        type = types[0]
    }
    // integer 归一化为 number，统一用 el-input-number
    return type === "integer" ? "number" : (type ?? "string")
}
function valueRefConstantEnum(key: string): string[] | undefined {
    const prop = nodeSchema.value?.$defs?.InParameters?.properties?.[key]
    if (!prop?.$ref) return undefined
    const refName = prop.$ref.replace("#/$defs/", "")
    const valueSchema = nodeSchema.value?.$defs?.[refName]?.properties?.constant
    if (!valueSchema) return undefined
    const candidates = valueSchema.enum
        ? [valueSchema]
        : (valueSchema.anyOf ?? []).filter((t: any) => Array.isArray(t.enum))
    const enums = candidates.flatMap((t: any) => t.enum ?? [])
    return enums.length > 0 ? enums : undefined
}
function valueRefMode(key: string): string {
    const ref = formData.value?.in_parameters?.[key]
    if (!ref) return "constant"
    return ref.mode === "state" ? "state" : "constant"
}
function onValueRefModeChange(key: string, mode: string) {
    const ref = formData.value?.in_parameters?.[key]
    if (!ref) return
    // 只切换标志位，保留 constant 与 state，避免来回切换时数据丢失
    ref.mode = mode
}
function setValueRefState(key: string, cmd: string) {
    const ref = formData.value?.in_parameters?.[key]
    if (ref) {
        ref.state = cmd
        ref.mode = "state"
    }
}
function setValueRefConstant(key: string, val: any) {
    const ref = formData.value?.in_parameters?.[key]
    if (ref) {
        ref.constant = val
        ref.mode = "constant"
    }
}
function valueRefListKeys(key: string): string[] {
    const list = formData.value?.in_parameters?.[key]
    if (!Array.isArray(list)) return []
    return list.map((r: any) => r?.state ?? "")
}
function setValueRefListKeys(key: string, keys: string[]) {
    const list = formData.value?.in_parameters?.[key]
    if (!Array.isArray(list)) return
    // 同步 el-input-tag 的增删：按新 keys 重建 ValueRef 列表
    formData.value!.in_parameters![key] = keys.map((k) => ({ constant: null, state: k, mode: "state" }))
}
function addValueRefState(key: string, cmd: string) {
    const list = formData.value?.in_parameters?.[key]
    if (!Array.isArray(list)) return
    if (list.some((r: any) => r?.state === cmd)) return
    list.push({ constant: null, state: cmd, mode: "state" })
}
function setOutParam(key: string, cmd: string) {
    if (formData.value?.out_parameters) {
        formData.value.out_parameters[key] = cmd
    }
}
const instances = ref<any[]>()
function normalizeInParameters(data: NodeData) {
    const paramDefaults = nodeSchema.value?.$defs?.InParameters?.properties
    if (!paramDefaults) return
    if (!data.in_parameters) data.in_parameters = {}
    for (const key of Object.keys(paramDefaults)) {
        if (!(key in data.in_parameters)) {
            data.in_parameters[key] = paramDefaults[key].default
        }
        // 规范化 ValueRef 字段，确保 constant / state / mode 结构完整，避免渲染时访问 undefined 报错
        if (isValueRef(paramDefaults[key])) {
            if (!data.in_parameters[key] || typeof data.in_parameters[key] !== 'object') {
                data.in_parameters[key] = { ...(paramDefaults[key].default ?? {}) }
            }
            const ref = data.in_parameters[key]
            if (ref.constant === undefined) ref.constant = null
            if (ref.state === undefined) ref.state = null
            // 兼容旧数据：无 mode 时按 state 是否非空推断
            if (ref.mode === undefined) {
                ref.mode = ref.state !== null && ref.state !== undefined ? "state" : "constant"
            }
        }
        // 规范化 ValueRef 列表字段（如 SendAlarmNode 的 values），列表元素均为 state 引用
        if (isValueRefList(paramDefaults[key]) && Array.isArray(data.in_parameters[key])) {
            for (const ref of data.in_parameters[key]) {
                if (ref && typeof ref === 'object') {
                    if (ref.constant === undefined) ref.constant = null
                    if (ref.state === undefined) ref.state = null
                    if (ref.mode === undefined) ref.mode = "state"
                }
            }
        }
    }
}
async function onNodeTypeChange(node_type: string) {
    await getSchema(node_type)
    if (formData.value) {
        normalizeInParameters(formData.value)
    }
}
async function updateNode(data: NodeData | null) {
    if (data) {
        await getSchema(data.node_type)
        if (["InferenceNode", "TrainNode", "SendAlarmNode"].includes(data.node_type)) {
            instances.value = await getInstances()
        }
        // 为新节点填充 schema 中定义的参数默认值
        normalizeInParameters(data)
        // 为 out_parameters 填充默认值
        const outDefaults = nodeSchema.value?.$defs?.OutParameters?.properties
        if (outDefaults) {
            if (!data.out_parameters) data.out_parameters = {}
            for (const key of Object.keys(outDefaults)) {
                if (!(key in data.out_parameters)) {
                    data.out_parameters[key] = outDefaults[key].default
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
    const current = formData.value?.in_parameters?.['jinja_prompt']?.constant ?? ''
    formData.value!.in_parameters!['jinja_prompt'].constant = current.slice(0, start) + text + current.slice(end)
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

.value-ref-editor {
    width: 100%;
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 6px;
}

.value-ref-editor .el-radio-group {
    flex-shrink: 0;
}

.value-ref-editor .el-dropdown,
.value-ref-editor .el-input,
.value-ref-editor .el-input-number {
    flex: 1;
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