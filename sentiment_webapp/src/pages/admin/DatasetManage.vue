<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { usePageSizeReset } from '@/composables/usePagination'
import { exportDataset, getDatasets, importDataset } from '@/api/admin'
import { getRuntimeCapabilities } from '@/api/analysis'
import { extractBlobErrorMessage } from '@/utils/blobReader'
import { parseContentDispositionFilename } from '@/utils/contentDisposition'
import { downloadBlob } from '@/utils/download'
import { ElMessage } from 'element-plus'
import { Files, Refresh, Download, Plus } from '@element-plus/icons-vue'
import {
  FALLBACK_RUNTIME_CAPABILITIES,
  normalizeRuntimeCapabilities,
} from '@/utils/runtimeCapabilities'
import PageHeader from '@/components/PageHeader.vue'

const loading = ref(false)
/** @type {import('vue').Ref<any[]>} */ const tableData = ref([])
const total = ref(0)
const errorMessage = ref('')
const exportErrorMessage = ref('')
const importErrorMessage = ref('')
const isImporting = ref(false)
/** @type {import('vue').Ref<HTMLInputElement | null>} */ const fileInputRef = ref(null)
/** @type {import('vue').Ref<any>} */ const tableRef = ref(null)
/** @type {import('vue').Ref<any[]>} */ const selectedRows = ref([])
const batchMode = ref(false)
const runtimeCapabilities = ref(FALLBACK_RUNTIME_CAPABILITIES)
const queryParams = reactive({
  page: 1,
  page_size: 15,
})

const acceptTypes = computed(() =>
  runtimeCapabilities.value.dataset_import_supported_formats.join(',')
)

const loadRuntimeCapabilities = async () => {
  try {
    const res = await getRuntimeCapabilities()
    runtimeCapabilities.value = normalizeRuntimeCapabilities(res.data)
  } catch {
    runtimeCapabilities.value = normalizeRuntimeCapabilities()
  }
}

const emptyStateMessage = computed(() => errorMessage.value || '暂无数据集记录')

const buildDownloadFileName = (row) => {
  const fileName = `评论数据_${row?.id || '导出'}`
  return `${fileName}.csv`
}

const fetchDatasets = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await getDatasets({
      page: queryParams.page,
      page_size: queryParams.page_size,
    })
    const rows = res?.data?.results ?? res?.data ?? []
    tableData.value = Array.isArray(rows) ? rows : []
    total.value = res?.data?.count ?? tableData.value.length
    return true
  } catch {
    tableData.value = []
    total.value = 0
    errorMessage.value = '数据集列表加载失败，请稍后重试'
    return false
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([fetchDatasets(), loadRuntimeCapabilities()])
})

const { handlePageSizeChange } = usePageSizeReset(queryParams, fetchDatasets)

const refreshDatasetsAfterImport = async () => {
  queryParams.page = 1
  const refreshed = await fetchDatasets()
  if (!refreshed) {
    ElMessage.warning('数据集列表刷新失败，页面数据可能不是最新')
  }
}

const extractExportErrorMessage = (error) =>
  extractBlobErrorMessage(error, '数据集导出失败，请稍后重试')

const handleExport = async (row) => {
  try {
    exportErrorMessage.value = ''
    const response = await exportDataset({
      ids: String(row.id),
      format: 'csv',
    })
    const blob = response?.data instanceof Blob ? response.data : new Blob([response?.data || ''])
    const filename = parseContentDispositionFilename(
      response?.headers?.['content-disposition'],
      buildDownloadFileName(row)
    )
    downloadBlob(blob, filename)
  } catch (/** @type {any} */ err) {
    const message = await extractExportErrorMessage(err)
    exportErrorMessage.value = message
    ElMessage.error(message)
  }
}

const handleBatchExport = async () => {
  const ids = selectedRows.value.map((r) => r.id)
  if (!ids.length) {
    ElMessage.warning('请先勾选要导出的数据')
    return
  }
  try {
    exportErrorMessage.value = ''
    const response = await exportDataset({ ids: ids.join(','), format: 'csv' })
    const blob = response?.data instanceof Blob ? response.data : new Blob([response?.data || ''])
    const filename = parseContentDispositionFilename(
      response?.headers?.['content-disposition'],
      `数据集导出_${Date.now()}.csv`
    )
    downloadBlob(blob, filename)
    ElMessage.success(`已导出 ${ids.length} 条数据`)
  } catch (/** @type {any} */ err) {
    const message = await extractExportErrorMessage(err)
    exportErrorMessage.value = message
    ElMessage.error(message)
  }
}

const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

const handleSelectAll = () => {
  tableRef.value?.toggleAllSelection()
}

const handleCancelBatchMode = () => {
  batchMode.value = false
  tableRef.value?.clearSelection()
}

const triggerImport = () => {
  if (isImporting.value) return
  fileInputRef.value?.click()
}

const resetImportInput = (event) => {
  if (event?.target) {
    event.target.value = ''
  }
}

const handleImportChange = async (event) => {
  const file = event?.target?.files?.[0]
  if (!file) {
    return
  }

  importErrorMessage.value = ''
  const lowerName = file.name.toLowerCase()
  if (!lowerName.endsWith('.txt') && !lowerName.endsWith('.xlsx')) {
    const message = '只支持 TXT 和 Excel(.xlsx) 文件'
    importErrorMessage.value = message
    ElMessage.error(message)
    resetImportInput(event)
    return
  }

  const formData = new FormData()
  formData.append('file', file)

  isImporting.value = true
  try {
    const response = await importDataset(formData)
    const count = response?.data?.count ?? 0
    ElMessage.success(`成功导入 ${count} 条数据`)
    await refreshDatasetsAfterImport()
  } catch (/** @type {any} */ err) {
    const message = err?.response?.data?.error || '数据集导入失败，请稍后重试'
    importErrorMessage.value = message
    ElMessage.error(message)
  } finally {
    isImporting.value = false
    resetImportInput(event)
  }
}

const formatCategorySource = (row) => {
  const category = row?.category || '-'
  const source = row?.source || '-'
  return `${category} / ${source}`
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
</script>

<template>
  <div class="h-full flex flex-col space-y-6">
    <PageHeader title="数据集管理" description="管理后端返回的评论数据，并支持按记录导出">
      <template #actions>
        <div class="flex flex-wrap items-center gap-3">
          <input
            ref="fileInputRef"
            type="file"
            :accept="acceptTypes"
            class="hidden"
            @change="handleImportChange"
          />
          <template v-if="batchMode">
            <el-button class="!h-10 !px-4 !rounded-lg" @click="handleSelectAll">
              全选/取消
            </el-button>
            <el-button
              type="primary"
              class="!h-10 !px-4 !rounded-lg"
              :disabled="!selectedRows.length"
              @click="handleBatchExport"
            >
              <el-icon class="mr-1"><Download /></el-icon>
              导出{{ selectedRows.length ? ` (${selectedRows.length})` : '' }}
            </el-button>
            <el-button class="!h-10 !px-4 !rounded-lg" @click="handleCancelBatchMode">
              取消
            </el-button>
          </template>
          <template v-else>
            <el-button type="primary" class="!h-10 !px-4 !rounded-lg" @click="batchMode = true">
              <el-icon class="mr-1"><Download /></el-icon>
              批量导出
            </el-button>
            <el-button
              type="primary"
              class="!h-10 !px-4 !rounded-lg"
              :disabled="isImporting"
              @click="triggerImport"
            >
              <el-icon class="mr-1"><Plus /></el-icon>
              {{ isImporting ? '导入中...' : '导入数据集' }}
            </el-button>
          </template>
        </div>
      </template>
    </PageHeader>

    <div
      class="bg-white rounded-xl border border-slate-200 shadow-sm flex-1 flex flex-col overflow-hidden"
    >
      <div
        v-if="errorMessage"
        class="mx-6 mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        {{ errorMessage }}
      </div>
      <div
        v-if="importErrorMessage"
        class="mx-6 mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        {{ importErrorMessage }}
      </div>
      <div
        v-if="exportErrorMessage"
        class="mx-6 mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        {{ exportErrorMessage }}
      </div>

      <!-- Toolbar -->
      <div class="p-6 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
        <div class="text-sm text-slate-500">仅展示真实评论记录，不提供预览数据</div>
        <el-button :icon="Refresh" circle @click="fetchDatasets" />
      </div>

      <!-- Table Section -->
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
          <el-table-column
            v-if="batchMode"
            type="selection"
            width="50"
            align="center"
            :reserve-selection="true"
          />
          <el-table-column prop="id" label="编号" width="70" align="center" />

          <el-table-column label="评论内容" min-width="240" header-align="center">
            <template #default="scope">
              <div class="flex items-center gap-4 py-2">
                <div class="h-10 w-10 rounded-xl bg-amber-50 flex items-center justify-center">
                  <el-icon class="text-amber-600" :size="20"><Files /></el-icon>
                </div>
                <span class="font-bold text-slate-900 line-clamp-2">{{
                  scope.row.content || '-'
                }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="分类 / 来源" width="120" align="center">
            <template #default="scope">
              <span class="text-slate-500 text-sm">{{ formatCategorySource(scope.row) }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="comment_time" label="评论时间" width="140" align="center">
            <template #default="scope">
              <span class="text-slate-500 text-sm font-mono">
                {{ formatDateTime(scope.row.comment_time) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column prop="created_at" label="创建日期" width="140" align="center">
            <template #default="scope">
              <span class="text-slate-500 text-sm font-mono">
                {{ formatDateTime(scope.row.created_at) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="80" align="center">
            <template #default="scope">
              <el-button link type="primary" class="!font-bold" @click="handleExport(scope.row)">
                <el-icon class="mr-1"><Download /></el-icon>
                导出
              </el-button>
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
          @current-change="fetchDatasets"
        />
      </div>
    </div>
  </div>
</template>
