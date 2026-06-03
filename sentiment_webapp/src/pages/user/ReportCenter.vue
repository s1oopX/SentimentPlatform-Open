<script setup>
import { Document, Download, Plus, Refresh, Calendar } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useReportCenter } from '@/composables/useReportCenter'
import { formatDateTimeText } from '@/utils/dateTime'

const authStore = useAuthStore()
const {
  loading,
  generating,
  showGenerateForm,
  showPrefillNotice,
  reports,
  total,
  errorMessage,
  queryParams,
  generateForm,
  canUseScopedReportFilters,
  fetchReports,
  handlePageSizeChange,
  handleGenerate,
  handleDownload,
  toggleGenerateForm,
  getReportTagType,
  getVisibleReportStatusDisplay,
  getReportFailureReason,
  isReportInProgress,
} = useReportCenter({ authStore })
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div class="space-y-2">
        <h1 class="text-3xl font-bold text-slate-900">报表管理</h1>
        <p class="text-slate-600 text-lg">生成和下载分析报表</p>
      </div>
      <el-button
        type="primary"
        class="!h-11 !px-6 !text-base !font-semibold !rounded-xl shadow-md"
        @click="toggleGenerateForm"
      >
        <el-icon class="mr-2"><Plus /></el-icon>
        生成报表
      </el-button>
    </div>

    <el-alert
      v-if="showPrefillNotice"
      title="已根据当前分析结果预填筛选条件"
      type="info"
      :closable="false"
      show-icon
    />

    <!-- 生成报表表单 -->
    <div
      v-if="showGenerateForm"
      class="bg-white rounded-xl border border-slate-200 shadow-lg animate-in fade-in slide-in-from-top-4 duration-300"
    >
      <div class="px-6 py-4 border-b border-slate-100">
        <h3 class="font-bold text-lg text-slate-900">生成新报表</h3>
        <p class="text-sm text-slate-500">配置参数并开始分析任务</p>
      </div>
      <div class="p-6">
        <el-form
          :model="generateForm"
          label-position="top"
          class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4"
        >
          <el-form-item label="报表周期">
            <el-select
              v-model="generateForm.report_type"
              class="w-full !rounded-lg h-11 el-input-rounded"
            >
              <el-option label="日报" value="daily" />
              <el-option label="周报" value="weekly" />
              <el-option label="月报" value="monthly" />
            </el-select>
          </el-form-item>

          <el-form-item label="导出格式">
            <el-select v-model="generateForm.report_format" class="w-full h-11 el-input-rounded">
              <el-option label="PDF 格式（推荐可视化）" value="pdf" />
              <el-option label="Excel 格式（适合数据处理）" value="excel" />
              <el-option label="CSV 格式（纯文本）" value="csv" />
            </el-select>
          </el-form-item>

          <el-form-item label="核心日期">
            <el-date-picker
              v-model="generateForm.start_date"
              type="date"
              placeholder="选择统计日期"
              class="w-full !h-11 !rounded-xl"
              value-format="YYYY-MM-DD"
            />
          </el-form-item>

          <el-form-item v-if="canUseScopedReportFilters" label="分类筛选">
            <el-input
              v-model="generateForm.category"
              placeholder="填写分类名可进一步筛选，留空=全部"
              clearable
              class="h-11 el-input-rounded"
            />
          </el-form-item>
        </el-form>
        <div class="mt-6 pt-6 border-t border-slate-100 flex justify-end gap-3">
          <el-button class="!rounded-xl" @click="showGenerateForm = false">取消</el-button>
          <el-button
            type="primary"
            :loading="generating"
            class="!rounded-xl px-8"
            @click="handleGenerate"
            >开始生成</el-button
          >
        </div>
      </div>
    </div>

    <!-- 报表列表 -->
    <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div class="px-6 py-4 border-b border-slate-100 flex justify-between items-center">
        <h3 class="font-bold text-slate-900">已生成列表</h3>
        <el-button :icon="Refresh" circle size="small" @click="fetchReports" />
      </div>

      <div class="p-6">
        <div v-if="loading" class="flex flex-col items-center justify-center py-20 gap-4">
          <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-primary"></div>
          <p class="text-slate-500">正在获取报表列表...</p>
        </div>

        <div
          v-else-if="errorMessage"
          class="flex flex-col items-center justify-center py-20 gap-4 text-center"
        >
          <div
            class="flex items-start justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3"
          >
            <div class="flex-1 text-sm font-medium text-red-700">
              {{ errorMessage }}
            </div>
            <el-button size="small" :icon="Refresh" :loading="loading" @click="fetchReports">
              重试
            </el-button>
          </div>
          <p class="text-sm text-slate-500">请检查网络或稍后重试，然后手动刷新列表。</p>
        </div>

        <div
          v-else-if="!loading && reports.length === 0"
          class="flex flex-col items-center justify-center py-20 text-slate-400"
        >
          <el-icon :size="64" class="mb-4 opacity-20"><Document /></el-icon>
          <p>暂无任何报表，点击右上角开始生成</p>
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="report in reports"
            :key="report.id"
            class="group flex flex-col gap-4 p-5 border border-slate-200 rounded-xl hover:border-primary/50 hover:bg-slate-50 transition-all duration-200 lg:flex-row lg:items-center lg:justify-between"
          >
            <div class="flex items-center gap-4">
              <div
                class="h-12 w-12 bg-slate-100 rounded-xl flex items-center justify-center group-hover:bg-primary/10 transition-colors"
              >
                <el-icon
                  class="text-slate-600 group-hover:text-primary transition-colors"
                  :size="24"
                  ><Document
                /></el-icon>
              </div>
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <span class="font-bold text-slate-900"
                    >{{ report.report_type_display }} - {{ report.report_format_display }}</span
                  >
                  <el-tag :type="getReportTagType(report.status)" size="small" effect="light">
                    {{ getVisibleReportStatusDisplay(report) }}
                  </el-tag>
                </div>
                <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
                  <span class="flex items-center gap-1"
                    ><el-icon><Calendar /></el-icon>{{ report.start_date }} 至
                    {{ report.end_date }}</span
                  >
                  <span>文件大小: {{ report.file_size_mb?.toFixed(2) || '0.00' }} MB</span>
                  <span>时间: {{ formatDateTimeText(report.created_at) }}</span>
                </div>
                <div v-if="getReportFailureReason(report)" class="text-sm text-red-500">
                  {{ getReportFailureReason(report) }}
                </div>
              </div>
            </div>

            <div v-if="report.status === 'completed'" class="flex gap-2">
              <el-button type="primary" plain class="!rounded-lg" @click="handleDownload(report)">
                <el-icon class="mr-2"><Download /></el-icon>
                下载
              </el-button>
            </div>
            <div
              v-else-if="isReportInProgress(report.status)"
              class="flex items-center gap-2 text-sm text-slate-500"
            >
              <div class="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
              文件生成中，列表将自动刷新
            </div>
            <div v-else class="text-sm text-red-500">生成失败，请重新提交</div>
          </div>
        </div>

        <!-- Pagination (simplified for this view) -->
        <div
          v-if="!errorMessage"
          class="mt-8 pt-6 border-t border-slate-100 flex flex-col gap-3 px-2 sm:flex-row sm:items-center sm:justify-between"
        >
          <span class="text-sm text-slate-500">共 {{ total }} 个生成的报表文件</span>
          <el-pagination
            v-model:current-page="queryParams.page"
            v-model:page-size="queryParams.page_size"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            :total="total"
            @size-change="handlePageSizeChange"
            @current-change="fetchReports"
          />
        </div>
      </div>
    </div>
  </div>
</template>
