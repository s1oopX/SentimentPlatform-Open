<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  downloadBatchTemplate,
  getBatchSchema,
  getRuntimeCapabilities,
  performBatchAnalysis,
} from '@/api/analysis'
import { extractErrorMessage } from '@/api/request'
import { ElMessage } from 'element-plus'
import ErrorRetryAlert from '@/components/ErrorRetryAlert.vue'
import { downloadBlob } from '@/utils/download'
import {
  UploadFilled,
  FolderOpened,
  Check,
  Download,
  Document,
  DataAnalysis,
  List,
  Refresh,
} from '@element-plus/icons-vue'
import {
  FALLBACK_RUNTIME_CAPABILITIES,
  normalizeRuntimeCapabilities,
} from '@/utils/runtimeCapabilities'
import { MAX_BATCH_ROWS, validateBatchRowLimit } from '@/utils/batchRowLimit'
import { parseContentDispositionFilename } from '@/utils/contentDisposition'
import { formatDateTimeText } from '@/utils/dateTime'

const router = useRouter()
/**
 * @typedef {{
 *   raw: File
 *   name?: string
 *   [key: string]: any
 * }} BatchFileEntry
 * @typedef {{
 *   max_rows?: number
 *   xlsx?: { columns?: any[]; [key: string]: any }
 *   [key: string]: any
 * }} BatchSchema
 * @typedef {{
 *   total?: number
 *   results?: any[]
 *   summary?: {
 *     total?: number
 *     sentiment_counts?: { positive?: number, neutral?: number, negative?: number }
 *     avg_confidence?: number
 *     keyword_top?: any[]
 *     [key: string]: any
 *   }
 *   [key: string]: any
 * }} BatchAnalysisResponse
 */
const loading = ref(false)
/** @type {import('vue').Ref<BatchFileEntry[]>} */ const fileList = ref([])
const errorMessage = ref('')
const uploadProgress = ref(0)
const progressText = ref('')
/** @type {import('vue').Ref<BatchAnalysisResponse | null>} */ const batchResult = ref(null)
const runtimeCapabilities = ref(FALLBACK_RUNTIME_CAPABILITIES)
/** @type {import('vue').Ref<BatchSchema | null>} */ const batchSchema = ref(null)
const schemaLoadError = ref('')
const downloadingTemplateFormat = ref('')
const acceptTypes = computed(() =>
  runtimeCapabilities.value.batch_analysis_supported_formats.join(',')
)
const schemaMaxRows = computed(() => batchSchema.value?.max_rows || MAX_BATCH_ROWS)
const schemaColumns = computed(() => batchSchema.value?.xlsx?.columns || [])
const progressStatus = computed(() => (uploadProgress.value >= 100 ? 'success' : undefined))
const batchSummary = computed(() => batchResult.value?.summary || {})
const batchResults = computed(() => batchResult.value?.results || [])
const totalAnalyzed = computed(() =>
  Number(batchResult.value?.total || batchSummary.value.total || batchResults.value.length || 0)
)
const sentimentCounts = computed(
  () =>
    batchSummary.value.sentiment_counts || {
      positive: 0,
      neutral: 0,
      negative: 0,
    }
)
const avgConfidenceText = computed(() => {
  const confidence = Number(batchSummary.value.avg_confidence)
  return Number.isFinite(confidence) ? `${(confidence * 100).toFixed(1)}%` : '--'
})
const keywordTop = computed(() => batchSummary.value.keyword_top || [])
const sentimentDistribution = computed(() => [
  {
    key: 'positive',
    label: '积极',
    count: Number(sentimentCounts.value.positive || 0),
    className: 'bg-emerald-500',
  },
  {
    key: 'neutral',
    label: '中性',
    count: Number(sentimentCounts.value.neutral || 0),
    className: 'bg-amber-400',
  },
  {
    key: 'negative',
    label: '消极',
    count: Number(sentimentCounts.value.negative || 0),
    className: 'bg-rose-500',
  },
])

const sentimentTagType = (sentiment) => {
  if (sentiment === 1) return 'success'
  if (sentiment === -1) return 'danger'
  return 'info'
}

const sentimentLabel = (row) =>
  row?.sentiment_display ||
  (row?.sentiment === 1 ? '积极' : row?.sentiment === -1 ? '消极' : '中性')

const formatConfidence = (confidence) =>
  confidence === null || confidence === undefined || confidence === ''
    ? '--'
    : `${(Number(confidence) * 100).toFixed(1)}%`

const formatKeyword = (keyword) => {
  if (typeof keyword === 'string') return keyword
  return keyword?.keyword || keyword?.word || String(keyword || '')
}

const getResultKeywords = (row) => {
  return Array.isArray(row?.keywords)
    ? row.keywords.map(formatKeyword).filter(Boolean).slice(0, 4)
    : []
}

const getDistributionWidth = (count) => {
  if (!totalAnalyzed.value) return '0%'
  return `${Math.max(4, Math.round((count / totalAnalyzed.value) * 100))}%`
}

const loadRuntimeCapabilities = async () => {
  try {
    const res = await getRuntimeCapabilities()
    runtimeCapabilities.value = normalizeRuntimeCapabilities(res.data)
  } catch {
    runtimeCapabilities.value = normalizeRuntimeCapabilities()
  }
}

const loadBatchSchema = async () => {
  schemaLoadError.value = ''
  try {
    const res = await getBatchSchema()
    batchSchema.value = res?.data || null
  } catch {
    batchSchema.value = null
    schemaLoadError.value = '字段说明加载失败，请使用模板文件作为准入格式'
  }
}

const handleDownloadTemplate = async (format) => {
  downloadingTemplateFormat.value = format
  errorMessage.value = ''
  try {
    const response = await downloadBatchTemplate(format)
    const fallback = `批量分析模板.${format === 'txt' ? 'txt' : 'xlsx'}`
    const filename = parseContentDispositionFilename(
      response?.headers?.['content-disposition'],
      fallback
    )
    downloadBlob(response.data, filename)
    ElMessage.success('模板已下载')
  } catch (/** @type {any} */ err) {
    errorMessage.value = extractErrorMessage(err, '模板下载失败，请稍后重试')
    ElMessage.error(errorMessage.value)
  } finally {
    downloadingTemplateFormat.value = ''
  }
}

const handleExceed = () => {
  ElMessage.warning('只能上传1个文件，请先删除旧文件')
}

const setUploadProgress = (value, text) => {
  uploadProgress.value = Math.max(0, Math.min(100, value))
  progressText.value = text
}

const resetUploadProgress = () => {
  uploadProgress.value = 0
  progressText.value = ''
}

const handleRequestUploadProgress = (event) => {
  if (!event?.total) {
    setUploadProgress(Math.max(uploadProgress.value, 60), '文件已上传，正在分析')
    return
  }
  const uploadedRatio = event.loaded / event.total
  setUploadProgress(30 + Math.round(uploadedRatio * 45), '正在上传文件')
}

const navigateToHistory = async () => {
  try {
    await router.push('/user/history')
  } catch {
    ElMessage.warning('未能跳转到历史记录，请稍后手动前往查看')
  }
}

const resetForNextUpload = () => {
  batchResult.value = null
  fileList.value = []
  resetUploadProgress()
  errorMessage.value = ''
}

const handleUpload = async () => {
  if (!fileList.value.length) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  loading.value = true
  errorMessage.value = ''
  batchResult.value = null
  setUploadProgress(10, '正在校验文件')
  try {
    const rowCheck = await validateBatchRowLimit(fileList.value[0].raw)
    if (!rowCheck.ok) {
      const message = rowCheck.message ?? '文件超出批量行数限制'
      errorMessage.value = message
      ElMessage.warning(message)
      loading.value = false
      resetUploadProgress()
      return
    }

    setUploadProgress(25, '正在准备上传')
    const formData = new FormData()
    formData.append('file', fileList.value[0].raw)

    const response = await performBatchAnalysis(formData, {
      onUploadProgress: handleRequestUploadProgress,
    })
    setUploadProgress(100, '分析完成')
    fileList.value = []
    batchResult.value = response?.data || null
    ElMessage.success('批量分析完成')
  } catch (/** @type {any} */ err) {
    errorMessage.value = extractErrorMessage(err, '批量分析提交失败，请稍后重试')
    ElMessage.error(errorMessage.value)
    resetUploadProgress()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.allSettled([loadRuntimeCapabilities(), loadBatchSchema()])
})
</script>

<template>
  <div class="max-w-4xl mx-auto space-y-8">
    <div class="space-y-2">
      <h1 class="text-3xl font-bold text-slate-900">批量分析</h1>
      <p class="text-slate-600 text-lg">上传文件进行批量评论情感分析</p>
    </div>

    <ErrorRetryAlert :message="errorMessage" :on-retry="handleUpload" :loading="loading" />

    <div class="bg-white rounded-xl border border-slate-200 shadow-md">
      <div class="p-6 border-b border-slate-100">
        <h3 class="flex items-center gap-2 text-xl font-semibold text-slate-900">
          <el-icon class="text-purple-600"><FolderOpened /></el-icon>
          上传分析任务
        </h3>
        <p class="text-base text-slate-500 mt-1">
          支持 Excel (.xlsx) 或文本 (.txt) 格式，单次最大支持
          {{ runtimeCapabilities.max_upload_size_mb }}MB
        </p>
      </div>

      <div class="p-8">
        <div class="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div class="space-y-2">
              <h4 class="flex items-center gap-2 text-base font-semibold text-slate-900">
                <el-icon class="text-purple-600"><Document /></el-icon>
                上传模板与字段
              </h4>
              <p class="text-sm text-slate-600">
                单次最多 {{ schemaMaxRows }} 条；Excel 从首个工作表第 2 行开始读取 A 列，TXT
                每行一条评论。
              </p>
              <p v-if="schemaLoadError" class="text-sm text-amber-600">{{ schemaLoadError }}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <el-button
                plain
                class="!rounded-lg"
                :loading="downloadingTemplateFormat === 'xlsx'"
                @click="handleDownloadTemplate('xlsx')"
              >
                <el-icon class="mr-1"><Download /></el-icon>
                Excel 模板
              </el-button>
              <el-button
                plain
                class="!rounded-lg"
                :loading="downloadingTemplateFormat === 'txt'"
                @click="handleDownloadTemplate('txt')"
              >
                <el-icon class="mr-1"><Download /></el-icon>
                TXT 模板
              </el-button>
            </div>
          </div>

          <div v-if="schemaColumns.length" class="mt-4 grid gap-3 md:grid-cols-2">
            <div
              v-for="column in schemaColumns"
              :key="column.field"
              class="rounded-lg border border-slate-200 bg-white p-3 text-sm"
            >
              <div class="flex items-center gap-2">
                <span class="font-semibold text-slate-900">{{ column.label }}</span>
                <el-tag v-if="column.required" size="small" type="danger" effect="plain"
                  >必填</el-tag
                >
              </div>
              <p class="mt-1 text-slate-500">{{ column.description }}</p>
            </div>
          </div>
        </div>

        <el-upload
          v-model:file-list="fileList"
          class="batch-uploader"
          drag
          action="#"
          :auto-upload="false"
          :limit="1"
          :accept="acceptTypes"
          @exceed="handleExceed"
        >
          <div class="py-10">
            <el-icon class="text-purple-300 mb-4" :size="64"><UploadFilled /></el-icon>
            <div class="text-xl font-medium text-slate-700 mb-2">
              将文件拖拽至此处，或
              <em class="text-purple-600 font-semibold not-italic">点击上传</em>
            </div>
            <div class="text-sm text-slate-500">目前仅支持具有单列长文本的 TXT / Excel</div>
          </div>
        </el-upload>

        <div class="mt-8 flex justify-end">
          <el-button
            type="primary"
            class="px-8 !h-12 !text-base !font-semibold !rounded-xl shadow-md hover:shadow-lg transition-all"
            color="#9333ea"
            :loading="loading"
            @click="handleUpload"
          >
            <el-icon class="mr-2"><Check /></el-icon>
            {{ loading ? progressText || '处理中...' : '提交批量分析' }}
          </el-button>
        </div>
        <div v-if="loading || uploadProgress > 0" class="mt-4 space-y-2">
          <div class="flex items-center justify-between text-sm text-slate-500">
            <span>{{ progressText || '等待处理' }}</span>
            <span>{{ uploadProgress }}%</span>
          </div>
          <el-progress
            :percentage="uploadProgress"
            :status="progressStatus"
            :stroke-width="8"
            striped
            striped-flow
          />
        </div>
      </div>
    </div>

    <div v-if="batchResult" class="bg-white rounded-xl border border-green-200 shadow-sm">
      <div
        class="flex flex-col gap-4 border-b border-green-100 bg-gradient-to-r from-green-50 to-blue-50 p-6 md:flex-row md:items-center md:justify-between"
      >
        <div>
          <h3 class="flex items-center gap-2 text-xl font-bold text-green-900">
            <el-icon class="text-green-600"><DataAnalysis /></el-icon>
            本次批量分析结果
          </h3>
          <p class="mt-1 text-sm text-green-800/70">已完成 {{ totalAnalyzed }} 条评论分析</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <el-button class="!rounded-lg" plain @click="resetForNextUpload">
            <el-icon class="mr-1"><Refresh /></el-icon>
            继续上传
          </el-button>
          <el-button type="primary" class="!rounded-lg" @click="navigateToHistory">
            <el-icon class="mr-1"><List /></el-icon>
            查看历史
          </el-button>
        </div>
      </div>

      <div class="p-6 space-y-6">
        <div class="grid gap-4 md:grid-cols-3">
          <div class="border-b border-slate-100 pb-4 md:border-b-0 md:border-r md:pr-4">
            <p class="text-sm font-medium text-slate-500">分析总数</p>
            <p class="mt-2 text-3xl font-bold tabular-nums text-slate-900">{{ totalAnalyzed }}</p>
          </div>
          <div class="border-b border-slate-100 pb-4 md:border-b-0 md:border-r md:pr-4">
            <p class="text-sm font-medium text-slate-500">平均置信度</p>
            <p class="mt-2 text-3xl font-bold tabular-nums text-slate-900">
              {{ avgConfidenceText }}
            </p>
          </div>
          <div>
            <p class="text-sm font-medium text-slate-500">高频关键词</p>
            <div v-if="keywordTop.length" class="mt-3 flex flex-wrap gap-2">
              <el-tag
                v-for="item in keywordTop.slice(0, 5)"
                :key="`${formatKeyword(item)}-${item.count}`"
                effect="plain"
              >
                {{ formatKeyword(item) }} {{ item.count }}
              </el-tag>
            </div>
            <p v-else class="mt-3 text-sm text-slate-400">暂无关键词</p>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 p-4">
          <div class="mb-4 flex items-center justify-between gap-3">
            <h4 class="text-base font-semibold text-slate-900">情感分布</h4>
            <span class="text-sm text-slate-500">共 {{ totalAnalyzed }} 条</span>
          </div>
          <div class="space-y-3">
            <div
              v-for="item in sentimentDistribution"
              :key="item.key"
              class="grid grid-cols-[3.5rem_1fr_3.5rem] items-center gap-3 text-sm"
            >
              <span class="font-medium text-slate-600">{{ item.label }}</span>
              <div class="h-2.5 overflow-hidden rounded-full bg-slate-100">
                <div
                  class="h-full rounded-full transition-all"
                  :class="item.className"
                  :style="{ width: getDistributionWidth(item.count) }"
                ></div>
              </div>
              <span class="text-right font-mono text-slate-500">{{ item.count }}</span>
            </div>
          </div>
        </div>

        <div>
          <div class="mb-3 flex items-center justify-between gap-3">
            <h4 class="text-base font-semibold text-slate-900">结果明细</h4>
            <span class="text-sm text-slate-500">本次返回 {{ batchResults.length }} 条</span>
          </div>
          <el-table
            :data="batchResults"
            max-height="420"
            class="batch-result-table rounded-lg border border-slate-200"
          >
            <template #empty>
              <div class="py-8 text-sm text-slate-500">暂无结果明细</div>
            </template>
            <el-table-column label="评论内容" min-width="320" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="font-medium text-slate-700">{{ row.comment_content || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="情感" width="110" align="center">
              <template #default="{ row }">
                <el-tag :type="sentimentTagType(row.sentiment)">
                  {{ sentimentLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="110" align="center">
              <template #default="{ row }">
                <span class="font-mono text-slate-500">{{ formatConfidence(row.confidence) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="关键词" min-width="180">
              <template #default="{ row }">
                <div v-if="getResultKeywords(row).length" class="flex flex-wrap gap-1">
                  <el-tag
                    v-for="keyword in getResultKeywords(row)"
                    :key="`${row.id}-${keyword}`"
                    size="small"
                    effect="plain"
                  >
                    {{ keyword }}
                  </el-tag>
                </div>
                <span v-else class="text-sm text-slate-400">-</span>
              </template>
            </el-table-column>
            <el-table-column label="分析时间" width="180">
              <template #default="{ row }">
                <span class="text-sm text-slate-500">{{ formatDateTimeText(row.created_at) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.batch-uploader :deep(.el-upload-dragger) {
  border: 2px dashed hsl(var(--border) / 0.8);
  border-radius: 0.75rem;
  background-color: transparent;
  transition: all 0.3s;
}
.dark .batch-uploader :deep(.el-upload-dragger) {
  border-color: #334155;
  background-color: #0f172a;
}
.batch-uploader :deep(.el-upload-dragger:hover) {
  border-color: #9333ea;
  background-color: rgba(147, 51, 234, 0.05);
}
</style>
