<script setup>
import PageHeader from '@/components/PageHeader.vue'
import { Link, Document } from '@element-plus/icons-vue'

const swaggerUrl = '/swagger/'
const redocUrl = '/redoc/'
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="API 文档" description="后端接口文档，基于 OpenAPI 规范自动生成" />

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center gap-3 mb-4">
          <div
            class="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600"
          >
            <el-icon :size="20"><Link /></el-icon>
          </div>
          <div>
            <h3 class="text-base font-semibold text-slate-900">Swagger UI</h3>
            <p class="text-xs text-slate-400">交互式文档</p>
          </div>
        </div>
        <p class="text-sm text-slate-500 mb-4">
          支持在线调试接口、查看请求参数与响应示例，适合开发和测试
        </p>
        <a
          :href="swaggerUrl"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-2 rounded-lg bg-green-50 px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-100 transition-colors"
        >
          <el-icon><Link /></el-icon>
          打开 Swagger UI
        </a>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center gap-3 mb-4">
          <div
            class="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600"
          >
            <el-icon :size="20"><Document /></el-icon>
          </div>
          <div>
            <h3 class="text-base font-semibold text-slate-900">ReDoc</h3>
            <p class="text-xs text-slate-400">只读文档</p>
          </div>
        </div>
        <p class="text-sm text-slate-500 mb-4">
          美观的三栏式布局，清晰易读，适合阅览和分享给团队成员
        </p>
        <a
          :href="redocUrl"
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors"
        >
          <el-icon><Document /></el-icon>
          打开 ReDoc
        </a>
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 class="text-base font-semibold text-slate-700 mb-4">接口概览</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
        <div class="rounded-lg bg-slate-50 p-4">
          <div class="font-medium text-slate-900 mb-1">认证模块</div>
          <div class="text-slate-500">/api/auth/*</div>
          <div class="text-xs text-slate-400 mt-1">登录、注册、JWT 刷新、密码重置</div>
        </div>
        <div class="rounded-lg bg-slate-50 p-4">
          <div class="font-medium text-slate-900 mb-1">情感分析</div>
          <div class="text-slate-500">/api/analyze/*</div>
          <div class="text-xs text-slate-400 mt-1">单条分析、批量分析、历史记录</div>
        </div>
        <div class="rounded-lg bg-slate-50 p-4">
          <div class="font-medium text-slate-900 mb-1">管理面板</div>
          <div class="text-slate-500">/api/admin/*</div>
          <div class="text-xs text-slate-400 mt-1">用户管理、模型管理、训练中心</div>
        </div>
        <div class="rounded-lg bg-slate-50 p-4">
          <div class="font-medium text-slate-900 mb-1">报告服务</div>
          <div class="text-slate-500">/api/report/*</div>
          <div class="text-xs text-slate-400 mt-1">报告生成、下载、列表查询</div>
        </div>
      </div>
    </div>
  </div>
</template>
