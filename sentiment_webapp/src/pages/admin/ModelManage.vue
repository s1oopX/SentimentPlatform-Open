<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { usePageSizeReset } from '@/composables/usePagination'
import { getModels, getModelLogs, activateModel } from '@/api/admin'
import { extractErrorMessage } from '@/api/request'
import { formatMetric, formatRuntimeType } from '@/composables/trainingConstants'
import { formatDateTimeText } from '@/utils/dateTime'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Cpu,
  Check,
  Refresh,
  Plus,
  Document,
  SwitchButton,
  CircleCheckFilled,
  WarningFilled,
} from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'

/**
 * @typedef {{
 *   id: number
 *   name?: string
 *   version?: string
 *   model_type?: string
 *   runtime_type?: string
 *   is_active?: boolean
 *   is_runtime_compatible?: boolean
 *   is_best_candidate?: boolean
 *   path?: string
 *   metrics?: Record<string, any>
 *   activated_at?: string | null
 *   source_run_id?: number | null
 *   source_run_name?: string
 *   source_run_record_id?: string
 *   dataset_ref?: string
 *   artifact_summary?: Record<string, any>
 *   runtime_incompatibility_reason?: string
 *   created_at?: string
 *   [key: string]: any
 * }} AdminModelRow
 */
const router = useRouter()
const loading = ref(false)
/** @type {import('vue').Ref<AdminModelRow[]>} */ const tableData = ref([])
const total = ref(0)
const errorMessage = ref('')
/** @type {import('vue').Ref<AdminModelRow | null>} */ const selectedModel = ref(null)
/** @type {import('vue').Ref<any[]>} */ const modelLogs = ref([])
const logsLoading = ref(false)
const logsError = ref('')
const logsWarning = ref('')
const logsDrawerVisible = ref(false)
/** @type {import('vue').Ref<number | null>} */ const activatingModelId = ref(null)
const queryParams = reactive({
  page: 1,
  page_size: 100,
})
const filters = reactive({
  status: '',
  model_type: '',
  runtime_type: '',
})

const statusOptions = [
  { label: '运行中', value: 'active' },
  { label: '可启用', value: 'available' },
  { label: '不兼容', value: 'incompatible' },
]

const modelTypeOptions = computed(() =>
  Array.from(new Set(tableData.value.map((row) => row.model_type).filter(Boolean))).map(
    (value) => ({ label: value, value })
  )
)

const runtimeTypeOptions = computed(() =>
  Array.from(new Set(tableData.value.map((row) => row.runtime_type).filter(Boolean))).map(
    (value) => ({ label: formatRuntimeType(value), value })
  )
)

const getStatusValue = (row) => {
  if (row?.is_active) return 'active'
  return row?.is_runtime_compatible ? 'available' : 'incompatible'
}

const filteredTableData = computed(() =>
  tableData.value.filter((row) => {
    if (filters.status && getStatusValue(row) !== filters.status) return false
    if (filters.model_type && row.model_type !== filters.model_type) return false
    if (filters.runtime_type && row.runtime_type !== filters.runtime_type) return false
    return true
  })
)

const emptyStateMessage = computed(() => {
  if (errorMessage.value) return errorMessage.value
  if (tableData.value.length > 0 && filteredTableData.value.length === 0) {
    return '当前筛选条件下暂无模型'
  }
  return '暂无模型记录'
})

const canActivateModel = (row) => Boolean(row && !row.is_active && row.is_runtime_compatible)

const getActivateLabel = (row) => {
  if (row?.is_active) return '已激活'
  return '切换'
}

const fetchModels = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await getModels({
      page: queryParams.page,
      page_size: queryParams.page_size,
    })
    const rows = res?.data?.results ?? res?.data ?? []
    tableData.value = Array.isArray(rows) ? rows.sort((a, b) => a.id - b.id) : []
    total.value = res?.data?.count ?? tableData.value.length
    const currentSelected = selectedModel.value
    if (currentSelected && !tableData.value.some((item) => item.id === currentSelected.id)) {
      selectedModel.value = null
      modelLogs.value = []
      logsError.value = ''
      logsWarning.value = ''
      logsDrawerVisible.value = false
    }
  } catch {
    tableData.value = []
    total.value = 0
    selectedModel.value = null
    modelLogs.value = []
    logsLoading.value = false
    logsError.value = ''
    logsWarning.value = ''
    logsDrawerVisible.value = false
    errorMessage.value = '模型列表加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchModels())

const { handlePageSizeChange } = usePageSizeReset(queryParams, fetchModels)

const handleViewLogs = async (row) => {
  selectedModel.value = row
  logsDrawerVisible.value = true
  logsLoading.value = true
  logsError.value = ''
  logsWarning.value = ''
  modelLogs.value = []

  try {
    const res = await getModelLogs(row.id)
    modelLogs.value = Array.isArray(res?.data?.logs) ? res.data.logs : []
    logsWarning.value = typeof res?.data?.warning === 'string' ? res.data.warning : ''
  } catch (/** @type {any} */ e) {
    logsError.value = e?.response?.data?.error || '模型日志加载失败，请稍后重试'
  } finally {
    logsLoading.value = false
  }
}

const handleActivate = async (row) => {
  if (row.is_active) {
    ElMessage.info('该模型已是当前运行模型')
    return
  }
  if (!canActivateModel(row)) {
    ElMessage.warning('该模型当前不兼容在线运行，不能启用')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认将 "${row.name || row.version}" 切换为当前在线模型吗？当前运行模型会自动停用。`,
      `${getActivateLabel(row)}模型`,
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    activatingModelId.value = row.id
    await activateModel(row.id)
    ElMessage.success(`模型 "${row.name || row.version}" 已切换为当前运行模型`)
    await fetchModels()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(extractErrorMessage(e, '模型激活失败'))
  } finally {
    if (activatingModelId.value === row.id) {
      activatingModelId.value = null
    }
  }
}
</script>

<template>
  <div class="flex h-full flex-col space-y-6">
    <PageHeader title="模型管理" description="查看所有模型，切换当前运行模型">
      <template #actions>
        <el-button
          type="primary"
          class="!h-11 !px-6 !text-base !font-semibold !rounded-xl shadow-md"
          @click="router.push('/admin/training')"
        >
          <el-icon class="mr-2"><Plus /></el-icon>
          进入训练中心
        </el-button>
      </template>
    </PageHeader>

    <div
      class="flex flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <div
        v-if="errorMessage"
        class="mx-6 mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        {{ errorMessage }}
      </div>

      <!-- Toolbar -->
      <div
        class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/50 p-5"
      >
        <div class="flex flex-wrap items-center gap-3">
          <el-select v-model="filters.status" clearable placeholder="运行状态" class="!w-36">
            <el-option
              v-for="option in statusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-select v-model="filters.model_type" clearable placeholder="训练类型" class="!w-48">
            <el-option
              v-for="option in modelTypeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-select v-model="filters.runtime_type" clearable placeholder="运行时" class="!w-44">
            <el-option
              v-for="option in runtimeTypeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
        <el-button data-testid="model-refresh-button" :icon="Refresh" circle @click="fetchModels" />
      </div>

      <!-- Table Section -->
      <div class="flex-1 overflow-hidden">
        <el-table
          v-loading="loading"
          :data="filteredTableData"
          class="admin-table h-full"
          header-cell-class-name="admin-table-header"
        >
          <template #empty>
            <div class="py-10 text-sm text-slate-500">
              {{ emptyStateMessage }}
            </div>
          </template>
          <el-table-column prop="id" label="编号" width="60" align="center" />

          <el-table-column label="模型信息" min-width="200" header-align="center">
            <template #default="scope">
              <div class="flex items-center gap-4 py-2 pl-4">
                <div
                  class="h-10 w-10 shrink-0 rounded-xl bg-blue-50 flex items-center justify-center"
                >
                  <el-icon class="text-blue-600" :size="20"><Cpu /></el-icon>
                </div>
                <div class="flex flex-col">
                  <span class="font-bold text-slate-900">{{
                    scope.row.name || scope.row.version || '-'
                  }}</span>
                  <span class="text-xs text-slate-500 italic">{{ scope.row.version || '-' }}</span>
                  <div class="mt-1 flex flex-wrap items-center gap-2">
                    <span class="text-xs text-slate-500">{{ scope.row.model_type || '-' }}</span>
                    <el-tag v-if="scope.row.is_best_candidate" size="small" type="success"
                      >最佳候选</el-tag
                    >
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="激活状态" width="110" align="center">
            <template #default="scope">
              <div class="flex items-center justify-center whitespace-nowrap">
                <div
                  v-if="scope.row.is_active"
                  class="flex items-center gap-1.5 text-green-600 bg-green-50 px-3 py-1 rounded-full text-xs font-bold"
                >
                  <el-icon><Check /></el-icon>
                  运行中
                </div>
                <div
                  v-else
                  class="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold"
                  :class="
                    scope.row.is_runtime_compatible
                      ? 'text-slate-400 bg-slate-50'
                      : 'text-amber-600 bg-amber-50'
                  "
                >
                  {{ scope.row.is_runtime_compatible ? '待启用' : '不兼容' }}
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="性能指标" min-width="180" align="center">
            <template #default="scope">
              <div class="flex flex-col gap-0.5 text-xs text-slate-500">
                <span
                  >Macro-F1：<b class="text-slate-700">{{
                    formatMetric(scope.row.metrics?.macro_f1)
                  }}</b></span
                >
                <span
                  >准确率：<b class="text-slate-700">{{
                    formatMetric(scope.row.metrics?.accuracy)
                  }}</b></span
                >
                <span
                  >消极召回：<b class="text-slate-700">{{
                    formatMetric(scope.row.metrics?.negative_recall)
                  }}</b></span
                >
              </div>
            </template>
          </el-table-column>

          <el-table-column label="来源 / 运行时" min-width="160" align="center">
            <template #default="scope">
              <div class="flex flex-col items-center gap-1 text-sm">
                <span class="flex items-center gap-1 text-slate-600">
                  <el-icon :size="13" class="text-slate-400"><Cpu /></el-icon>
                  {{ formatRuntimeType(scope.row.runtime_type) }}
                </span>
                <span class="flex items-center gap-1">
                  <el-icon
                    :size="13"
                    :class="scope.row.artifact_complete ? 'text-emerald-500' : 'text-amber-500'"
                  >
                    <CircleCheckFilled v-if="scope.row.artifact_complete" />
                    <WarningFilled v-else />
                  </el-icon>
                  <span
                    :class="scope.row.artifact_complete ? 'text-emerald-600' : 'text-amber-600'"
                    class="text-xs"
                  >
                    {{ scope.row.artifact_complete ? '产物完整' : '产物缺失' }}
                  </span>
                </span>
                <span v-if="scope.row.activated_at" class="text-xs text-slate-400">
                  激活：{{ scope.row.activated_at?.slice(0, 10) }}
                </span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="操作" min-width="140" align="center">
            <template #default="scope">
              <div class="flex items-center justify-center gap-2">
                <el-button
                  v-if="canActivateModel(scope.row)"
                  link
                  type="success"
                  class="!font-bold"
                  :loading="activatingModelId === scope.row.id"
                  :disabled="activatingModelId === scope.row.id"
                  @click="handleActivate(scope.row)"
                >
                  <el-icon class="mr-1"><SwitchButton /></el-icon>
                  {{ getActivateLabel(scope.row) }}
                </el-button>
                <span
                  v-else-if="scope.row.is_active"
                  class="flex items-center gap-1 text-sm text-emerald-600 font-medium"
                >
                  <el-icon :size="14"><CircleCheckFilled /></el-icon>
                  已激活
                </span>
                <span v-else class="flex items-center gap-1 text-sm text-slate-400">
                  <el-icon :size="14"><WarningFilled /></el-icon>
                  不可用
                </span>
                <el-button link type="info" class="!font-bold" @click="handleViewLogs(scope.row)">
                  <el-icon class="mr-1"><Document /></el-icon>
                  日志
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <el-drawer
        v-model="logsDrawerVisible"
        :title="
          selectedModel ? `模型日志 - ${selectedModel.name || selectedModel.version}` : '模型日志'
        "
        size="46%"
      >
        <div class="space-y-4">
          <div class="flex justify-end">
            <el-button
              v-if="selectedModel"
              :loading="logsLoading"
              :icon="Refresh"
              @click="handleViewLogs(selectedModel)"
              >刷新</el-button
            >
          </div>

          <div
            v-if="logsError"
            class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {{ logsError }}
          </div>

          <div
            v-if="!logsError && logsWarning"
            class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700"
          >
            {{ logsWarning }}
          </div>

          <div v-if="!logsError && logsLoading" class="text-sm text-slate-500">
            正在获取模型日志...
          </div>

          <div v-else-if="!logsError && modelLogs.length === 0" class="text-sm text-slate-500">
            暂无模型日志
          </div>

          <div v-else-if="!logsError" class="space-y-3">
            <div
              v-for="(log, index) in modelLogs"
              :key="`${log.timestamp || index}-${index}`"
              class="rounded-xl border border-slate-200 bg-white px-4 py-3"
            >
              <div class="flex items-center justify-between gap-4">
                <span class="text-xs font-mono text-slate-500">{{
                  formatDateTimeText(log.timestamp)
                }}</span>
                <span
                  class="text-xs font-bold"
                  :class="
                    log.level === 'ERROR'
                      ? 'text-red-600'
                      : log.level === 'WARNING'
                        ? 'text-amber-600'
                        : 'text-green-600'
                  "
                >
                  {{ log.level || '-' }}
                </span>
              </div>
              <p class="mt-2 text-sm text-slate-700">{{ log.message || '-' }}</p>
            </div>
          </div>
        </div>
      </el-drawer>

      <!-- Pagination Footer -->
      <div class="flex justify-end border-t border-slate-100 bg-white p-4">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :page-sizes="[15, 30, 50, 100]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @size-change="handlePageSizeChange"
          @current-change="fetchModels"
        />
      </div>
    </div>
  </div>
</template>
