<script setup>
import { computed } from 'vue'
import { Expand, Fold } from '@element-plus/icons-vue'

const props = defineProps({
  sidebarOpen: { type: Boolean, required: true },
  isDesktop: { type: Boolean, default: false },
  pageTitle: { type: String, default: '' },
  sidebarClass: { type: String, default: '' },
})

const emit = defineEmits(['toggle', 'close'])
const sidebarCollapsed = computed(() => props.isDesktop && !props.sidebarOpen)
</script>

<template>
  <el-container class="layout-root min-h-screen">
    <div
      v-show="sidebarOpen && !isDesktop"
      class="sidebar-overlay"
      aria-hidden="true"
      @click="emit('close')"
    />
    <el-aside
      width="240px"
      class="layout-sidebar"
      :class="[sidebarClass, { 'is-open': sidebarOpen, 'is-collapsed': sidebarCollapsed }]"
    >
      <div class="logo-container">
        <slot name="logo" />
      </div>

      <button
        type="button"
        class="desktop-sidebar-toggle"
        :aria-label="sidebarOpen ? '收起侧边栏' : '展开侧边栏'"
        :aria-expanded="sidebarOpen"
        @click="emit('toggle')"
      >
        <el-icon :size="18">
          <Fold v-if="sidebarOpen" />
          <Expand v-else />
        </el-icon>
      </button>

      <div class="sidebar-menu-area">
        <slot name="menu" :collapsed="sidebarCollapsed" />
      </div>

      <div class="sidebar-footer">
        <slot name="sidebar-footer" />
      </div>
    </el-aside>

    <el-container class="layout-main-container bg-slate-50" :class="{ 'is-shifted': sidebarOpen }">
      <el-header
        class="layout-header border-b flex items-center justify-between bg-white px-6 backdrop-blur-md bg-white/80"
        :class="{ 'is-shifted': sidebarOpen }"
      >
        <div class="header-breadcrumb flex items-center gap-3">
          <button
            type="button"
            class="sidebar-toggle"
            :aria-label="sidebarOpen ? '收起侧边栏' : '展开侧边栏'"
            :aria-expanded="sidebarOpen"
            @click="emit('toggle')"
          >
            <el-icon :size="20">
              <Fold v-if="sidebarOpen" />
              <Expand v-else />
            </el-icon>
          </button>
          <h2 v-if="pageTitle" class="text-base font-semibold text-slate-700">
            {{ pageTitle }}
          </h2>
        </div>
      </el-header>

      <el-main class="layout-main p-6">
        <router-view v-slot="{ Component, route: viewRoute }">
          <transition name="fade" mode="out-in">
            <keep-alive>
              <component :is="Component" v-if="viewRoute.meta.keepAlive" :key="viewRoute.name" />
            </keep-alive>
          </transition>
          <transition name="fade" mode="out-in">
            <component :is="Component" v-if="!viewRoute.meta.keepAlive" :key="viewRoute.name" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-root {
  --sidebar-expanded-width: 272px;
  --sidebar-collapsed-width: 80px;
  --layout-gutter: 56px;
  background: #edf3fb;
}

.layout-sidebar {
  height: 100vh;
  display: flex;
  flex-direction: column;
  z-index: 50;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: var(--sidebar-expanded-width) !important;
  overflow: visible;
  transform: translateX(-100%);
  transition: transform 0.2s ease;
  border: none !important;
}

.layout-sidebar::after {
  content: '';
  position: absolute;
  top: 0;
  right: calc(-1 * var(--layout-gutter));
  bottom: 0;
  width: var(--layout-gutter);
  background: linear-gradient(90deg, #d8e5f5 0%, #e8f0f8 48%, #f6f8fc 100%);
  border-left: 1px solid #c9d8eb;
  border-right: 1px solid #dbe4f0;
  display: none;
  pointer-events: none;
}

.layout-sidebar.is-open {
  transform: translateX(0);
  box-shadow: 0 18px 42px -24px rgb(15 23 42 / 0.45);
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.55);
  z-index: 40;
}

.sidebar-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: inherit;
  cursor: pointer;
  transition: background-color 0.2s;
}
.sidebar-toggle:hover {
  background-color: hsl(var(--accent));
}
.sidebar-toggle:focus-visible,
.desktop-sidebar-toggle:focus-visible {
  outline: 2px solid rgba(56, 189, 248, 0.85);
  outline-offset: 2px;
}

.desktop-sidebar-toggle {
  display: none;
}

.border-r {
  border-right: none;
}
.border-b {
  border-bottom: 1px solid #e2e8f0;
}

.logo-container {
  height: 78px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid hsl(214 32% 91%);
  margin-bottom: 0;
}

.sidebar-menu-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid hsl(var(--border));
}

.layout-header {
  height: 60px;
  background-color: hsl(var(--background));
  z-index: 30;
}

.bg-muted\/20 {
  background-color: hsl(var(--muted));
}

.layout-main-container {
  min-height: 100vh;
  min-width: 0;
  background: #f6f8fc !important;
  transition:
    margin-left 0.2s ease,
    width 0.2s ease;
}

.layout-main {
  min-width: 0;
}

.fade-enter-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.fade-leave-to {
  opacity: 0;
}

@media (min-width: 768px) {
  .layout-sidebar::after {
    display: block;
  }

  .layout-sidebar {
    transform: translateX(0);
    transition:
      width 0.2s ease,
      box-shadow 0.2s ease;
  }

  .layout-sidebar.is-collapsed {
    width: var(--sidebar-collapsed-width) !important;
  }

  .layout-sidebar.is-open {
    box-shadow: none;
  }

  .sidebar-overlay {
    display: none !important;
  }

  .layout-main-container {
    margin-left: calc(var(--sidebar-collapsed-width) + var(--layout-gutter));
    width: calc(100% - var(--sidebar-collapsed-width) - var(--layout-gutter));
  }

  .layout-main-container.is-shifted {
    margin-left: calc(var(--sidebar-expanded-width) + var(--layout-gutter));
    width: calc(100% - var(--sidebar-expanded-width) - var(--layout-gutter));
  }

  .layout-header {
    position: fixed;
    left: calc(var(--sidebar-collapsed-width) + var(--layout-gutter));
    right: 0;
    top: 0;
    width: calc(100% - var(--sidebar-collapsed-width) - var(--layout-gutter));
    transition:
      left 0.2s ease,
      width 0.2s ease;
  }

  .layout-header.is-shifted {
    left: calc(var(--sidebar-expanded-width) + var(--layout-gutter));
    width: calc(100% - var(--sidebar-expanded-width) - var(--layout-gutter));
  }

  .layout-header .sidebar-toggle {
    display: none;
  }

  .desktop-sidebar-toggle {
    position: absolute;
    top: 92px;
    right: -16px;
    z-index: 2;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: 1px solid #dbe3ef;
    border-radius: 999px;
    background: #ffffff;
    color: #475569;
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
    cursor: pointer;
    transition:
      background-color 0.2s ease,
      color 0.2s ease,
      transform 0.2s ease;
  }

  .desktop-sidebar-toggle:hover {
    background: #eff6ff;
    border-color: #bfdbfe;
    color: #2563eb;
  }

  .layout-sidebar.is-collapsed .desktop-sidebar-toggle {
    top: 92px;
    right: 24px;
  }

  .layout-main {
    padding-top: 84px;
    padding-left: 32px;
    padding-right: 24px;
  }
}
</style>
