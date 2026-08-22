<script setup lang="ts">
import { VideoPlay, Upload, Grid, Edit, Share } from '@element-plus/icons-vue'
import { _ } from '@/i18n'

defineProps<{
    running: boolean
    saving: boolean
    viewMode: 'graph' | 'json'
}>()

const emit = defineEmits<{
    (e: 'run'): void
    (e: 'save'): void
    (e: 'auto-layout'): void
    (e: 'toggle-view'): void
}>()

function handleRun() {
    emit('run')
}

function handleSave() {
    emit('save')
}

function handleAutoLayout() {
    emit('auto-layout')
}

function handleToggleView() {
    emit('toggle-view')
}
</script>

<template>
    <el-menu mode="horizontal" :ellipsis="false" class="top-menu">
        <div class="menu-left">
            <el-button class="auto-layout-btn" :icon="Grid" @click="handleAutoLayout">
                {{ _('Layout') }}
            </el-button>
            <el-button class="run-btn" type="success" :loading="running" :icon="VideoPlay" @click="handleRun">
                {{ _('Run') }}
            </el-button>
            <el-button class="save-btn" type="primary" :loading="saving" :icon="Upload" @click="handleSave">
                {{ _('Save') }}
            </el-button>

        </div>

        <div class="flex-grow" />
        <div class="menu-right">
            <el-button :icon="viewMode === 'json' ? Share : Edit" @click="handleToggleView">
                {{ viewMode === 'json' ? _('Graph') : _('JSON') }}
            </el-button>
        </div>
    </el-menu>
</template>

<style scoped>
.top-menu {
    display: flex;
    align-items: center;
    padding: 0 16px;
    height: 48px;
    border-bottom: 1px solid var(--el-border-color-light);
}

.menu-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.flex-grow {
    flex-grow: 1;
}

.menu-right {
    display: flex;
    align-items: center;
}

.run-btn :deep(.el-icon) {
    font-size: 16px;
}
</style>
