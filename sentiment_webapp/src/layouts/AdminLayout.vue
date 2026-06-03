<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useLogout } from '@/composables/useLogout'
import { useAppLayout } from '@/composables/useAppLayout'
import {
  Collection,
  Cpu,
  DataBoard,
  Document,
  FolderChecked,
  List,
  TrendCharts,
  User,
} from '@element-plus/icons-vue'
import AppLayoutShell from '@/components/AppLayoutShell.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { sidebarOpen, toggleSidebar, closeSidebar, isLgViewport, pageTitle } = useAppLayout(route)

const adminDisplayName = computed(
  () =>
    authStore.user?.display_name || authStore.user?.nickname || authStore.user?.email || '管理员'
)
const adminInitial = computed(() => adminDisplayName.value.charAt(0)?.toUpperCase() || '管')

const goToProfile = () => router.push('/admin/profile')

const { handleLogout } = useLogout()
</script>

<template>
  <AppLayoutShell
    :sidebar-open="sidebarOpen"
    :is-desktop="isLgViewport"
    :page-title="pageTitle"
    sidebar-class="dark-sidebar"
    @toggle="toggleSidebar"
    @close="closeSidebar"
  >
    <template #logo>
      <div class="flex items-center gap-2.5">
        <div class="sidebar-brand-logo">
          <img src="/brand/yx-logo.svg" alt="" />
        </div>
        <div class="sidebar-brand-copy">
          <span class="sidebar-brand-name">云析智研</span>
          <span class="sidebar-brand-subtitle">管理控制台</span>
        </div>
      </div>
    </template>

    <template #menu="{ collapsed }">
      <el-menu
        :default-active="route.path"
        class="layout-menu admin-menu tech-menu"
        background-color="transparent"
        text-color="hsl(210 40% 98%)"
        active-text-color="hsl(0 0% 100%)"
        :collapse="collapsed"
        :collapse-transition="false"
        router
      >
        <el-menu-item index="/admin/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>控制台</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/datasets">
          <el-icon><Collection /></el-icon>
          <span>数据集管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/models">
          <el-icon><Cpu /></el-icon>
          <span>模型管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/training">
          <el-icon><TrendCharts /></el-icon>
          <span>训练中心</span>
        </el-menu-item>
        <el-menu-item index="/admin/logs">
          <el-icon><List /></el-icon>
          <span>操作日志</span>
        </el-menu-item>
        <el-menu-item index="/admin/api-docs">
          <el-icon><Document /></el-icon>
          <span>API 文档</span>
        </el-menu-item>
        <el-menu-item index="/admin/backup">
          <el-icon><FolderChecked /></el-icon>
          <span>数据库备份</span>
        </el-menu-item>
      </el-menu>
    </template>

    <template #sidebar-footer>
      <el-dropdown trigger="click" class="w-full">
        <div class="tech-user-profile" :title="adminDisplayName">
          <el-avatar :size="32" class="mr-2" :src="authStore.user?.avatar || undefined">{{
            adminInitial
          }}</el-avatar>
          <div class="tech-user-info">
            <div class="font-medium text-sm text-white">{{ adminDisplayName }}</div>
            <div class="tech-role-badge">管理员账号</div>
          </div>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="goToProfile">个人资料</el-dropdown-item>
            <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>
  </AppLayoutShell>
</template>
