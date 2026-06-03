export const taskTypeOptions = [
  { label: 'Transformer 训练', value: 'transformer_train' },
  { label: 'Transformer 搜索', value: 'transformer_search' },
  { label: '传统模型比较', value: 'classical_compare' },
  { label: '神经网络基线训练', value: 'neural_baseline_train' },
]

export const modelFamilyOptions = [
  { label: 'BERT 中文基座', value: 'bert' },
  { label: 'RoBERTa 中文基座', value: 'roberta' },
]

export const searchTypeOptions = [
  { label: '随机搜索', value: 'random' },
  { label: '网格搜索', value: 'grid' },
  { label: '不搜索', value: 'none', classicalOnly: true },
]

export const classicalCandidateOptions = [
  { label: '逻辑回归', value: 'logistic_regression' },
  { label: '线性 SVM', value: 'linear_svm' },
  { label: '随机森林', value: 'random_forest' },
]

export const neuralCandidateOptions = [
  { label: 'TextCNN', value: 'textcnn' },
  { label: 'BiLSTM', value: 'bilstm' },
]

const findOptionLabel = (options, value) =>
  options.find((option) => option.value === value)?.label || value || '--'

export const formatModelFamily = (value) => findOptionLabel(modelFamilyOptions, value)

export const formatSearchType = (value) => findOptionLabel(searchTypeOptions, value)

export const formatCandidateModel = (value) =>
  findOptionLabel([...classicalCandidateOptions, ...neuralCandidateOptions], value)

export const formatSourceType = (value) => {
  const labels = { training_run: '真实任务' }
  return labels[value] || value || '--'
}

export const formatExecutionMode = (value) => {
  const labels = { celery: 'Celery 队列' }
  return labels[value] || value || '--'
}

export const formatStatus = (value) => {
  const labels = {
    queued: '已排队',
    running: '执行中',
    succeeded: '成功',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[value] || value || '--'
}

export const formatPostRunStatus = (value) => {
  const labels = {
    pending: '待处理',
    warning: '警告',
    failed: '失败',
    succeeded: '成功',
    running: '执行中',
    cancelled: '已取消',
  }
  return labels[value] || value || '--'
}

export const formatRuntimeType = (value) => {
  const labels = {
    transformer: 'Transformer',
    classical_joblib: '传统模型 joblib',
    neural_torch: '神经网络 PyTorch',
    unsupported: '暂不支持',
  }
  return labels[value] || value || '--'
}

export const formatMaybe = (value) => {
  if (value === null || value === undefined || value === '') return '--'
  return value
}

export const formatMetric = (value) => {
  if (value === null || value === undefined || value === '') return '--'
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return String(value)
  return numberValue.toFixed(4)
}

export const getRunId = (recordId) => String(recordId || '').replace(/^run-/, '')

export const readLogText = (data) => {
  if (typeof data === 'string') return data
  if (!data) return ''
  return data.log_text || data.text || data.log || data.content || data.message || ''
}
