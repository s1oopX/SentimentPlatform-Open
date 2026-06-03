import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { extractErrorMessage } from '@/api/request'
import { createTrainingRecord } from '@/api/admin'
import { classicalCandidateOptions, neuralCandidateOptions } from './trainingConstants'

/**
 * @param {(recordId: string, pageSize: number) => Promise<boolean>} onAfterCreate
 * @param {{ pageSize: number }} recordsPaging
 */
export function useTrainingForm(onAfterCreate, recordsPaging) {
  const submitting = ref(false)

  const form = reactive({
    name: '模型训练任务',
    task_type: 'transformer_search',
    dataset_source: 'workspace_dataset',
    dataset_ref: 'chinese-news-sentiment-c3-ds',
    model_family: 'bert',
    candidate_models: /** @type {string[]} */ ([]),
    search_type: 'random',
    split_strategy: 'auto_split',
    target_macro_f1: 0.85,
    max_length: 256,
    use_gpu: false,
    max_trials: 8,
    cv_folds: 3,
  })

  const showModelFamily = computed(() =>
    ['transformer_train', 'transformer_search'].includes(form.task_type)
  )

  const showCandidateModels = computed(() =>
    ['classical_compare', 'neural_baseline_train'].includes(form.task_type)
  )

  const showSearchType = computed(() =>
    ['transformer_search', 'classical_compare'].includes(form.task_type)
  )

  const showUseGpu = computed(() => form.task_type === 'neural_baseline_train')

  const candidateModelOptions = computed(() => {
    if (form.task_type === 'classical_compare') return classicalCandidateOptions
    if (form.task_type === 'neural_baseline_train') return neuralCandidateOptions
    return []
  })

  const buildCreatePayload = () => {
    const payload = {
      name: form.name,
      task_type: form.task_type,
      dataset_source: form.dataset_source,
      dataset_ref: form.dataset_ref,
      split_strategy: form.split_strategy,
      target_macro_f1: form.target_macro_f1,
      max_length: form.max_length,
      use_gpu: showUseGpu.value ? form.use_gpu : false,
      max_trials: form.max_trials,
      cv_folds: form.cv_folds,
    }

    if (showModelFamily.value) payload.model_family = form.model_family
    if (showCandidateModels.value) payload.candidate_models = [...form.candidate_models]
    if (showSearchType.value) payload.search_type = form.search_type

    return payload
  }

  const validateForm = () => {
    if (!form.name.trim()) return '请填写训练任务名称'
    if (!form.dataset_ref.trim()) return '请填写数据集引用'
    if (showModelFamily.value && !form.model_family) return '请选择模型族'
    if (showCandidateModels.value && !form.candidate_models.length) return '请选择候选模型'
    if (showSearchType.value && !form.search_type) return '请选择搜索方式'
    return ''
  }

  const resetForm = () => {
    form.name = '模型训练任务'
    form.task_type = 'transformer_search'
    form.dataset_source = 'workspace_dataset'
    form.dataset_ref = 'chinese-news-sentiment-c3-ds'
    form.model_family = 'bert'
    form.candidate_models = /** @type {string[]} */ ([])
    form.search_type = 'random'
    form.split_strategy = 'auto_split'
    form.target_macro_f1 = 0.85
    form.max_length = 256
    form.use_gpu = false
    form.max_trials = 8
    form.cv_folds = 3
  }

  /**
   * @param {import('vue').Ref<string>} errorMessage
   * @param {() => Promise<void>} onErrorFallback
   */
  const handleCreate = async (errorMessage, onErrorFallback) => {
    const validationMessage = validateForm()
    if (validationMessage) {
      errorMessage.value = validationMessage
      ElMessage.warning(validationMessage)
      return
    }

    submitting.value = true
    try {
      const response = await createTrainingRecord(buildCreatePayload())
      ElMessage.success('已提交真实训练任务')
      resetForm()
      const refreshed = await onAfterCreate(response?.data?.record_id || '', recordsPaging.pageSize)
      if (!refreshed) ElMessage.warning('刷新失败，页面可能陈旧')
    } catch (/** @type {any} */ err) {
      errorMessage.value = extractErrorMessage(err, '训练任务提交失败，请稍后重试')
      ElMessage.error(errorMessage.value)
      const [refreshResult] = await Promise.allSettled([onErrorFallback()])
      if (refreshResult.status === 'rejected') {
        ElMessage.warning('训练记录列表刷新失败，页面数据可能不是最新')
      }
    } finally {
      submitting.value = false
    }
  }

  watch(
    () => form.task_type,
    (taskType) => {
      if (['transformer_train', 'transformer_search'].includes(taskType)) {
        if (!form.model_family) form.model_family = 'bert'
        form.candidate_models = /** @type {string[]} */ ([])
        return
      }
      form.model_family = ''
      if (taskType !== 'neural_baseline_train') form.use_gpu = false
      if (taskType === 'classical_compare') {
        const allowed = new Set(classicalCandidateOptions.map((item) => item.value))
        const next = form.candidate_models.filter((item) => allowed.has(item))
        form.candidate_models = next.length ? next : ['linear_svm']
        return
      }
      if (taskType === 'neural_baseline_train') {
        const allowed = new Set(neuralCandidateOptions.map((item) => item.value))
        const next = form.candidate_models.filter((item) => allowed.has(item))
        form.candidate_models = next.length ? next : ['textcnn']
      }
    },
    { immediate: true }
  )

  return {
    submitting,
    form,
    showModelFamily,
    showCandidateModels,
    showSearchType,
    showUseGpu,
    candidateModelOptions,
    handleCreate,
    resetForm,
    validateForm,
  }
}
