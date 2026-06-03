<script setup>
import { computed, ref, watch } from 'vue'
import { Refresh, Plus, Delete } from '@element-plus/icons-vue'
import { useTrainingCenter } from '@/composables/useTrainingCenter'
import ErrorRetryAlert from '@/components/ErrorRetryAlert.vue'
import HeatmapMatrix from '@/components/HeatmapMatrix.vue'
import MetricBarChart from '@/components/MetricBarChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import TrendChart from '@/components/TrendChart.vue'
import {
  formatCandidateModel,
  formatModelFamily,
  formatSearchType,
} from '@/composables/trainingConstants'

const {
  loading,
  submitting,
  errorMessage,
  dashboard,
  comparison,
  records,
  recordsTotal,
  detail,
  logDialogVisible,
  logLoading,
  logError,
  logContent,
  actionLoading,
  recordsQuery,
  form,
  taskTypeOptions,
  modelFamilyOptions,
  searchTypeOptions,
  candidateModelOptions,
  showModelFamily,
  showCandidateModels,
  showSearchType,
  showUseGpu,
  metricCards,
  lossCurveDates,
  lossCurveSeries,
  classicalCvMetricItems,
  canRetryCurrentDetail,
  canRetryPostRunCurrentDetail,
  canActivateCurrentDetail,
  canDeleteCurrentDetail,
  hasCurrentDetailLogAvailable,
  loadDetail,
  openLogDialog,
  handleCreate,
  handleRetry,
  handleRetryPostRun,
  handleActivate,
  handleDelete,
  handleDownloadLog,
  handleRecordPageChange,
  handleRecordPageSizeChange,
  formatSourceType,
  formatExecutionMode,
  formatStatus,
  formatSourceMeta,
  formatPostRunStatus,
  formatRuntimeType,
  formatMaybe,
  formatMetric,
  loadTrainingCenter,
} = useTrainingCenter()

const activeTab = ref('train')

const localDatasetOptions = [
  {
    label: 'chinese-news-sentiment-c3-ds',
    value: 'chinese-news-sentiment-c3-ds',
    note: '本地原始数据集，适合自动 7:1:2 分层划分',
    path: 'sentiment_server/ml_assets/data/chinese-news-sentiment-c3-ds',
    splitStrategies: ['auto_split'],
  },
]

const filteredLocalDatasetOptions = computed(() =>
  localDatasetOptions.filter((option) => option.splitStrategies.includes(form.split_strategy))
)

const selectedLocalDataset = computed(
  () =>
    localDatasetOptions.find((option) => option.value === form.dataset_ref) ||
    filteredLocalDatasetOptions.value[0] ||
    localDatasetOptions[0]
)

const currentTaskType = computed(
  () => taskTypeOptions.find((option) => option.value === form.task_type) || taskTypeOptions[0]
)

const visibleSearchTypeOptions = computed(() =>
  searchTypeOptions.filter(
    (option) => !option.classicalOnly || form.task_type === 'classical_compare'
  )
)

const currentModelSelection = computed(() => {
  if (showModelFamily.value)
    return form.model_family ? formatModelFamily(form.model_family) : '请选择模型族'
  if (showCandidateModels.value)
    return form.candidate_models.length
      ? form.candidate_models.map((item) => formatCandidateModel(item)).join(' / ')
      : '请选择候选模型'
  return '--'
})

const currentTaskNote = computed(() => {
  const notes = {
    transformer_train: '训练单个 Transformer 模型，适合固定模型族后直接产出线上候选模型。',
    transformer_search: '搜索 Transformer 超参数，适合 BERT / RoBERTa 的系统化调优。',
    classical_compare: '比较传统机器学习模型，适合快速建立可解释基线。',
    neural_baseline_train:
      '训练 TextCNN / BiLSTM 神经网络基线，适合和传统模型、Transformer 横向对比。',
  }
  return notes[form.task_type] || '选择项目支持的训练任务并提交到训练队列。'
})

const selectedTaskMetricCards = computed(() => [
  { label: '当前任务', value: currentTaskType.value.label },
  { label: '模型选择', value: currentModelSelection.value },
  { label: '目标 Macro-F1', value: formatMetric(form.target_macro_f1) },
  { label: '切分策略', value: '自动分层划分' },
])

const trainingParameterCards = computed(() => [
  { label: '任务类型', value: currentTaskType.value.label, note: currentTaskNote.value },
  {
    label: '模型范围',
    value: currentModelSelection.value,
    note: showModelFamily.value ? 'Transformer 模型族' : '候选模型可多选并生成对比结果',
  },
  {
    label: '本地数据集名称',
    value: selectedLocalDataset.value.label,
    note: `本地目录：${selectedLocalDataset.value.path}`,
  },
  { label: '切分策略', value: 'auto_split', note: selectedLocalDataset.value.note },
  {
    label: '搜索方式',
    value: showSearchType.value ? formatSearchType(form.search_type) : '不使用搜索',
    note: showSearchType.value ? '用于超参数搜索或传统模型比较' : '当前任务按固定训练配置执行',
  },
  {
    label: 'max_length',
    value: String(form.max_length),
    note: '文本截断或补齐后的最大 token 长度',
  },
  {
    label: 'max_trials / cv_folds',
    value: `${form.max_trials} / ${form.cv_folds}`,
    note: '搜索次数与交叉验证折数',
  },
  {
    label: '执行资源',
    value: showUseGpu.value ? (form.use_gpu ? 'GPU' : 'CPU') : '按任务默认',
    note: showUseGpu.value ? '神经网络基线可切换 PyTorch 训练设备' : '由训练任务类型决定执行环境',
  },
])

const trainingCommandLines = computed(() => {
  const lines = [
    'python ml_assets/scripts/data/split_dataset.py --input-dir <dataset> --output-dir <auto_split>',
  ]
  if (form.task_type === 'transformer_train') {
    lines.push(
      'python ml_assets/scripts/training/run_experiment.py transformer-train',
      `--model-name-or-path ${form.model_family === 'roberta' ? 'hfl/chinese-roberta-wwm-ext' : 'bert-base-chinese'}`,
      `--max-length ${form.max_length} --target-macro-f1 ${form.target_macro_f1}`
    )
  } else if (form.task_type === 'transformer_search') {
    lines.push(
      'python ml_assets/scripts/training/search_transformer.py',
      `--model-name-or-path ${form.model_family === 'roberta' ? 'hfl/chinese-roberta-wwm-ext' : 'bert-base-chinese'}`,
      `--search-type ${form.search_type} --max-trials ${form.max_trials} --cv-folds ${form.cv_folds}`
    )
  } else if (form.task_type === 'classical_compare') {
    lines.push(
      'python ml_assets/scripts/training/compare_models.py',
      `--models ${form.candidate_models.join(' ') || '<candidate_models>'}`,
      `--search-type ${form.search_type} --max-trials ${form.max_trials} --cv-folds ${form.cv_folds}`
    )
  } else {
    lines.push(
      'python ml_assets/scripts/training/train_neural_baselines.py',
      `--models ${form.candidate_models.join(' ') || '<candidate_models>'}`,
      `--device ${form.use_gpu ? 'cuda' : 'cpu'}`
    )
  }
  return lines
})

const successfulRecords = computed(() =>
  (records.value || []).filter((record) => record.status === 'succeeded')
)

const recentSuccessfulRecords = computed(() => {
  const recent = dashboard.value?.recent_records || []
  return recent.filter((record) => record.status === 'succeeded').slice(0, 4)
})

const hasDisplayValue = (value) => value !== null && value !== undefined && value !== ''

const hasRuntimeModels = computed(
  () => (detail.value?.runtime_compatibility?.registered_models || []).length > 0
)

const hasConfusionMatrix = computed(() => {
  const matrix = detail.value?.confusion_matrix
  return Array.isArray(matrix) && matrix.length > 0 && matrix.every((row) => row?.length > 0)
})

const confusionMatrixLabels = computed(() => {
  const labelMap = {
    negative: '消极',
    neutral: '中性',
    positive: '积极',
  }
  const rawLabels = detail.value?.label_order?.length
    ? detail.value.label_order
    : ['negative', 'neutral', 'positive']
  return rawLabels.map((label) => labelMap[label] || label)
})

const hasLeaderboardPreview = computed(() => (detail.value?.leaderboard_preview || []).length > 0)

const hasArtifactSummaries = computed(() => (detail.value?.artifact_summaries || []).length > 0)

watch(
  () => form.split_strategy,
  () => {
    if (form.split_strategy !== 'auto_split') {
      form.split_strategy = 'auto_split'
      return
    }
    const nextDataset = filteredLocalDatasetOptions.value[0]
    if (nextDataset && form.dataset_ref !== nextDataset.value) {
      form.dataset_ref = nextDataset.value
    }
  },
  { immediate: true }
)

const modelArchitectures = [
  {
    key: 'classical',
    label: '传统机器学习',
    accentClass: 'border-blue-200 bg-blue-50/60',
    badgeClass: 'bg-blue-100 text-blue-700',
    models: ['逻辑回归', 'SVM', '随机森林'],
    taskTypes: ['classical_compare'],
    note: '基于 sklearn，支持 GridSearchCV / RandomizedSearchCV 与 StratifiedKFold 交叉验证',
  },
  {
    key: 'neural',
    label: '神经网络基线',
    accentClass: 'border-emerald-200 bg-emerald-50/60',
    badgeClass: 'bg-emerald-100 text-emerald-700',
    models: ['TextCNN', 'BiLSTM'],
    taskTypes: ['neural_baseline_train'],
    note: '基于 PyTorch，含 Embedding + 多卷积核 / 双向 LSTM，支持早停',
  },
  {
    key: 'transformer',
    label: 'Transformer 预训练模型',
    accentClass: 'border-violet-200 bg-violet-50/60',
    badgeClass: 'bg-violet-100 text-violet-700',
    models: ['BERT', 'RoBERTa'],
    taskTypes: ['transformer_train', 'transformer_search'],
    note: '基于 Transformers Trainer，搜索 learning_rate / batch_size / weight_decay',
  },
]

const formatAnalysisKey = (key) => {
  const labels = {
    positive: '积极',
    neutral: '中性',
    negative: '消极',
    train: '训练集',
    eval: '验证集',
    test: '测试集',
    missing_text: '缺失文本',
    duplicate_text: '重复文本',
    short_text: '过短文本',
    cleaned_rows: '清洗后行数',
    removed_rows: '移除行数',
  }
  return labels[key] || key
}

const analysisEntries = (value) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return []
  return Object.entries(value).filter(([, item]) => item !== null && item !== undefined)
}

const formatAnalysisValue = (value) => {
  if (value && typeof value === 'object') {
    return JSON.stringify(value)
  }
  return formatMaybe(value)
}

const openDetail = async (recordId) => {
  activeTab.value = 'detail'
  await loadDetail(recordId)
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="训练中心" description="管理员训练配置、评估对比和实验详情展示">
      <template #actions>
        <el-button type="primary" class="!h-10 !px-5 !rounded-lg" @click="activeTab = 'train'">
          <el-icon class="mr-1"><Plus /></el-icon>
          创建训练任务
        </el-button>
      </template>
    </PageHeader>

    <ErrorRetryAlert :message="errorMessage" :on-retry="loadTrainingCenter" :loading="loading" />

    <div class="grid grid-cols-1 gap-6 md:grid-cols-3">
      <StatCard
        v-for="card in metricCards"
        :key="card.label"
        :title="card.label"
        :value="card.value"
      />
    </div>

    <el-tabs v-model="activeTab" v-loading="loading">
      <el-tab-pane label="模型训练" name="train">
        <div class="space-y-6">
          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div class="text-sm font-semibold text-sky-700">Model Training Workspace</div>
                <h2 class="mt-1 text-xl font-semibold text-slate-900">项目通用模型训练配置</h2>
                <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                  统一提交
                  Transformer、传统机器学习和神经网络基线训练任务，并查看当前选择的训练参数。
                </p>
              </div>
              <el-tag type="success" effect="light" size="large">
                {{ currentTaskType.label }}
              </el-tag>
            </div>

            <div class="mt-5 grid grid-cols-1 gap-4 md:grid-cols-4">
              <div
                v-for="metric in selectedTaskMetricCards"
                :key="metric.label"
                class="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3"
              >
                <div class="text-xs font-medium text-slate-500">{{ metric.label }}</div>
                <div class="mt-2 truncate text-2xl font-semibold text-slate-900">
                  {{ metric.value }}
                </div>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div class="flex items-center justify-between gap-3">
                <h2 class="text-lg font-semibold text-slate-900">训练参数摘要</h2>
                <span class="text-xs text-slate-400">随右侧表单实时更新</span>
              </div>
              <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div
                  v-for="item in trainingParameterCards"
                  :key="item.label"
                  class="rounded-lg border border-slate-100 px-4 py-3"
                >
                  <div class="text-xs font-semibold uppercase text-slate-400">
                    {{ item.label }}
                  </div>
                  <div class="mt-1 break-words text-sm font-semibold text-slate-900">
                    {{ item.value }}
                  </div>
                  <div class="mt-1 break-all text-xs leading-5 text-slate-500">
                    {{ item.note }}
                  </div>
                </div>
              </div>

              <div class="mt-5 rounded-lg border border-slate-200 bg-slate-950 p-4">
                <div class="mb-2 text-xs font-semibold text-slate-300">终端训练命令要点</div>
                <pre class="overflow-auto text-xs leading-6 text-slate-100 whitespace-pre-wrap">{{
                  trainingCommandLines.join(' \\\n  ')
                }}</pre>
              </div>
            </div>

            <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 class="mb-4 text-lg font-semibold text-slate-900">提交模型训练任务</h2>
              <el-form :model="form" label-position="top">
                <el-form-item label="名称">
                  <el-input v-model="form.name" />
                </el-form-item>
                <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <el-form-item label="任务类型">
                    <el-select v-model="form.task_type">
                      <el-option
                        v-for="option in taskTypeOptions"
                        :key="option.value"
                        :label="option.label"
                        :value="option.value"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item v-if="showModelFamily" label="模型族">
                    <el-select v-model="form.model_family">
                      <el-option
                        v-for="option in modelFamilyOptions"
                        :key="option.value"
                        :label="option.label"
                        :value="option.value"
                      />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item v-if="showCandidateModels" label="候选模型">
                  <el-select v-model="form.candidate_models" multiple>
                    <el-option
                      v-for="option in candidateModelOptions"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
                <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <el-form-item label="本地数据集名称">
                    <el-select v-model="form.dataset_ref">
                      <el-option
                        v-for="option in filteredLocalDatasetOptions"
                        :key="option.value"
                        :label="option.label"
                        :value="option.value"
                      >
                        <div class="flex flex-col leading-5">
                          <span>{{ option.label }}</span>
                          <span class="text-xs text-slate-400">{{ option.note }}</span>
                        </div>
                      </el-option>
                    </el-select>
                    <div class="mt-1 text-xs leading-5 text-slate-400">
                      {{ selectedLocalDataset.note }}；目录：{{ selectedLocalDataset.path }}
                    </div>
                  </el-form-item>
                  <el-form-item label="切分策略">
                    <el-select v-model="form.split_strategy" disabled>
                      <el-option label="自动 7:1:2 分层划分" value="auto_split" />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item v-if="showSearchType" label="搜索方式">
                  <el-select v-model="form.search_type">
                    <el-option
                      v-for="option in visibleSearchTypeOptions"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
                <el-divider content-position="left">高级参数</el-divider>
                <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <el-form-item label="目标 Macro-F1">
                    <el-input-number
                      v-model="form.target_macro_f1"
                      :min="0.01"
                      :max="1"
                      :step="0.01"
                    />
                  </el-form-item>
                  <el-form-item label="最大文本长度">
                    <el-input-number v-model="form.max_length" :min="8" :max="4096" :step="8" />
                  </el-form-item>
                  <el-form-item label="最大搜索次数">
                    <el-input-number v-model="form.max_trials" :min="1" :max="200" />
                  </el-form-item>
                  <el-form-item label="交叉验证折数">
                    <el-input-number v-model="form.cv_folds" :min="2" :max="20" />
                  </el-form-item>
                </div>
                <el-form-item v-if="showUseGpu" label="PyTorch 使用 GPU">
                  <el-switch v-model="form.use_gpu" />
                </el-form-item>
                <el-button type="primary" :loading="submitting" @click="handleCreate">
                  提交训练任务
                </el-button>
              </el-form>
            </div>
          </div>

          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="flex items-center justify-between gap-3">
              <h2 class="text-lg font-semibold text-slate-900">最近成功训练</h2>
              <el-button text type="primary" @click="activeTab = 'records'">查看完整记录</el-button>
            </div>
            <div
              v-if="recentSuccessfulRecords.length"
              class="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2"
            >
              <button
                v-for="record in recentSuccessfulRecords"
                :key="record.record_id"
                type="button"
                class="block w-full rounded-lg border border-slate-100 px-4 py-3 text-left text-sm transition hover:border-sky-200"
                @click="openDetail(record.record_id)"
              >
                <div class="font-semibold text-slate-900">{{ record.title }}</div>
                <div class="mt-2 text-slate-500">{{ formatSourceMeta(record) }}</div>
              </button>
            </div>
            <div v-else class="mt-4 text-sm text-slate-400">暂无成功训练记录</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="总览" name="overview">
        <div class="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-lg font-semibold text-slate-900">系统支持的模型架构</h2>
            <span class="text-xs text-slate-400"
              >传统机器学习、神经网络与 Transformer 训练覆盖</span
            >
          </div>
          <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div
              v-for="arch in modelArchitectures"
              :key="arch.key"
              :class="[
                'rounded-xl border px-4 py-4 transition-shadow hover:shadow-md',
                arch.accentClass,
              ]"
            >
              <div class="text-sm font-semibold text-slate-700">{{ arch.label }}</div>
              <div class="mt-3 flex flex-wrap gap-2">
                <span
                  v-for="model in arch.models"
                  :key="model"
                  :class="['rounded-md px-2 py-0.5 text-xs font-semibold', arch.badgeClass]"
                >
                  {{ model }}
                </span>
              </div>
              <div class="mt-3 text-xs text-slate-500 leading-5">
                <div class="flex flex-wrap items-center gap-1">
                  <span class="text-slate-400">训练任务：</span>
                  <code
                    v-for="taskType in arch.taskTypes"
                    :key="taskType"
                    class="rounded bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-600"
                    >{{ taskType }}</code
                  >
                </div>
                <div class="mt-2 text-slate-500">{{ arch.note }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 class="mb-4 text-lg font-semibold text-slate-900">最近记录</h2>
            <div v-if="dashboard?.recent_records?.length" class="space-y-3">
              <button
                v-for="record in dashboard.recent_records"
                :key="record.record_id"
                type="button"
                class="block w-full rounded-xl border border-slate-100 px-4 py-3 text-left text-sm transition hover:border-sky-200"
                @click="openDetail(record.record_id)"
              >
                <div class="font-semibold text-slate-900">{{ record.title }}</div>
                <div class="mt-2 text-slate-500">
                  {{ formatSourceMeta(record) }}
                </div>
                <div v-if="record.note" class="mt-2 text-xs text-amber-600">
                  {{ record.note }}
                </div>
              </button>
            </div>
            <div v-else class="text-sm text-slate-400">暂无训练记录</div>
          </div>

          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 class="mb-4 text-lg font-semibold text-slate-900">最佳记录</h2>
            <div v-if="dashboard?.best_records?.length" class="space-y-3">
              <button
                v-for="record in dashboard.best_records"
                :key="record.record_id"
                type="button"
                class="block w-full rounded-xl border border-slate-100 px-4 py-3 text-left text-sm transition hover:border-sky-200"
                @click="openDetail(record.record_id)"
              >
                <div class="font-semibold text-slate-900">{{ record.title }}</div>
                <div class="mt-2 text-slate-500">
                  宏平均 F1 {{ formatMetric(record.metric_highlights?.macro_f1) }}
                </div>
                <div v-if="record.note" class="mt-2 text-xs text-amber-600">
                  {{ record.note }}
                </div>
              </button>
            </div>
            <div v-else class="text-sm text-slate-400">暂无最佳记录</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="对比" name="comparison">
        <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <MetricBarChart
            :items="comparison"
            label-key="subject_name"
            value-key="macro_f1"
            title="宏平均 F1 对比"
            empty-text="暂无对比数据"
          />
          <MetricBarChart
            :items="comparison"
            label-key="subject_name"
            value-key="accuracy"
            title="准确率对比"
            empty-text="暂无对比数据"
          />
        </div>
        <div class="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">详细指标</h2>
          <div class="mb-4 text-sm text-slate-500">
            当前对比视图仅展示最近 50 条成功训练任务，避免历史全量数据拖慢页面加载。
          </div>
          <el-table :data="comparison">
            <el-table-column prop="subject_name" label="候选项" />
            <el-table-column label="宏平均 F1">
              <template #default="scope">{{ formatMetric(scope.row.macro_f1) }}</template>
            </el-table-column>
            <el-table-column label="准确率">
              <template #default="scope">{{ formatMetric(scope.row.accuracy) }}</template>
            </el-table-column>
            <el-table-column label="消极召回率">
              <template #default="scope">{{ formatMetric(scope.row.negative_recall) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="记录" name="records">
        <div class="space-y-6">
          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div class="flex items-center justify-between gap-3">
              <h2 class="text-lg font-semibold text-slate-900">成功训练记录</h2>
              <span class="text-xs text-slate-400">仅展示成功训练记录</span>
            </div>
            <div v-if="successfulRecords.length" class="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
              <button
                v-for="record in successfulRecords"
                :key="record.record_id"
                type="button"
                class="block w-full rounded-lg border border-slate-100 px-4 py-3 text-left text-sm transition hover:border-sky-200"
                @click="openDetail(record.record_id)"
              >
                <div class="font-semibold text-slate-900">{{ record.title }}</div>
                <div class="mt-2 text-slate-500">
                  {{ formatSourceMeta(record) }}
                </div>
              </button>
            </div>
            <div v-else class="mt-4 text-sm text-slate-400">暂无成功训练记录</div>
          </div>

          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 class="mb-4 text-lg font-semibold text-slate-900">全部训练记录</h2>
            <div v-if="records.length" class="space-y-3">
              <button
                v-for="record in records"
                :key="record.record_id"
                type="button"
                class="block w-full rounded-xl border border-slate-100 px-4 py-3 text-left text-sm transition hover:border-sky-200"
                @click="openDetail(record.record_id)"
              >
                <div class="font-semibold text-slate-900">{{ record.title }}</div>
                <div class="mt-2 text-slate-500">
                  {{ formatSourceMeta(record) }}
                </div>
                <div v-if="record.note" class="mt-2 text-xs text-amber-600">
                  {{ record.note }}
                </div>
              </button>
              <el-pagination
                :total="recordsTotal"
                :current-page="recordsQuery.page"
                :page-size="recordsQuery.pageSize"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next"
                @current-change="handleRecordPageChange"
                @size-change="handleRecordPageSizeChange"
              />
            </div>
            <div v-else class="text-sm text-slate-400">暂无训练记录</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="详情" name="detail">
        <div v-if="detail" class="space-y-6">
          <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 class="text-lg font-semibold text-slate-900">{{ detail.title }}</h2>
            <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3 text-sm">
              <div class="rounded-xl bg-slate-50 px-4 py-3">记录编号: {{ detail.record_id }}</div>
              <div class="rounded-xl bg-slate-50 px-4 py-3">
                来源类型: {{ formatSourceType(detail.source_type) }}
              </div>
              <div class="rounded-xl bg-slate-50 px-4 py-3">
                执行模式: {{ formatExecutionMode(detail.execution_mode) }}
              </div>
              <div class="rounded-xl bg-slate-50 px-4 py-3">
                状态: {{ formatStatus(detail.status) }}
              </div>
              <div v-if="detail.post_run_status" class="rounded-xl bg-slate-50 px-4 py-3">
                后处理状态: {{ formatPostRunStatus(detail.post_run_status) }}
              </div>
            </div>
            <div
              v-if="detail.note"
              class="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700"
            >
              {{ detail.note }}
            </div>
            <div
              v-if="detail.quality_warnings?.length"
              class="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3"
            >
              <div class="text-sm font-semibold text-amber-800">质量告警</div>
              <div class="mt-2 space-y-1 text-sm text-amber-700">
                <div v-for="warning in detail.quality_warnings" :key="warning">
                  {{ warning }}
                </div>
              </div>
            </div>
            <div
              v-if="
                canRetryCurrentDetail ||
                canRetryPostRunCurrentDetail ||
                canActivateCurrentDetail ||
                hasCurrentDetailLogAvailable
              "
              class="mt-4 flex flex-wrap gap-3"
            >
              <el-button
                v-if="canRetryCurrentDetail"
                :loading="actionLoading.retry"
                :disabled="actionLoading.retry"
                @click="handleRetry(detail.record_id)"
                >重试任务</el-button
              >
              <el-button
                v-if="canRetryPostRunCurrentDetail"
                :loading="actionLoading.retryPostRun"
                :disabled="actionLoading.retryPostRun"
                @click="handleRetryPostRun(detail.record_id)"
                >重试后处理</el-button
              >
              <el-button
                v-if="canActivateCurrentDetail"
                type="primary"
                :loading="actionLoading.activate"
                :disabled="actionLoading.activate"
                @click="handleActivate(detail.record_id)"
                >激活模型</el-button
              >
              <el-button
                v-if="hasCurrentDetailLogAvailable"
                @click="openLogDialog(detail.record_id)"
                >查看日志</el-button
              >
              <el-button
                v-if="hasCurrentDetailLogAvailable"
                @click="handleDownloadLog(detail.record_id)"
                >下载日志</el-button
              >
              <el-button
                v-if="canDeleteCurrentDetail"
                :loading="actionLoading.delete"
                :disabled="actionLoading.delete"
                type="danger"
                plain
                @click="handleDelete(detail)"
              >
                <el-icon class="mr-1"><Delete /></el-icon>
                删除记录
              </el-button>
            </div>
          </div>

          <div class="grid grid-cols-1 items-start gap-6 xl:grid-cols-2">
            <div class="space-y-6">
              <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h2 class="mb-4 text-lg font-semibold text-slate-900">数据集分析</h2>
                <div class="grid grid-cols-1 gap-3 text-sm text-slate-600 md:grid-cols-2">
                  <div class="rounded-xl bg-slate-50 px-4 py-3">
                    数据集: {{ formatMaybe(detail.dataset_analysis?.dataset_ref) }}
                  </div>
                  <div class="rounded-xl bg-slate-50 px-4 py-3">
                    切分策略: {{ formatMaybe(detail.dataset_analysis?.split_strategy) }}
                  </div>
                  <div
                    v-if="hasDisplayValue(detail.dataset_analysis?.rows?.train)"
                    class="rounded-xl bg-slate-50 px-4 py-3"
                  >
                    训练行数: {{ formatMaybe(detail.dataset_analysis?.rows?.train) }}
                  </div>
                  <div
                    v-if="hasDisplayValue(detail.dataset_analysis?.rows?.eval)"
                    class="rounded-xl bg-slate-50 px-4 py-3"
                  >
                    验证行数: {{ formatMaybe(detail.dataset_analysis?.rows?.eval) }}
                  </div>
                  <div
                    v-if="hasDisplayValue(detail.dataset_analysis?.rows?.test)"
                    class="rounded-xl bg-slate-50 px-4 py-3"
                  >
                    测试行数: {{ formatMaybe(detail.dataset_analysis?.rows?.test) }}
                  </div>
                  <div class="rounded-xl bg-slate-50 px-4 py-3">
                    目标 Macro-F1: {{ formatMetric(detail.dataset_analysis?.target_macro_f1) }}
                  </div>
                </div>
                <div class="mt-4 space-y-2 text-xs text-slate-500">
                  <div
                    v-for="(path, key) in detail.dataset_analysis?.paths || {}"
                    :key="key"
                    class="truncate"
                    :title="path"
                  >
                    {{ key }}: {{ path }}
                  </div>
                  <div
                    v-if="analysisEntries(detail.dataset_analysis?.label_distribution).length"
                    class="rounded-xl border border-slate-100 bg-white px-4 py-3"
                  >
                    <div class="mb-2 text-sm font-semibold text-slate-700">标签分布</div>
                    <div class="grid grid-cols-1 gap-2 md:grid-cols-3">
                      <div
                        v-for="[key, value] in analysisEntries(
                          detail.dataset_analysis?.label_distribution
                        )"
                        :key="key"
                      >
                        {{ formatAnalysisKey(key) }}: {{ formatAnalysisValue(value) }}
                      </div>
                    </div>
                  </div>
                  <div
                    v-if="analysisEntries(detail.dataset_analysis?.preprocessing_stats).length"
                    class="rounded-xl border border-slate-100 bg-white px-4 py-3"
                  >
                    <div class="mb-2 text-sm font-semibold text-slate-700">预处理统计</div>
                    <div class="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <div
                        v-for="[key, value] in analysisEntries(
                          detail.dataset_analysis?.preprocessing_stats
                        )"
                        :key="key"
                        class="truncate"
                        :title="formatAnalysisValue(value)"
                      >
                        {{ formatAnalysisKey(key) }}: {{ formatAnalysisValue(value) }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <HeatmapMatrix
                v-if="hasConfusionMatrix"
                :matrix="detail.confusion_matrix || []"
                :x-labels="confusionMatrixLabels"
                :y-labels="confusionMatrixLabels"
              />
              <div v-else class="rounded-xl border border-dashed border-slate-200 bg-white p-5">
                <h2 class="mb-3 text-lg font-semibold text-slate-900">混淆矩阵</h2>
                <div class="flex min-h-[170px] items-center justify-center text-center">
                  <div class="max-w-sm space-y-2">
                    <p class="text-sm font-semibold text-slate-600">当前训练记录未生成混淆矩阵</p>
                    <p class="text-xs leading-5 text-slate-400">
                      该记录只包含核心指标与损失曲线，缺少完整评估矩阵产物；重新训练或重新后处理后会在这里展示三分类矩阵。
                    </p>
                  </div>
                </div>
              </div>

              <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <h2 class="mb-4 text-lg font-semibold text-slate-900">指标摘要</h2>
                <div class="space-y-3 text-sm text-slate-600">
                  <div>宏平均 F1: {{ formatMetric(detail.metric_highlights?.macro_f1) }}</div>
                  <div>准确率: {{ formatMetric(detail.metric_highlights?.accuracy) }}</div>
                  <div>
                    消极召回率: {{ formatMetric(detail.metric_highlights?.negative_recall) }}
                  </div>
                </div>
              </div>
            </div>

            <div class="space-y-6">
              <div
                v-if="hasRuntimeModels"
                class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <h2 class="mb-4 text-lg font-semibold text-slate-900">运行兼容性</h2>
                <div class="space-y-3">
                  <div
                    v-for="model in detail.runtime_compatibility.registered_models"
                    :key="model.id"
                    class="rounded-xl border border-slate-100 px-4 py-3 text-sm"
                  >
                    <div class="flex items-center justify-between gap-3">
                      <div>
                        <div class="font-semibold text-slate-900">{{ model.name }}</div>
                        <div class="mt-1 text-xs text-slate-500">
                          {{ formatRuntimeType(model.runtime_type) }} /
                          {{ model.artifact_complete ? '产物完整' : '产物不完整' }}
                        </div>
                      </div>
                      <el-tag
                        :type="model.is_runtime_compatible ? 'success' : 'warning'"
                        effect="light"
                      >
                        {{ model.is_runtime_compatible ? '可启用' : '需处理' }}
                      </el-tag>
                    </div>
                    <div v-if="model.incompatibility_reason" class="mt-2 text-xs text-amber-600">
                      {{ model.incompatibility_reason }}
                    </div>
                    <div class="mt-2 truncate text-xs text-slate-400" :title="model.file_label">
                      {{ model.file_label }}
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="lossCurveDates.length"
                class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <h2 class="mb-4 text-lg font-semibold text-slate-900">损失曲线</h2>
                <TrendChart :dates="lossCurveDates" :series="lossCurveSeries" class="h-72" />
              </div>
              <div
                v-else-if="classicalCvMetricItems.length"
                class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div class="mb-4 flex items-center justify-between gap-3">
                  <h2 class="text-lg font-semibold text-slate-900">交叉验证指标</h2>
                  <span class="text-xs text-slate-400">mean ± std</span>
                </div>
                <div class="space-y-5">
                  <div v-for="item in classicalCvMetricItems" :key="item.label" class="space-y-2">
                    <div class="flex items-center justify-between gap-4 text-sm">
                      <span class="font-semibold text-slate-700">{{ item.label }}</span>
                      <span class="font-mono text-xs font-semibold tabular-nums text-slate-600">
                        {{ formatMetric(item.mean) }}
                        <template v-if="item.std !== null">
                          ± {{ formatMetric(item.std) }}</template
                        >
                      </span>
                    </div>
                    <div class="h-3 overflow-hidden rounded-full bg-slate-100">
                      <div
                        class="h-full rounded-full bg-sky-500"
                        :style="{
                          width: `${Math.max(item.percent, item.percent > 0 ? 10 : 0)}%`,
                        }"
                      />
                    </div>
                  </div>
                </div>
                <p class="mt-5 text-xs leading-5 text-slate-400">
                  传统 sklearn
                  模型使用分层交叉验证评估候选参数，因此这里展示验证折均值和波动，不展示按轮次变化的训练曲线。
                </p>
              </div>

              <div
                v-if="hasLeaderboardPreview || hasArtifactSummaries"
                class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <h2 class="mb-4 text-lg font-semibold text-slate-900">排行榜预览与产物摘要</h2>
                <div v-if="hasLeaderboardPreview" class="space-y-2 text-sm text-slate-600">
                  <div
                    v-for="row in detail.leaderboard_preview"
                    :key="row.model_name || row.subject_name"
                  >
                    {{ row.model_name || row.subject_name }} /
                    {{ formatMetric(row.eval_macro_f1 || row.macro_f1) }}
                    <span v-if="row.cv_macro_f1_mean" class="text-xs text-slate-400">
                      / CV {{ formatMetric(row.cv_macro_f1_mean) }}
                    </span>
                  </div>
                </div>
                <div
                  v-if="hasArtifactSummaries"
                  class="space-y-2 text-xs text-slate-500"
                  :class="hasLeaderboardPreview ? 'mt-4' : ''"
                >
                  <div v-for="artifact in detail.artifact_summaries || []" :key="artifact.key">
                    {{ artifact.label }}: {{ artifact.value }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="text-sm text-slate-400">暂无可展示的训练详情</div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="logDialogVisible" title="训练日志" width="70%">
      <div class="space-y-4">
        <div
          v-if="logError"
          class="flex items-start justify-between gap-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3"
        >
          <div class="flex-1 text-sm font-medium text-red-700">
            {{ logError }}
          </div>
          <el-button
            size="small"
            :icon="Refresh"
            :loading="logLoading"
            @click="() => openLogDialog(detail.record_id)"
            >重试</el-button
          >
        </div>
        <div v-else-if="logLoading" class="text-sm text-slate-400">日志加载中...</div>
        <pre
          v-else
          class="max-h-[60vh] overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100 whitespace-pre-wrap"
          >{{ logContent }}</pre
        >
      </div>
    </el-dialog>
  </div>
</template>
