<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { usePageSizeReset } from '@/composables/usePagination'
import { exportDataset, getAutoRetrainStatus, getDatasets } from '@/api/admin'
import { extractBlobErrorMessage } from '@/utils/blobReader'
import { parseContentDispositionFilename } from '@/utils/contentDisposition'
import { downloadBlob } from '@/utils/download'
import { ElMessage } from 'element-plus'
import { DataLine, Download, Files, Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'

const loading = ref(false)
/** @type {import('vue').Ref<any[]>} */ const tableData = ref([])
const total = ref(0)
const errorMessage = ref('')
const exportErrorMessage = ref('')
const autoRetrainLoading = ref(false)
const autoRetrainErrorMessage = ref('')
/** @type {import('vue').Ref<any>} */ const autoRetrainStatus = ref(null)
/** @type {import('vue').Ref<any>} */ const tableRef = ref(null)
/** @type {import('vue').Ref<any[]>} */ const selectedRows = ref([])
const exportFormat = ref('csv')

const queryParams = reactive({
  page: 1,
  page_size: 15,
  keyword: '',
  project_name: '',
  category: '',
  source: '',
  final_sentiment: '',
  review_status: '',
  analysis_channel: '',
  start_date: '',
  end_date: '',
})

const emptyStateMessage = computed(() => errorMessage.value || '暂无可导出的分析记录')
const selectedCount = computed(() => selectedRows.value.length)
const currentPageCorrectedCount = computed(
  () =>
    tableData.value.filter(
      (row) => row.corrected_sentiment !== null && row.corrected_sentiment !== undefined
    ).length
)
const autoRetrainProgressPercent = computed(() => {
  const ratio = Number(autoRetrainStatus.value?.progress_ratio || 0)
  return Math.min(Math.round(ratio * 100), 100)
})
const latestAutoRetrainBatch = computed(() => autoRetrainStatus.value?.recent_batches?.[0] || null)

const buildQueryPayload = ({ includePagination = true } = {}) => {
  const payload = {}
  if (includePagination) {
    payload.page = queryParams.page
    payload.page_size = queryParams.page_size
  }

  for (const key of [
    'keyword',
    'project_name',
    'category',
    'source',
    'final_sentiment',
    'review_status',
    'analysis_channel',
    'start_date',
    'end_date',
  ]) {
    const value = String(queryParams[key] ?? '').trim()
    if (value) payload[key] = value
  }
  return payload
}

const fetchDatasets = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await getDatasets(buildQueryPayload())
    const rows = res?.data?.results ?? res?.data ?? []
    tableData.value = Array.isArray(rows) ? rows : []
    total.value = res?.data?.count ?? tableData.value.length
    return true
  } catch {
    tableData.value = []
    total.value = 0
    errorMessage.value = '数据集记录加载失败，请稍后重试'
    return false
  } finally {
    loading.value = false
  }
}

const fetchAutoRetrainStatus = async () => {
  autoRetrainLoading.value = true
  autoRetrainErrorMessage.value = ''
  try {
    const res = await getAutoRetrainStatus()
    autoRetrainStatus.value = res?.data || null
  } catch {
    autoRetrainStatus.value = null
    autoRetrainErrorMessage.value = '自动重训状态加载失败'
  } finally {
    autoRetrainLoading.value = false
  }
}

const refreshAll = async () => {
  await Promise.all([fetchDatasets(), fetchAutoRetrainStatus()])
}

onMounted(refreshAll)

const { handlePageSizeChange } = usePageSizeReset(queryParams, fetchDatasets)

const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

const handleSearchChange = async () => {
  queryParams.page = 1
  await fetchDatasets()
}

const resetFilters = async () => {
  Object.assign(queryParams, {
    page: 1,
    keyword: '',
    project_name: '',
    category: '',
    source: '',
    final_sentiment: '',
    review_status: '',
    analysis_channel: '',
    start_date: '',
    end_date: '',
  })
  tableRef.value?.clearSelection()
  await fetchDatasets()
}

const extractExportErrorMessage = (error) =>
  extractBlobErrorMessage(error, '数据集导出失败，请稍后重试')

const downloadExport = async (params, fallbackName) => {
  try {
    exportErrorMessage.value = ''
    const response = await exportDataset({
      ...params,
      format: exportFormat.value,
    })
    const blob = response?.data instanceof Blob ? response.data : new Blob([response?.data || ''])
    const filename = parseContentDispositionFilename(
      response?.headers?.['content-disposition'],
      fallbackName
    )
    downloadBlob(blob, filename)
    return true
  } catch (/** @type {any} */ err) {
    const message = await extractExportErrorMessage(err)
    exportErrorMessage.value = message
    ElMessage.error(message)
    return false
  }
}

const handleExportFiltered = async () => {
  if (!total.value) {
    ElMessage.warning('当前筛选条件下暂无可导出数据')
    return
  }
  const suffix = exportFormat.value === 'xlsx' ? 'xlsx' : 'csv'
  const ok = await downloadExport(
    buildQueryPayload({ includePagination: false }),
    `训练数据集_${Date.now()}.${suffix}`
  )
  if (ok) ElMessage.success(`已按当前筛选导出 ${total.value} 条记录`)
}

const handleExportSelected = async () => {
  const ids = selectedRows.value.map((row) => row.id)
  if (!ids.length) {
    ElMessage.warning('请先勾选要导出的记录')
    return
  }
  const suffix = exportFormat.value === 'xlsx' ? 'xlsx' : 'csv'
  const ok = await downloadExport(
    { ids: ids.join(',') },
    `训练数据集_选中${ids.length}条.${suffix}`
  )
  if (ok) ElMessage.success(`已导出选中的 ${ids.length} 条记录`)
}

const handleExportRow = async (row) => {
  const suffix = exportFormat.value === 'xlsx' ? 'xlsx' : 'csv'
  const ok = await downloadExport({ ids: String(row.id) }, `训练数据_${row.id}.${suffix}`)
  if (ok) ElMessage.success('已导出当前记录')
}

const formatDateTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
}

const getSentimentTagType = (sentiment) => {
  const normalized = Number(sentiment)
  if (normalized === -1 || sentiment === 'negative') return 'danger'
  if (normalized === 1 || sentiment === 'positive') return 'success'
  return 'info'
}

const hasCorrection = (row) =>
  row?.corrected_sentiment !== null && row?.corrected_sentiment !== undefined

const getLabelSourceText = (row) => (hasCorrection(row) ? '人工修正' : '模型标签')

const isHighConfidence = (row) => Number(row?.confidence) >= 0.7

const isEffectivelyReviewed = (row) => {
  if (row?.review_status) return row.review_status === 'reviewed'
  return isHighConfidence(row) || Boolean(row?.reviewed_at)
}

const getReviewStatusText = (row) =>
  row?.review_status_display || (isEffectivelyReviewed(row) ? '已审核' : '未审核')

const getReviewStatusType = (row) => (isEffectivelyReviewed(row) ? 'success' : 'warning')

const getReviewMetaText = (row) => {
  if (row?.reviewed_by_email) return row.reviewed_by_email
  if (isHighConfidence(row)) return '高置信自动通过'
  return '待分析师审核'
}

const getChannelText = (row) => {
  if (row?.analysis_channel === 'batch') return '批量分析'
  if (row?.analysis_channel === 'single') return '单条分析'
  return row?.analysis_channel || '-'
}

const formatCategorySource = (row) => {
  const category = row?.category || '-'
  const source = row?.source || row?.analysis_source_name || '-'
  return `${category} / ${source}`
}

const getTrainingStatusType = (status) => {
  if (status === 'succeeded') return 'success'
  if (status === 'failed' || status === 'cancelled') return 'danger'
  if (status === 'running') return 'primary'
  return 'warning'
}

const getTrainingStatusText = (status) => {
  const map = {
    queued: '已触发',
    running: '训练中',
    succeeded: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status || '未触发'
}
</script>

<template>
  <div class="h-full flex flex-col space-y-6">
    <PageHeader title="数据集管理" description="沉淀用户分析记录与分析师修正标签，导出可训练数据集">
      <template #actions>
        <div class="flex flex-wrap items-center gap-3">
          <el-select v-model="exportFormat" class="!w-28" size="large">
            <el-option label="CSV" value="csv" />
            <el-option label="XLSX" value="xlsx" />
          </el-select>
          <el-button
            type="primary"
            class="!h-10 !px-4 !rounded-lg"
            :disabled="!selectedCount"
            @click="handleExportSelected"
          >
            <el-icon class="mr-1"><Download /></el-icon>
            导出选中{{ selectedCount ? ` (${selectedCount})` : '' }}
          </el-button>
          <el-button type="primary" class="!h-10 !px-4 !rounded-lg" @click="handleExportFiltered">
            <el-icon class="mr-1"><DataLine /></el-icon>
            导出筛选结果
          </el-button>
        </div>
      </template>
    </PageHeader>

    <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div class="text-sm font-semibold text-slate-900">5000 条自动重训触发</div>
          <div class="mt-1 text-sm text-slate-500">
            达到阈值后自动保存本批训练数据集，并提交一条训练任务
          </div>
        </div>
        <div class="flex items-center gap-2">
          <el-tag
            :type="autoRetrainStatus?.enabled ? 'success' : 'info'"
            effect="plain"
            class="!rounded-md"
          >
            {{ autoRetrainStatus?.enabled ? '已启用' : '未启用' }}
          </el-tag>
          <el-button
            :loading="autoRetrainLoading"
            :icon="Refresh"
            circle
            @click="fetchAutoRetrainStatus"
          />
        </div>
      </div>

      <el-alert
        v-if="autoRetrainErrorMessage"
        :title="autoRetrainErrorMessage"
        type="error"
        show-icon
        :closable="false"
        class="mt-4"
      />

      <div v-else class="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <div class="mb-2 flex items-center justify-between text-sm">
            <span class="font-medium text-slate-700">
              当前累计 {{ autoRetrainStatus?.progress_count || 0 }} /
              {{ autoRetrainStatus?.threshold || 5000 }}
            </span>
            <span class="text-slate-500">
              还差
              {{ autoRetrainStatus?.remaining_to_next || autoRetrainStatus?.threshold || 5000 }} 条
            </span>
          </div>
          <el-progress
            :percentage="autoRetrainProgressPercent"
            :stroke-width="10"
            :show-text="false"
          />
          <div class="mt-4 grid grid-cols-3 gap-3">
            <div class="rounded-lg bg-slate-50 px-3 py-2">
              <div class="text-xs text-slate-500">可训练累计</div>
              <div class="mt-1 font-mono text-lg font-semibold text-slate-900">
                {{ autoRetrainStatus?.pending_count || 0 }}
              </div>
            </div>
            <div class="rounded-lg bg-slate-50 px-3 py-2">
              <div class="text-xs text-slate-500">已保存批次</div>
              <div class="mt-1 font-mono text-lg font-semibold text-slate-900">
                {{ autoRetrainStatus?.batch_count || 0 }}
              </div>
            </div>
            <div class="rounded-lg bg-slate-50 px-3 py-2">
              <div class="text-xs text-slate-500">已入集记录</div>
              <div class="mt-1 font-mono text-lg font-semibold text-slate-900">
                {{ autoRetrainStatus?.batched_total || 0 }}
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-slate-100 bg-slate-50/70 px-4 py-3">
          <div class="mb-2 text-xs font-semibold text-slate-500">最近自动批次</div>
          <div v-if="latestAutoRetrainBatch" class="space-y-2">
            <div class="truncate text-sm font-semibold text-slate-900">
              {{ latestAutoRetrainBatch.dataset_ref }}
            </div>
            <div class="flex flex-wrap gap-2 text-xs text-slate-500">
              <span>{{ latestAutoRetrainBatch.result_count }} 条</span>
              <span>{{ formatDateTime(latestAutoRetrainBatch.generated_at) }}</span>
            </div>
            <el-tag
              v-if="latestAutoRetrainBatch.training_run"
              :type="getTrainingStatusType(latestAutoRetrainBatch.training_run.status)"
              class="!rounded-md"
            >
              {{ getTrainingStatusText(latestAutoRetrainBatch.training_run.status) }}
            </el-tag>
            <span v-else class="text-xs text-slate-400">暂无训练任务</span>
          </div>
          <div v-else class="text-sm text-slate-500">暂无自动保存批次</div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <div class="text-sm text-slate-500">筛选结果</div>
        <div class="mt-2 text-2xl font-bold text-slate-900">{{ total }}</div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <div class="text-sm text-slate-500">当前页人工修正</div>
        <div class="mt-2 text-2xl font-bold text-indigo-600">{{ currentPageCorrectedCount }}</div>
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <div class="text-sm text-slate-500">已选记录</div>
        <div class="mt-2 text-2xl font-bold text-slate-900">{{ selectedCount }}</div>
      </div>
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
      <el-alert
        v-if="exportErrorMessage"
        :title="exportErrorMessage"
        type="error"
        show-icon
        :closable="false"
        class="mx-6 mt-6"
      />

      <div class="border-b border-slate-100 bg-slate-50/50 p-6">
        <div class="grid grid-cols-2 items-end gap-4 md:grid-cols-4 xl:grid-cols-8">
          <div class="col-span-2 space-y-1.5">
            <label class="ml-1 text-xs font-semibold uppercase text-slate-500">内容检索</label>
            <el-input
              v-model="queryParams.keyword"
              placeholder="搜索评论、用户、备注..."
              class="el-input-rounded"
              clearable
              @change="handleSearchChange"
            >
              <template #prefix>
                <el-icon class="text-slate-400"><Search /></el-icon>
              </template>
            </el-input>
          </div>

          <div class="space-y-1.5">
            <label class="ml-1 text-xs font-semibold uppercase text-slate-500">最终标签</label>
            <el-select
              v-model="queryParams.final_sentiment"
              class="!w-full el-input-rounded"
              placeholder="全部"
              @change="handleSearchChange"
            >
              <el-option label="全部" value="" />
              <el-option label="积极" value="1" />
              <el-option label="中性" value="0" />
              <el-option label="消极" value="-1" />
            </el-select>
          </div>

          <div class="space-y-1.5">
            <label class="ml-1 text-xs font-semibold uppercase text-slate-500">审核状态</label>
            <el-select
              v-model="queryParams.review_status"
              class="!w-full el-input-rounded"
              placeholder="全部"
              @change="handleSearchChange"
            >
              <el-option label="全部" value="" />
              <el-option label="已审核" value="reviewed" />
              <el-option label="未审核" value="unreviewed" />
            </el-select>
          </div>

          <div class="space-y-1.5">
            <label class="ml-1 text-xs font-semibold uppercase text-slate-500">分析渠道</label>
            <el-select
              v-model="queryParams.analysis_channel"
              class="!w-full el-input-rounded"
              placeholder="全部"
              @change="handleSearchChange"
            >
              <el-option label="全部" value="" />
              <el-option label="单条分析" value="single" />
              <el-option label="批量分析" value="batch" />
            </el-select>
          </div>

          <div class="space-y-1.5">
            <label class="ml-1 text-xs font-semibold uppercase text-slate-500">分类</label>
            <el-input
              v-model="queryParams.category"
              placeholder="分类"
              clearable
              @change="handleSearchChange"
            />
          </div>

          <div class="space-y-1.5">
            <label class="ml-1 text-xs font-semibold uppercase text-slate-500">来源</label>
            <el-input
              v-model="queryParams.source"
              placeholder="来源"
              clearable
              @change="handleSearchChange"
            />
          </div>

          <div class="flex items-center gap-2">
            <el-button :icon="Refresh" circle @click="refreshAll" />
            <el-button class="!rounded-lg" @click="resetFilters">重置</el-button>
          </div>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          <input
            v-model="queryParams.start_date"
            type="date"
            class="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none focus:border-blue-300"
            @change="handleSearchChange"
          />
          <input
            v-model="queryParams.end_date"
            type="date"
            class="h-9 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none focus:border-blue-300"
            @change="handleSearchChange"
          />
          <el-input
            v-model="queryParams.project_name"
            placeholder="项目名称"
            clearable
            @change="handleSearchChange"
          />
        </div>
      </div>

      <div class="flex-1 overflow-hidden">
        <el-table
          ref="tableRef"
          v-loading="loading"
          :data="tableData"
          class="admin-table h-full"
          header-cell-class-name="admin-table-header"
          row-key="id"
          @selection-change="handleSelectionChange"
        >
          <template #empty>
            <div class="py-10 text-sm text-slate-500">
              {{ emptyStateMessage }}
            </div>
          </template>

          <el-table-column type="selection" width="48" align="center" :reserve-selection="true" />
          <el-table-column prop="id" label="编号" width="76" align="center" />

          <el-table-column label="用户记录" min-width="300" header-align="center">
            <template #default="scope">
              <div class="flex items-start gap-4 py-2">
                <div
                  class="h-10 w-10 shrink-0 rounded-xl bg-indigo-50 flex items-center justify-center"
                >
                  <el-icon class="text-indigo-600" :size="20"><Files /></el-icon>
                </div>
                <div class="min-w-0">
                  <div class="line-clamp-2 font-semibold text-slate-900">
                    {{ scope.row.content || '-' }}
                  </div>
                  <div class="mt-1 text-xs text-slate-500">
                    {{ scope.row.user_email || '-' }} · {{ getChannelText(scope.row) }}
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="最终标签" width="130" align="center">
            <template #default="scope">
              <div class="flex flex-col items-center gap-1">
                <el-tag
                  :type="getSentimentTagType(scope.row.final_sentiment)"
                  effect="dark"
                  class="!rounded-md !px-3"
                >
                  {{ scope.row.final_sentiment_display || '-' }}
                </el-tag>
                <span class="text-xs text-slate-500">{{ getLabelSourceText(scope.row) }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="模型 / 修正" width="150" align="center">
            <template #default="scope">
              <div class="text-sm text-slate-600">
                <div>模型：{{ scope.row.model_sentiment_display || '-' }}</div>
                <div>修正：{{ scope.row.corrected_sentiment_display || '未修正' }}</div>
                <div class="font-mono text-xs text-slate-400">
                  {{
                    scope.row.confidence != null
                      ? `${(Number(scope.row.confidence) * 100).toFixed(1)}%`
                      : '-'
                  }}
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="分类 / 来源" width="170" align="center">
            <template #default="scope">
              <span class="text-sm text-slate-500">{{ formatCategorySource(scope.row) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="审核信息" width="170" align="center">
            <template #default="scope">
              <div class="flex flex-col items-center gap-1 text-sm text-slate-600">
                <div class="flex flex-wrap justify-center gap-1">
                  <el-tag :type="getReviewStatusType(scope.row)" effect="plain" class="!rounded-md">
                    {{ getReviewStatusText(scope.row) }}
                  </el-tag>
                  <el-tag v-if="hasCorrection(scope.row)" type="primary" class="!rounded-md">
                    人工修正
                  </el-tag>
                </div>
                <div class="max-w-full truncate text-xs text-slate-500">
                  {{ getReviewMetaText(scope.row) }}
                </div>
                <div class="font-mono text-xs text-slate-400">
                  {{ formatDateTime(scope.row.reviewed_at) }}
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="created_at" label="分析时间" width="140" align="center">
            <template #default="scope">
              <span class="font-mono text-sm text-slate-500">
                {{ formatDateTime(scope.row.created_at) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="90" align="center">
            <template #default="scope">
              <el-button link type="primary" class="!font-bold" @click="handleExportRow(scope.row)">
                <el-icon class="mr-1"><Download /></el-icon>
                导出
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="p-4 border-t border-slate-100 bg-white flex justify-end">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :page-sizes="[15, 30, 50, 100]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @size-change="handlePageSizeChange"
          @current-change="fetchDatasets"
        />
      </div>
    </div>
  </div>
</template>
