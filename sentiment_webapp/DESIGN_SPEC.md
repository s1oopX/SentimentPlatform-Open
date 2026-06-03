# 前端 UI 重构设计规范

## 一、设计语言定位

**现代企业级 SaaS** — 冷静、精准、高效。适合舆情与数据分析场景。

视觉风格：极简扁平 + 微重力感（subtle shadow），深色侧边栏 + 浅灰内容区。

---

## 二、色彩系统

### 2.1 主色调

```css
--primary: 224 71.4% 45.1%;         /* indigo-600: 主操作按钮、活跃状态 */
--primary-foreground: 210 40% 98%;  /* 主色上的白色文字 */
```

### 2.2 中性色

| 用途 | Tailwind 类 | 说明 |
|------|-------------|------|
| 页面背景 | `bg-slate-50` | 柔和浅灰，不刺眼 |
| 卡片背景 | `bg-white` | 白色浮层 |
| 主标题 | `text-slate-800` | 深色但非纯黑 |
| 次要文字 | `text-slate-500` | 辅助信息 |
| 弱文字 | `text-slate-400` | 时间戳、提示 |
| 边框 | `border-slate-200` | 极淡分割线 |
| 侧边栏 | 深色渐变（已有） | `hsl(220 20% 16%)` |

### 2.3 情感语义色（全局统一）

| 情感 | 色值 | Tailwind | 用途 |
|------|------|----------|------|
| 积极 | `#10b981` | `emerald-500` | 图表、标签、高亮 |
| 消极 | `#f43f5e` | `rose-500` | 图表、标签、高亮 |
| 中性 | `#f59e0b` | `amber-500` | 图表、标签、高亮 |

这三个色值必须在 ECharts 图表、表格标签、分析结果展示中保持一致。

### 2.4 功能色

| 用途 | 色值 | Tailwind |
|------|------|----------|
| 成功 | `#10b981` | `emerald-500` |
| 警告 | `#f59e0b` | `amber-500` |
| 错误 | `#ef4444` | `red-500` |
| 信息 | `#6366f1` | `indigo-500` |

---

## 三、排版规范

### 3.1 字体

```css
font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
```

### 3.2 尺寸层级

| 级别 | 类 | 用途 |
|------|-----|------|
| 页面标题 | `text-2xl font-bold text-slate-800` | 页面顶部 |
| 卡片标题 | `text-base font-semibold text-slate-700` | 卡片头部 |
| 正文 | `text-sm text-slate-600` | 表格、描述 |
| 辅助 | `text-xs text-slate-400` | 时间戳、注解 |
| 大数字（统计卡片） | `text-3xl font-bold tabular-nums` | StatCard 中的核心数字 |

### 3.3 数字等宽

所有统计数字使用 `font-variant-numeric: tabular-nums`（Tailwind 类：`tabular-nums`），确保数字上下对齐。

---

## 四、间距与圆角

### 4.1 间距

| 场景 | 值 | Tailwind |
|------|-----|----------|
| 页面内边距 | 24px | `p-6` |
| 卡片内边距 | 24px | `p-6` |
| 卡片间距 | 24px | `gap-6` |
| 表格行高 | 松散 | 默认 Element Plus |

### 4.2 圆角

| 组件 | 圆角 | Tailwind |
|------|------|----------|
| 卡片 | 12px | `rounded-xl` |
| 按钮 | 8px | `rounded-lg` |
| 输入框 | 12px | `rounded-xl`（已有 el-input-rounded） |
| 弹窗 | 16px | `rounded-2xl` |
| 标签 Tag | 6px | `rounded-md` |
| 头像 | 圆形 | `rounded-full` |

### 4.3 阴影

| 场景 | Tailwind |
|------|----------|
| 卡片 | `shadow-sm` |
| 弹窗 | `shadow-xl` |
| 悬浮卡片 | `hover:shadow-md transition-shadow` |
| 侧边栏展开 | 已有深色阴影 |

---

## 五、卡片规范

所有数据卡片统一结构：

```html
<div class="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
  <h3 class="text-base font-semibold text-slate-700 mb-4">卡片标题</h3>
  <!-- 内容 -->
</div>
```

StatCard（统计数字卡片）：

```html
<div class="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
  <p class="text-sm text-slate-500 mb-1">总分析次数</p>
  <p class="text-3xl font-bold text-slate-800 tabular-nums">12,345</p>
  <p class="text-xs text-emerald-500 mt-2">↑ 12% 较上周</p>
</div>
```

---

## 六、ECharts 图表规范

### 6.1 全局配置

```javascript
// 统一 ECharts 主题色
const SENTIMENT_COLORS = {
  positive: '#10b981',  // emerald-500
  negative: '#f43f5e',  // rose-500
  neutral: '#f59e0b',   // amber-500
}

// 网格线
grid: { left: 48, right: 24, top: 32, bottom: 32 }
splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }  // slate-200 虚线

// Tooltip
tooltip: {
  backgroundColor: '#fff',
  borderColor: '#e2e8f0',
  borderWidth: 1,
  borderRadius: 8,
  textStyle: { color: '#334155', fontSize: 13 },
  padding: [8, 12],
  extraCssText: 'box-shadow: 0 4px 12px rgba(0,0,0,0.08);'
}
```

### 6.2 颜色顺序

图表 series 的默认颜色顺序：
1. `#6366f1` (indigo-500) — 主数据
2. `#10b981` (emerald-500) — 积极
3. `#f43f5e` (rose-500) — 消极
4. `#f59e0b` (amber-500) — 中性
5. `#8b5cf6` (violet-500) — 对比数据

---

## 七、三角色差异化设计原则

### 7.1 普通用户（/user/）

- **核心理念：开门见山，结果直达**
- Dashboard：3~4 个 StatCard + 一个趋势图，不要信息过载
- SingleAnalysis：大输入框居中，结果摘要醒目（情感标签 + 置信度 + 关键词高亮）
- 操作流程尽量短：输入 → 分析 → 看结果，不超过 2 步

### 7.2 分析师（/analyst/）

- **核心理念：高信息密度，快速筛选**
- Overview：一屏 4~6 个图表（情感分布、趋势、词云、来源分布并排）
- CommentsList：紧凑型表格，左侧/顶部筛选器集中，支持快速标注
- 表格行间距可以比用户端更紧凑（`size="small"`）

### 7.3 管理员（/admin/）

- **核心理念：控制感，状态一目了然**
- Dashboard：系统级 StatCard（用户总数、日活、总分析次数）
- ModelManage：每个模型一张卡片，显示状态标签（已激活/待机/不兼容）
- TrainingCenter：进度指示器、状态标签（排队中→执行中→成功/失败）颜色鲜明
- 操作需要确认弹窗（角色变更、模型切换等高危操作）

---

## 八、Element Plus 覆盖变量（已在 index.css 中）

当前已有的覆盖基本正确，建议微调：

```css
:root {
  --primary: 224 71.4% 45.1%;       /* 从偏黑换为 indigo-600 */
  --radius: 0.75rem;                 /* 从 0.5rem 提升到 12px */
  --background: 210 40% 98%;         /* 从纯白换为 slate-50 */
}
```

---

## 九、执行优先级

| 优先级 | 任务 | 影响范围 |
|--------|------|----------|
| P0 | 修改 `index.css` 全局变量（主色、背景、圆角） | 全站 |
| P1 | 重构 StatCard / AppPanel 组件 | 所有 Dashboard |
| P2 | 统一 ECharts 主题色和 Tooltip 样式 | 所有图表 |
| P3 | 重构 UserLayout / AnalystLayout / AdminLayout 侧边栏 | 导航体验 |
| P4 | 逐页面调整间距和排版 | 各页面 |

---

## 十、设计决策总结

| 维度 | 决策 |
|------|------|
| 主色 | Indigo-600（科技蓝） |
| 背景 | Slate-50（柔和浅灰） |
| 情感色 | 绿/红/黄（emerald/rose/amber） |
| 圆角 | 12px（卡片/输入框） |
| 侧边栏 | 深色（已有，保持） |
| 图表风格 | 去噪、虚线网格、统一 Tooltip |
| 数字 | 等宽 tabular-nums |
