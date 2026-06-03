<script setup>
import { computed, ref, reactive, onMounted } from 'vue'
import { useRefreshOnActivated } from '@/composables/useRefreshOnActivated'
import { usePageSizeReset } from '@/composables/usePagination'
import { useAuthStore } from '@/stores/auth'
import { getUsers, updateUserStatus, updateUserRole } from '@/api/admin'
import { extractErrorMessage } from '@/api/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Unlock, Lock, SwitchButton, Warning } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const isSelf = (row) => row?.id === authStore.user?.id

/**
 * @typedef {{
 *   id: number
 *   email?: string
 *   role?: string
 *   role_display?: string
 *   nickname?: string
 *   display_name?: string
 *   status?: number
 *   [key: string]: any
 * }} AdminUserRow
 */
const roleDialogVisible = ref(false)
/** @type {import('vue').Ref<AdminUserRow | null>} */ const roleDialogTarget = ref(null)
const roleDialogSelected = ref('')
const roleDialogReason = ref('')
const roleDialogLoading = ref(false)

const openRoleDialog = (row) => {
  roleDialogTarget.value = row
  roleDialogSelected.value = ''
  roleDialogReason.value = ''
  roleDialogVisible.value = true
}

const confirmRoleChange = async () => {
  if (!roleDialogSelected.value || !roleDialogTarget.value) return
  const row = roleDialogTarget.value
  const displayName = getUserDisplayName(row)
  const currentRole = row.role || 'user'
  const reason = roleDialogReason.value.trim()

  if (roleDialogSelected.value === currentRole) {
    ElMessage.warning('新角色与当前角色相同，无需变更')
    return
  }

  if (!reason) {
    ElMessage.warning('请填写角色变更理由')
    return
  }

  roleDialogLoading.value = true
  try {
    const res = await updateUserRole(row.id, {
      role: roleDialogSelected.value,
      reason,
    })
    const nextUser = res?.data
    if (nextUser?.id) {
      tableData.value = tableData.value.map((user) => (user.id === nextUser.id ? nextUser : user))
    } else {
      await fetchUsers()
    }
    ElMessage.success(`用户 ${displayName} 角色已变更`)
    roleDialogVisible.value = false
  } catch (e) {
    ElMessage.error(extractErrorMessage(e, '角色变更失败'))
  } finally {
    roleDialogLoading.value = false
  }
}

const ROLE_OPTIONS = [
  { value: 'user', label: '普通用户', description: '个人分析、报表' },
  { value: 'analyst', label: '分析师', description: '审核评论、管理项目' },
]

const loading = ref(false)
/** @type {import('vue').Ref<AdminUserRow[]>} */ const tableData = ref([])
const total = ref(0)
const errorMessage = ref('')

const queryParams = reactive({
  page: 1,
  page_size: 15,
  search: '',
})

const emptyStateMessage = computed(() => errorMessage.value || '暂无用户数据')
const isUserEnabled = (user) => Number(user?.status) === 1
const getUserDisplayName = (user) => user?.display_name || user?.nickname || user?.email || '-'
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
const getUserInitial = (user) => {
  const label = getUserDisplayName(user)
  return label ? label.charAt(0).toUpperCase() : '?'
}

const fetchUsers = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await getUsers({
      page: queryParams.page,
      page_size: queryParams.page_size,
      search: queryParams.search,
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
    errorMessage.value = '用户列表加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const handleSearchChange = async () => {
  queryParams.page = 1
  await fetchUsers()
}

const { handlePageSizeChange } = usePageSizeReset(queryParams, fetchUsers)

onMounted(() => {
  fetchUsers()
})

useRefreshOnActivated(fetchUsers)

const handleStatusToggle = async (row) => {
  const actionText = isUserEnabled(row) ? '禁用' : '启用'
  const displayName = getUserDisplayName(row)

  try {
    const { value: reason } = await ElMessageBox.prompt(
      `确定要 ${actionText} 用户 "${displayName}" 吗？\n请填写操作理由（1-200字）`,
      '状态变更确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPlaceholder: '请输入操作理由',
        inputPattern: /^.{1,200}$/,
        inputErrorMessage: '理由不能为空且不超过200字',
        type: isUserEnabled(row) ? 'warning' : 'success',
        roundButton: true,
      }
    )

    const res = await updateUserStatus(row.id, { reason })
    const nextUser = res?.data

    if (nextUser?.id) {
      tableData.value = tableData.value.map((user) => (user.id === nextUser.id ? nextUser : user))
    } else {
      await fetchUsers()
    }

    ElMessage.success(`用户 ${displayName} 已成功${actionText}`)
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(extractErrorMessage(e, '操作失败'))
    }
  }
}
</script>

<template>
  <div class="h-full flex flex-col space-y-8">
    <div class="space-y-2">
      <h1 class="text-2xl font-bold text-slate-800">用户管理</h1>
      <p class="text-slate-500 text-sm">管控系统权限、角色分配及账户活跃状态</p>
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
        <div class="flex flex-wrap gap-4">
          <el-input
            v-model="queryParams.search"
            placeholder="搜索昵称、邮箱或手机号..."
            class="!w-full sm:!w-80 el-input-rounded"
            clearable
            @change="handleSearchChange"
          >
            <template #prefix
              ><el-icon class="text-slate-400"><Search /></el-icon
            ></template>
          </el-input>
          <el-button :icon="Refresh" circle @click="fetchUsers" />
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
          <el-table-column prop="id" label="编号" width="70" align="center" />

          <el-table-column label="用户信息" min-width="220">
            <template #default="scope">
              <div class="flex items-center gap-3 py-2">
                <el-avatar
                  :size="40"
                  :src="scope.row.avatar || undefined"
                  class="shrink-0 bg-slate-100 text-slate-600 font-bold"
                >
                  {{ getUserInitial(scope.row) }}
                </el-avatar>
                <div class="flex flex-col">
                  <span class="font-bold text-slate-900">{{ getUserDisplayName(scope.row) }}</span>
                  <span class="text-xs text-slate-500">{{ scope.row.email }}</span>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="角色权限" width="120">
            <template #default="scope">
              <el-tag
                :type="
                  scope.row.role === 'admin'
                    ? 'danger'
                    : scope.row.role === 'analyst'
                      ? 'warning'
                      : 'info'
                "
                effect="light"
                class="!px-3 !rounded-md !font-semibold"
              >
                {{ scope.row.role_display || scope.row.role || '-' }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="账户状态" width="110" align="center">
            <template #default="scope">
              <div class="flex items-center justify-center">
                <div
                  v-if="isUserEnabled(scope.row)"
                  class="flex items-center gap-1.5 text-green-600 bg-green-50 px-2 py-1 rounded-full text-xs font-bold"
                >
                  <div class="h-1.5 w-1.5 bg-green-600 rounded-full"></div>
                  {{ scope.row.status_display || '启用' }}
                </div>
                <div
                  v-else
                  class="flex items-center gap-1.5 text-slate-400 bg-slate-50 px-2 py-1 rounded-full text-xs font-bold"
                >
                  <div class="h-1.5 w-1.5 bg-slate-400 rounded-full"></div>
                  {{ scope.row.status_display || '禁用' }}
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="created_at" label="加入时间" width="150" align="center">
            <template #default="scope">
              <span class="text-slate-500 text-sm font-mono">{{
                formatDateTime(scope.row.created_at)
              }}</span>
            </template>
          </el-table-column>

          <el-table-column label="快捷操作" width="160" align="center">
            <template #default="scope">
              <div v-if="isSelf(scope.row)" class="text-xs text-slate-400">当前账号</div>
              <div v-else class="flex items-center justify-center gap-2">
                <el-button
                  link
                  type="primary"
                  class="!font-bold"
                  @click="openRoleDialog(scope.row)"
                >
                  <el-icon class="mr-1"><SwitchButton /></el-icon>
                  改角色
                </el-button>
                <el-button
                  v-if="isUserEnabled(scope.row)"
                  link
                  type="danger"
                  class="!font-bold"
                  @click="handleStatusToggle(scope.row)"
                >
                  <el-icon class="mr-1"><Lock /></el-icon>
                  禁用
                </el-button>
                <el-button
                  v-else
                  link
                  type="success"
                  class="!font-bold"
                  @click="handleStatusToggle(scope.row)"
                >
                  <el-icon class="mr-1"><Unlock /></el-icon>
                  启用
                </el-button>
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
          @current-change="fetchUsers"
        />
      </div>
    </div>

    <el-dialog v-model="roleDialogVisible" title="变更用户角色" width="420px">
      <div v-if="roleDialogTarget" class="space-y-4">
        <div class="flex items-center gap-3 rounded-lg bg-slate-50 px-4 py-3">
          <span class="text-sm font-medium text-slate-500">用户</span>
          <span class="text-sm font-semibold text-slate-900">
            {{ getUserDisplayName(roleDialogTarget) }}
          </span>
          <el-tag
            size="small"
            :type="
              roleDialogTarget.role === 'admin'
                ? 'danger'
                : roleDialogTarget.role === 'analyst'
                  ? 'warning'
                  : 'info'
            "
          >
            {{ roleDialogTarget.role_display || roleDialogTarget.role || '-' }}
          </el-tag>
        </div>

        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700">新角色</label>
          <div class="flex flex-col gap-2">
            <button
              v-for="opt in ROLE_OPTIONS"
              :key="opt.value"
              type="button"
              :disabled="opt.value === (roleDialogTarget.role || 'user')"
              class="flex min-h-11 w-full items-center rounded-lg border px-3 text-left transition disabled:cursor-not-allowed disabled:opacity-50"
              :class="
                roleDialogSelected === opt.value
                  ? 'border-blue-300 bg-blue-50 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-slate-50'
              "
              @click="roleDialogSelected = opt.value"
            >
              <span class="font-medium">{{ opt.label }}</span>
              <span class="ml-2 text-xs text-slate-400">{{ opt.description }}</span>
            </button>
          </div>
        </div>

        <div>
          <label class="mb-2 block text-sm font-medium text-slate-700"
            >变更理由 <span class="text-red-500">*</span></label
          >
          <el-input
            v-model="roleDialogReason"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
            placeholder="简要说明变更原因"
          />
        </div>

        <div
          v-if="roleDialogSelected && roleDialogSelected !== (roleDialogTarget.role || 'user')"
          class="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700"
        >
          <el-icon class="mt-0.5 shrink-0"><Warning /></el-icon>
          <span>
            将角色从
            <strong>{{ roleDialogTarget.role_display || roleDialogTarget.role }}</strong>
            变更为
            <strong>{{ ROLE_OPTIONS.find((o) => o.value === roleDialogSelected)?.label }}</strong>
          </span>
        </div>
      </div>

      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="
            !roleDialogSelected || roleDialogSelected === (roleDialogTarget?.role || 'user')
          "
          :loading="roleDialogLoading"
          @click="confirmRoleChange"
        >
          确认变更
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
