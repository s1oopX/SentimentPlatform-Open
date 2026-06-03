<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useLogout } from '@/composables/useLogout'
import { useAppLayout } from '@/composables/useAppLayout'
import { DataLine, Document, Odometer } from '@element-plus/icons-vue'
import AppLayoutShell from '@/components/AppLayoutShell.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { sidebarOpen, toggleSidebar, closeSidebar, isLgViewport, pageTitle } = useAppLayout(route)

const displayName = computed(
  () => authStore.user?.display_name || authStore.user?.nickname || authStore.user?.email || '用户'
)
const userInitial = computed(() => displayName.value.charAt(0)?.toUpperCase() || '用')

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
          <span class="sidebar-brand-subtitle">情感分析工作台</span>
        </div>
      </div>
    </template>

    <template #menu="{ collapsed }">
      <el-menu
        :default-active="route.path"
        class="layout-menu user-menu tech-menu"
        background-color="transparent"
        text-color="hsl(210 40% 98%)"
        active-text-color="hsl(0 0% 100%)"
        :collapse="collapsed"
        :collapse-transition="false"
        :default-openeds="['analysis-group']"
        router
      >
        <el-menu-item index="/user/dashboard">
          <el-icon><DataLine /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-sub-menu index="analysis-group" popper-class="tech-menu-popper">
          <template #title>
            <el-icon><Odometer /></el-icon>
            <span>分析中心</span>
          </template>
          <el-menu-item index="/user/analysis">单条分析</el-menu-item>
          <el-menu-item index="/user/analysis/batch">批量分析</el-menu-item>
          <el-menu-item index="/user/history">分析历史</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/user/reports">
          <el-icon><Document /></el-icon>
          <span>报告中心</span>
        </el-menu-item>
      </el-menu>
    </template>

    <template #sidebar-footer>
      <el-dropdown trigger="click" class="w-full">
        <div class="tech-user-profile" :title="displayName">
          <el-avatar :size="32" class="mr-2" :src="authStore.user?.avatar || undefined">{{
            userInitial
          }}</el-avatar>
          <div class="tech-user-info">
            <div class="font-medium text-sm text-white">{{ displayName }}</div>
            <div class="tech-role-badge">个人账号</div>
          </div>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="router.push('/user/profile')">个人资料</el-dropdown-item>
            <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>
  </AppLayoutShell>
</template>
