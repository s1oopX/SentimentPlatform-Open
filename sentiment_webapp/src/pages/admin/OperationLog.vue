<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { useRefreshOnActivated } from '@/composables/useRefreshOnActivated'
import { usePageSizeReset } from '@/composables/usePagination'
import { getOperationLogs } from '@/api/admin'
import {
  Search,
  Timer,
  Refresh,
  LocationFilled,
  Clock,
  User as UserIcon,
} from '@element-plus/icons-vue'
import { formatDateTimeText } from '@/utils/dateTime'

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const errorMessage = ref('')
const actionTypeOptions = [
  { label: '登录', value: 'login' },
  { label: '登出', value: 'logout' },
  { label: '注册', value: 'register' },
  { label: '修改密码', value: 'change_password' },
  { label: '重置密码', value: 'reset_password' },
  { label: '单条评论分析', value: 'analyze_single' },
  { label: '批量评论分析', value: 'analyze_batch' },
  { label: '导出报告', value: 'export_report' },
  { label: '上传文件', value: 'upload_file' },
  { label: '下载文件', value: 'download_file' },
  { label: '创建用户', value: 'create_user' },
  { label: '更新用户', value: 'update_user' },
  { label: '删除用户', value: 'delete_user' },
  { label: '模型训练', value: 'model_train' },
  { label: '模型切换', value: 'model_switch' },
  { label: '数据库备份', value: 'backup_db' },
  { label: '数据库恢复', value: 'restore_db' },
  { label: '其他', value: 'other' },
]

const queryParams = reactive({
  page: 1,
  page_size: 15,
  search: '',
  action: '',
  dateRange: null,
})

const emptyStateMessage = computed(() => errorMessage.value || '暂无操作日志')
const buildLogFilters = (searchValue = '', actionValue = '') => {
  const keyword = String(searchValue).trim()
  const action = String(actionValue || '').trim()
  const filters = { search: keyword, action }
  if (keyword) {
    if (/^\d+$/.test(keyword)) {
      filters.user_id = keyword
    }
  }
  const range = /** @type {any} */ (queryParams.dateRange)
  if (Array.isArray(range) && range.length === 2) {
    filters.start_date = range[0]
    filters.end_date = range[1]
  }
  return filters
}

const fetchLogs = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const filters = buildLogFilters(queryParams.search, queryParams.action)
    const res = await getOperationLogs({
      page: queryParams.page,
      page_size: queryParams.page_size,
      ...filters,
    })
    if (res.data.results) {
      tableData.value = res.data.results
      total.value = res.data.count
    } else {
      tableData.value = res.data
      total.value = res.data.length
    }
  } catch {
    tableData.value = []
    total.value = 0
    errorMessage.value = '操作日志加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const handleSearchChange = async () => {
  queryParams.page = 1
  await fetchLogs()
}

const handleActionChange = async () => {
  queryParams.page = 1
  await fetchLogs()
}

const { handlePageSizeChange } = usePageSizeReset(queryParams, fetchLogs)

onMounted(() => fetchLogs())

useRefreshOnActivated(fetchLogs)
</script>

<template>
  <div class="h-full flex flex-col space-y-6">
    <div class="space-y-2">
      <h1 class="text-2xl font-bold text-slate-800">操作日志</h1>
      <p class="text-slate-500 text-sm">系统关键行为审计与数据变更追踪</p>
    </div>

    <div
      class="bg-white rounded-xl border border-slate-200 shadow-sm flex-1 flex flex-col overflow-hidden"
    >
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
        class="mx-6 mt-6"
      />

      <!-- Toolbar -->
      <div
        class="p-6 border-b border-slate-100 bg-slate-50/50 flex flex-wrap items-center justify-between gap-4"
      >
        <div class="flex flex-wrap gap-4 items-center">
          <el-input
            v-model="queryParams.search"
            placeholder="搜索用户ID、邮箱、详情或 IP..."
            class="!w-full sm:!w-72 el-input-rounded"
            clearable
            @change="handleSearchChange"
          >
            <template #prefix
              ><el-icon class="text-slate-400"><Search /></el-icon
            ></template>
          </el-input>
          <el-select
            v-model="queryParams.action"
            placeholder="操作类型"
            class="!w-48 el-input-rounded"
            clearable
            @change="handleActionChange"
          >
            <el-option
              v-for="option in actionTypeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-date-picker
            v-model="queryParams.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            class="!w-64"
            value-format="YYYY-MM-DD"
            clearable
            @change="handleSearchChange"
          />
          <el-button :icon="Refresh" circle @click="fetchLogs" />
        </div>
      </div>

      <!-- Table Section -->
      <div class="flex-1 overflow-hidden">
        <el-table
          v-loading="loading"
          :data="tableData"
          class="admin-table h-full"
          header-cell-class-name="admin-table-header"
        >
          <template #empty>
            <div class="py-10 text-sm text-slate-500">
              {{ emptyStateMessage }}
            </div>
          </template>
          <el-table-column prop="id" label="日志编号" width="100" align="center" />

          <el-table-column label="动作/行为" min-width="250" header-align="center">
            <template #default="scope">
              <div class="flex items-center gap-4 py-2 pl-6">
                <div class="h-10 w-10 rounded-xl bg-slate-100 flex items-center justify-center">
                  <el-icon class="text-slate-600" :size="20"><Timer /></el-icon>
                </div>
                <div class="flex flex-col">
                  <span class="font-bold text-slate-900">{{
                    scope.row.action_display || scope.row.action
                  }}</span>
                  <span class="text-xs text-slate-500">{{ scope.row.detail || '无详情' }}</span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="操作人" min-width="160" align="center">
            <template #default="scope">
              <div class="flex items-center justify-center gap-1.5 text-slate-600">
                <el-icon :size="14"><UserIcon /></el-icon>
                <span class="font-medium">{{
                  scope.row.user_email || `用户编号: ${scope.row.user ?? '-'}`
                }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="IP 地址" min-width="130" align="center">
            <template #default="scope">
              <div
                class="flex items-center justify-center gap-1.5 text-slate-500 font-mono text-xs"
              >
                <el-icon><LocationFilled /></el-icon>
                {{ scope.row.ip || '-' }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="发生时间" min-width="180" align="center">
            <template #default="scope">
              <div class="flex items-center justify-center gap-2 text-slate-500 text-sm font-mono">
                <el-icon><Clock /></el-icon>
                {{ formatDateTimeText(scope.row.created_at) }}
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Pagination Footer -->
      <div class="p-4 border-t border-slate-100 bg-white flex justify-end">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :page-sizes="[15, 30, 50, 100]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @size-change="handlePageSizeChange"
          @current-change="fetchLogs"
        />
      </div>
    </div>
  </div>
</template>
