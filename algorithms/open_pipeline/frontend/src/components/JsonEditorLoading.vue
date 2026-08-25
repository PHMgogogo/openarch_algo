<template>
  <div class="json-editor-loading">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span>{{ _('Editor loading...') }}</span>
  </div>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'
import { _ } from '@/i18n'
</script>

<style scoped>
.json-editor-loading {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #909399;
  font-size: 14px;
}

.json-editor-loading .el-icon {
  font-size: 28px;
}
</style>
