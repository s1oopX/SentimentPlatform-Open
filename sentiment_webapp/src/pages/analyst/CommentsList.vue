<script setup>
import { computed, onActivated, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAnalystComments, updateAnalystComment, deleteAnalystComment } from '@/api/analysis'
import { usePageSizeReset } from '@/composables/usePagination'
import { useRouteFilterSync } from '@/composables/useRouteFilterSync'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, StarFilled, Edit, Delete, Filter } from '@element-plus/icons-vue'
import { normalizeText, buildDateRangeParams } from '@/utils/filterUtils'

const route = useRoute()
const router = useRouter()

/**
 * @typedef {{
 *   id: number
 *   comment_content?: string
 *   sentiment?: number
 *   sentiment_display?: string
 *   confidence?: number
 *   analyst_note?: string
 *   is_priority?: boolean
 *   project_name?: string
 *   category?: string
 *   created_at?: string
 *   [key: string]: any
 * }} CommentRow
 */
/** @type {import('vue').Ref<CommentRow[]>} */ const tableData = ref([])
const total = ref(0)
/** @type {import('vue').Ref<string[]>} */ const categoryOptions = ref([])
/** @type {import('vue').Ref<number | null>} */ const editingId = ref(null)
/** @type {import('vue').Ref<number | null>} */ const savingId = ref(null)
/** @type {import('vue').Ref<number | null>} */ const deletingId = ref(null)
const editForm = reactive({
  analyst_note: '',
  is_priority: false,
})
const pagination = reactive({ page: 1, page_size: 15 })

const routeFilterKeys = [
  'keyword',
  'is_priority',
  'sentiment',
  'category',
  'start_date',
  'end_date',
]

const {
  filters,
  loading,
  errorMessage,
  applyFilters,
  fetchData: fetchComments,
} = useRouteFilterSync({
  router,
  route,
  filterKeys: routeFilterKeys,
  buildParams: (f) =>
    buildQueryParams({ ...f, page: pagination.page, page_size: pagination.page_size }),
  fetchFn: (params) => getAnalystComments(params),
  onFetched: (res) => {
    tableData.value = res.data.results || []
    total.value = res.data.count || tableData.value.length
    categoryOptions.value = Array.isArray(res.data.category_options)
      ? res.data.category_options
      : []
    if (editingId.value && !tableData.value.some((item) => item.id === editingId.value)) {
      editingId.value = null
    }
  },
})

// Bridge is_priority: filters store strings, template binds boolean
const priorityFilter = computed({
  get: () => (filters.is_priority === 'true' ? true : filters.is_priority === 'false' ? false : ''),
  set: (val) => {
    filters.is_priority = String(val)
  },
})

const buildQueryParams = (allParams) => {
  const params = { page: allParams.page, page_size: allParams.page_size }

  const keyword = normalizeText(allParams.keyword)
  if (keyword) params.keyword = keyword

  if (
    allParams.is_priority !== '' &&
    allParams.is_priority !== null &&
    allParams.is_priority !== undefined
  ) {
    params.is_priority = allParams.is_priority
  }

  const sentiment = normalizeText(allParams.sentiment)
  if (sentiment) params.sentiment = sentiment

  const category = normalizeText(allParams.category)
  if (category) params.category = category

  Object.assign(params, buildDateRangeParams(allParams))
  return params
}

const getSentimentTagType = (sentiment) => {
  const normalized = Number(sentiment)
  if (normalized === 1 || sentiment === 'positive') return 'success'
  if (normalized === -1 || sentiment === 'negative') return 'danger'
  return 'info'
}

const { handlePageSizeChange } = usePageSizeReset(pagination, fetchComments)

const emptyMessage = computed(() => errorMessage.value || '未发现符合筛选条件的记录')

const handleEdit = (row) => {
  if (savingId.value || deletingId.value) return
  editingId.value = row.id
  editForm.analyst_note = row.analyst_note || ''
  editForm.is_priority = row.is_priority || false
}

const handleSave = async (id) => {
  if (savingId.value) return
  savingId.value = id
  try {
    await updateAnalystComment(id, editForm)
    ElMessage.success('更新成功')
    editingId.value = null
    await fetchComments()
  } catch {
    // handled by interceptor
  } finally {
    if (savingId.value === id) {
      savingId.value = null
    }
  }
}

const handleDelete = async (id) => {
  if (deletingId.value) return
  try {
    await ElMessageBox.confirm('确定要删除这条分析结果吗？', '确认删除', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      roundButton: true,
    })
    deletingId.value = id
    await deleteAnalystComment(id)
    ElMessage.success('删除成功')

    const nextTotal = Math.max(total.value - 1, 0)
    const lastAvailablePage = Math.max(1, Math.ceil(nextTotal / pagination.page_size))
    if (pagination.page > lastAvailablePage) {
      pagination.page = lastAvailablePage
    }

    await fetchComments()
  } catch {
    return
  } finally {
    if (deletingId.value === id) {
      deletingId.value = null
    }
  }
}

onActivated(async () => {
  await fetchComments()
})
</script>

<template>
  <div class="h-full flex flex-col space-y-6">
    <div class="space-y-1">
      <h1 class="text-2xl font-bold text-slate-800">审核管理</h1>
      <p class="text-slate-500 text-sm">深度标注与专家审核工作站</p>
    </div>

    <div
      class="bg-white rounded-xl border border-slate-200 shadow-sm flex-1 flex flex-col overflow-hidden"
    >
      <!-- Toolbar/Filters -->
      <div
        class="grid grid-cols-2 items-end gap-4 border-b border-slate-100 bg-slate-50/50 p-6 md:grid-cols-4 xl:grid-cols-7"
      >
        <div class="space-y-1.5 col-span-2">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1"
            >内容检索</label
          >
          <el-input
            v-model="filters.keyword"
            placeholder="搜索关键词..."
            class="el-input-rounded"
            clearable
            @change="applyFilters"
          >
            <template #prefix
              ><el-icon class="text-slate-400"><Search /></el-icon
            ></template>
          </el-input>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1"
            >标记状态</label
          >
          <el-select
            v-model="priorityFilter"
            class="!w-full el-input-rounded"
            placeholder="全部"
            @change="applyFilters"
          >
            <el-option label="全部" value="" />
            <el-option label="重点关注" :value="true" />
            <el-option label="普通记录" :value="false" />
          </el-select>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1"
            >情感类别</label
          >
          <el-select
            v-model="filters.sentiment"
            class="!w-full el-input-rounded"
            placeholder="全部"
            @change="applyFilters"
          >
            <el-option label="全部" value="" />
            <el-option label="积极" value="1" />
            <el-option label="中性" value="0" />
            <el-option label="消极" value="-1" />
          </el-select>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1"
            >分类</label
          >
          <el-select
            v-model="filters.category"
            class="!w-full el-input-rounded"
            placeholder="全部分类"
            @change="applyFilters"
          >
            <el-option label="全部分类" value="" />
            <el-option
              v-for="category in categoryOptions"
              :key="category"
              :label="category"
              :value="category"
            />
          </el-select>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1"
            >开始日期</label
          >
          <input
            v-model="filters.start_date"
            type="date"
            class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-300"
            @change="applyFilters"
          />
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1"
            >结束日期</label
          >
          <input
            v-model="filters.end_date"
            type="date"
            class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-300"
            @change="applyFilters"
          />
        </div>
      </div>

      <!-- List -->
      <div class="flex-1 overflow-auto p-6">
        <div v-if="loading" class="flex items-center justify-center py-20">
          <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-primary"></div>
        </div>

        <div
          v-else-if="tableData.length === 0"
          class="flex flex-col items-center justify-center py-20 text-slate-400 border-2 border-dashed border-slate-100 rounded-xl"
        >
          <el-icon :size="48" class="mb-2 opacity-30"><Filter /></el-icon>
          <p>{{ emptyMessage }}</p>
        </div>

        <div v-else class="space-y-4">
          <div
            v-for="item in tableData"
            :key="item.id"
            class="group p-6 border border-slate-200 rounded-xl hover:border-indigo-200 hover:shadow-md transition-all duration-300 bg-white"
          >
            <!-- View Mode -->
            <div v-if="editingId !== item.id" class="flex items-start justify-between gap-6">
              <div class="flex-1 space-y-4">
                <div class="flex items-center gap-3">
                  <el-icon v-if="item.is_priority" class="text-amber-500 fill-amber-500" :size="20"
                    ><StarFilled
                  /></el-icon>
                  <p class="text-lg font-medium text-slate-900 leading-relaxed">
                    {{ item.comment_content }}
                  </p>
                </div>

                <div class="flex flex-wrap items-center gap-4 text-sm">
                  <el-tag
                    :type="getSentimentTagType(item.sentiment)"
                    effect="dark"
                    class="!px-3 !rounded-md"
                  >
                    {{ item.sentiment_display || item.sentiment }}
                  </el-tag>
                  <span class="text-slate-500 font-mono"
                    >置信度:
                    {{
                      item.confidence != null
                        ? `${(Number(item.confidence) * 100).toFixed(1)}%`
                        : '-'
                    }}</span
                  >
                  <span
                    v-if="item.category"
                    class="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs"
                    >分类: {{ item.category }}</span
                  >
                </div>

                <div
                  v-if="item.analyst_note"
                  class="p-3 bg-blue-50/50 border-l-4 border-blue-400 rounded-r-lg text-sm text-slate-700 italic"
                >
                  "{{ item.analyst_note }}"
                </div>
              </div>

              <div class="flex gap-2 transition-opacity">
                <el-button
                  :icon="Edit"
                  circle
                  :disabled="Boolean(savingId || deletingId)"
                  @click="handleEdit(item)"
                />
                <el-button
                  :icon="Delete"
                  type="danger"
                  plain
                  circle
                  :loading="deletingId === item.id"
                  :disabled="Boolean(savingId)"
                  @click="handleDelete(item.id)"
                />
              </div>
            </div>

            <!-- Edit Mode -->
            <div v-else class="space-y-6 animate-in fade-in duration-200">
              <div class="space-y-2">
                <label class="text-sm font-bold text-slate-900">专家备注</label>
                <el-input
                  v-model="editForm.analyst_note"
                  type="textarea"
                  :rows="3"
                  placeholder="添加对该记录的深度见解或修正意见..."
                  class="el-textarea-rounded"
                />
              </div>

              <div class="flex items-center gap-4">
                <el-checkbox
                  v-model="editForm.is_priority"
                  label="设为重点关注"
                  border
                  class="!rounded-xl"
                />
                <div class="flex-1 flex justify-end gap-3">
                  <el-button
                    class="!rounded-xl"
                    :disabled="savingId === item.id"
                    @click="editingId = null"
                    >取消</el-button
                  >
                  <el-button
                    type="primary"
                    class="!rounded-xl px-8"
                    :loading="savingId === item.id"
                    :disabled="savingId === item.id"
                    @click="handleSave(item.id)"
                    >保存更新</el-button
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div class="p-4 border-t border-slate-100 bg-white flex justify-end">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          layout="total, prev, pager, next"
          :total="total"
          @current-change="fetchComments"
          @size-change="handlePageSizeChange"
        />
      </div>
    </div>
  </div>
</template>
