<script setup lang="ts">
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { _ } from '@/i18n'
import { ElMessageBox } from 'element-plus'

defineProps<{
  pipelines: string[]
  activeId: string
}>()

const emit = defineEmits<{
  select: [id: string]
  create: []
  rename: [oldId: string]
  delete: [id: string]
}>()

async function confirmDelete(id: string) {
  try {
    await ElMessageBox.confirm(
      _('Are you sure to delete pipeline') + ` "${id}"?`,
      _('Delete Pipeline'),
      {
        confirmButtonText: _('OK'),
        cancelButtonText: _('Cancel'),
        type: 'warning',
      }
    )
    emit('delete', id)
  } catch { /* cancel */ }
}
</script>

<template>
  <div class="navigator">
    <div class="nav-header">
      <h4 class="nav-title">{{ _('Pipelines') }}</h4>
      <el-button type="primary" size="small" circle @click="emit('create')">
        <el-icon><Plus /></el-icon>
      </el-button>
    </div>
    <el-menu
      :default-active="activeId"
      @select="(id: string) => emit('select', id)"
    >
      <el-menu-item
        v-for="id in pipelines"
        :key="id"
        :index="id"
      >
        <div class="menu-item-content">
          <span class="menu-item-text">{{ id }}</span>
          <el-icon class="rename-icon" @click.stop="emit('rename', id)"><Edit /></el-icon>
          <el-icon class="delete-icon" @click.stop="confirmDelete(id)"><Delete /></el-icon>
        </div>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<style scoped>
.navigator {
  height: 100%;
  overflow-y: auto;
}

.nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
  border-bottom: 1px solid #ebeef5;
}

.nav-title {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
  margin: 0;
}

.el-menu {
  border-right: none;
}

.menu-item-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.menu-item-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rename-icon {
  flex-shrink: 0;
  margin-left: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.el-menu-item:hover .rename-icon {
  opacity: 1;
}

.delete-icon {
  flex-shrink: 0;
  margin-left: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  color: #f56c6c;
}

.el-menu-item:hover .delete-icon {
  opacity: 1;
}
</style>
