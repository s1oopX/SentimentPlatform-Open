<script setup>
import { ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { triggerDatabaseBackup } from '@/api/admin'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FolderOpened, Timer, WarningFilled, CircleCheckFilled } from '@element-plus/icons-vue'

const loading = ref(false)
/** @type {import('vue').Ref<any>} */ const backupResult = ref(null)
const backupError = ref('')

const handleBackup = async () => {
  try {
    await ElMessageBox.confirm(
      '确认执行数据库全量备份？备份期间不影响系统正常使用。',
      '数据库备份',
      { confirmButtonText: '执行备份', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }

  loading.value = true
  backupResult.value = null
  backupError.value = ''
  try {
    const res = await triggerDatabaseBackup()
    backupResult.value = res.data
    ElMessage.success('数据库备份成功')
  } catch (/** @type {any} */ err) {
    backupError.value = err?.response?.data?.error || '备份失败，请检查服务器配置'
    ElMessage.error(backupError.value)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader
      title="数据库备份"
      description="MySQL 数据库全量备份管理，支持手动触发和自动定期执行"
    />

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center gap-3 mb-2">
          <div class="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
            <el-icon :size="20" class="text-blue-600"><FolderOpened /></el-icon>
          </div>
          <div>
            <div class="text-sm font-medium text-slate-900">备份方式</div>
            <div class="text-xs text-slate-500">mysqldump 全量导出</div>
          </div>
        </div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center gap-3 mb-2">
          <div class="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
            <el-icon :size="20" class="text-green-600"><Timer /></el-icon>
          </div>
          <div>
            <div class="text-sm font-medium text-slate-900">自动备份</div>
            <div class="text-xs text-slate-500">每周日凌晨 2:00 自动执行</div>
          </div>
        </div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center gap-3 mb-2">
          <div class="h-10 w-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <el-icon :size="20" class="text-amber-600"><WarningFilled /></el-icon>
          </div>
          <div>
            <div class="text-sm font-medium text-slate-900">保留策略</div>
            <div class="text-xs text-slate-500">自动清理 30 天前旧备份</div>
          </div>
        </div>
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 class="text-base font-semibold text-slate-700 mb-4">手动备份</h3>
      <p class="text-sm text-slate-500 mb-5">
        点击下方按钮立即执行一次全量数据库备份，备份文件保存在服务器
        <code class="bg-slate-100 px-1.5 py-0.5 rounded text-xs">backups/</code> 目录中。
      </p>
      <el-button type="primary" size="large" :loading="loading" @click="handleBackup">
        <el-icon class="mr-2"><FolderOpened /></el-icon>
        {{ loading ? '备份中...' : '立即备份' }}
      </el-button>

      <div v-if="backupResult" class="mt-5 rounded-lg bg-green-50 border border-green-200 p-4">
        <div class="flex items-center gap-2 text-green-700 font-medium mb-2">
          <el-icon><CircleCheckFilled /></el-icon>
          {{ backupResult.message }}
        </div>
        <pre v-if="backupResult.output" class="text-xs text-green-600 whitespace-pre-wrap">{{
          backupResult.output
        }}</pre>
      </div>

      <div v-if="backupError" class="mt-5 rounded-lg bg-red-50 border border-red-200 p-4">
        <div class="flex items-center gap-2 text-red-700 font-medium">
          <el-icon><WarningFilled /></el-icon>
          {{ backupError }}
        </div>
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 class="text-base font-semibold text-slate-700 mb-4">备份说明</h3>
      <ul class="text-sm text-slate-600 space-y-2 list-disc list-inside">
        <li>
          备份使用
          <code class="bg-slate-100 px-1 py-0.5 rounded text-xs">mysqldump</code>
          导出完整数据库结构和数据
        </li>
        <li>
          备份文件格式：<code class="bg-slate-100 px-1 py-0.5 rounded text-xs"
            >数据库备份_YYYYMMDD_HHMMSS.sql</code
          >
        </li>
        <li>Windows 任务计划程序可配置每周自动执行备份脚本</li>
        <li>超过 30 天的旧备份会在下次备份时自动清理</li>
        <li>建议在业务低峰期执行手动备份</li>
      </ul>
    </div>
  </div>
</template>
