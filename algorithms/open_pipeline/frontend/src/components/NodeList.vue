<template>
    <div class="node-list">
        <div class="node-list-header">{{ _('Node List (Drag to Add)') }}</div>
        <el-scrollbar>
            <el-collapse v-model="activeCategories">
                <el-collapse-item v-for="group in groupedNodeTypes" :key="group.category" :title="_(group.category)"
                    :name="group.category">
                    <div v-for="item in group.items" :key="item.node_type" class="node-list-item"
                        @mousedown="onDragStart(item)">
                        <el-icon class="drag-icon">
                            <Rank />
                        </el-icon>
                        <span class="node-type-name">{{ _(item.node_type) }}</span>
                    </div>
                </el-collapse-item>
            </el-collapse>
        </el-scrollbar>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Rank } from '@element-plus/icons-vue'
import { NODE_WIDTH } from './Node.vue'
import { _ } from '@/i18n'
import { getNodeTypes } from '@/requests'

class NodeType {
    node_type: string = ''
    category: string = ''
}

const props = defineProps<{
    canvasRef?: { startDrag: (config: Record<string, unknown>) => void }
}>()

const nodeTypes = ref<NodeType[]>([])
const activeCategories = ref<string[]>([])

const groupedNodeTypes = computed(() => {
    const groups: Record<string, NodeType[]> = {}
    for (const item of nodeTypes.value) {
        const cat = item.category || _('Other')
        if (!groups[cat]) groups[cat] = []
        groups[cat].push(item)
    }
    return Object.entries(groups).map(([category, items]) => ({ category, items }))
})

onMounted(async () => {
    nodeTypes.value = await getNodeTypes()
    activeCategories.value = groupedNodeTypes.value.map(g => g.category)
})

function onDragStart(item: NodeType) {
    const uuid = crypto.randomUUID()
    props.canvasRef?.startDrag({
        id: uuid,
        type: 'node',
        properties: {
            data: {
                node_type: item.node_type,
                id: uuid,
                title: null,
                next: [],
                prev: [],
                read_data: [],
                write_data: [],
                read_state: [],
                write_state: [],
                parameters: {},
                category: item.category,
                order: -1,
            } as unknown,
            width: NODE_WIDTH,
        },
    })
}
</script>

<style scoped>
.node-list {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 6px;
    overflow-x: hidden;
}

.node-list-header {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
    padding: 8px 12px;
    border-bottom: 1px solid #e4e7ed;
    flex-shrink: 0;
}

.node-list-item {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    margin: 4px 0;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    cursor: grab;
    background: #fafafa;
    transition: all 0.2s;
    user-select: none;
}

.node-list-item:hover {
    border-color: #409eff;
    background: #ecf5ff;
    color: #409eff;
}

.node-list-item:active {
    cursor: grabbing;
    background: #d9ecff;
}

.drag-icon {
    font-size: 16px;
    color: #909399;
    flex-shrink: 0;
}

.node-type-name {
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.node-list :deep(.el-scrollbar__view) {
  padding-right: 10px;
}
</style>
