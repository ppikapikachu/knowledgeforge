# KnowledgeForge UI Design System

## 设计风格

**Minimalism & Swiss Style**

- Clean, simple, spacious, functional
- White space, high contrast, geometric, sans-serif, grid-based, essential
- 适合：Enterprise apps, dashboards, documentation sites, SaaS platforms, professional tools

## 颜色系统

| Token | 色值 | 用途 |
|-------|------|------|
| `--color-primary` | `#1E40AF` | 主色调（蓝色） |
| `--color-on-primary` | `#FFFFFF` | 主色上的文字 |
| `--color-secondary` | `#3B82F6` | 辅助色 |
| `--color-on-secondary` | `#000000` | 辅助色上的文字 |
| `--color-accent` | `#D97706` | 强调色（琥珀色） |
| `--color-on-accent` | `#000000` | 强调色上的文字 |
| `--color-background` | `#F8FAFC` | 页面背景 |
| `--color-foreground` | `#1E3A8A` | 前景文字 |
| `--color-card` | `#FFFFFF` | 卡片背景 |
| `--color-card-foreground` | `#1E3A8A` | 卡片文字 |
| `--color-muted` | `#E9EEF6` | 次要背景 |
| `--color-muted-foreground` | `#475569` | 次要文字 |
| `--color-border` | `#DBEAFE` | 边框 |
| `--color-destructive` | `#DC2626` | 危险操作 |
| `--color-on-destructive` | `#FFFFFF` | 危险操作上的文字 |
| `--color-ring` | `#1E40AF` | 焦点环 |

### 状态颜色

| 状态 | 色值 | 用途 |
|------|------|------|
| Success | `#059669` | 成功状态 |
| Warning | `#D97706` | 警告状态 |
| Error | `#DC2626` | 错误状态 |
| Info | `#2563EB` | 信息状态 |

### 难度颜色

| 难度 | 色值 | 标签 |
|------|------|------|
| 简单 | `#059669` | Success |
| 中等 | `#D97706` | Warning |
| 困难 | `#DC2626` | Error |

## 字体系统

### 中文

```
-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif
```

### 英文/数字

```
'Fira Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif
```

### 代码

```
'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace
```

### 字号

| 级别 | 字号 | 行高 | 字重 | 用途 |
|------|------|------|------|------|
| h1 | 30px | 1.2 | 700 | 页面标题 |
| h2 | 24px | 1.3 | 600 | 区块标题 |
| h3 | 20px | 1.35 | 600 | 卡片标题 |
| h4 | 16px | 1.4 | 600 | 小标题 |
| body | 14px | 1.5 | 400 | 正文 |
| small | 12px | 1.5 | 400 | 辅助文字 |
| caption | 12px | 1.4 | 500 | 标签/Badge |

## 间距系统

基于 4px 网格：

| Token | 值 | 用途 |
|-------|-----|------|
| `--space-1` | 4px | 微间距 |
| `--space-2` | 8px | 小间距 |
| `--space-3` | 12px | 默认间距 |
| `--space-4` | 16px | 中等间距 |
| `--space-5` | 20px | 区块间距 |
| `--space-6` | 24px | 页面内边距 |
| `--space-8` | 32px | 大区块间距 |
| `--space-10` | 40px | 页面间距 |
| `--space-12` | 48px | 超大间距 |

## 圆角

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | 4px | 小元素（Badge、Tag） |
| `--radius-md` | 6px | 按钮、输入框 |
| `--radius-lg` | 8px | 卡片、弹窗 |
| `--radius-xl` | 12px | 大卡片 |

## 阴影

| Token | 值 | 用途 |
|-------|-----|------|
| `--shadow-sm` | `0 1px 2px 0 rgb(0 0 0 / 0.05)` | 轻微阴影 |
| `--shadow-md` | `0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)` | 卡片阴影 |
| `--shadow-lg` | `0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)` | 弹窗阴影 |

## 按钮规范

### Primary Button

- 背景：`--color-primary`（#1E40AF）
- 文字：`--color-on-primary`（#FFFFFF）
- 圆角：`--radius-md`（6px）
- 高度：36px（默认）/ 32px（小）/ 40px（大）
- 内边距：0 16px
- 字重：500
- Hover：背景色加深 10%
- Active：背景色加深 15%
- Disabled：opacity 0.5

### Secondary Button

- 背景：`--color-muted`（#E9EEF6）
- 文字：`--color-foreground`（#1E3A8A）
- 边框：`--color-border`（#DBEAFE）

### Text Button

- 背景：透明
- 文字：`--color-primary`（#1E40AF）
- Hover：背景 `--color-muted`

### Danger Button

- 背景：`--color-destructive`（#DC2626）
- 文字：`--color-on-destructive`（#FFFFFF）

## 表格规范

- 轻边框，适当行高（48px）
- Hover 行背景：`--color-muted`
- 固定操作列
- 分页统一在表格下方

## 状态规范

### Badge/Tag

- 使用文字 + 颜色，不仅依赖颜色
- 圆角：`--radius-sm`（4px）
- 字号：12px
- 字重：500
- 内边距：2px 8px

### 状态映射

| 状态 | 颜色 | 文字 |
|------|------|------|
| 正常/启用 | Success | 正常 |
| 禁用 | Muted | 禁用 |
| 运行中 | Info | 运行中 |
| 成功 | Success | 成功 |
| 失败 | Error | 失败 |
| 待处理 | Warning | 待处理 |

## 图标规范

- 图标库：**Lucide**（设计文档指定）
- 默认尺寸：16px（行内）/ 20px（按钮）/ 24px（导航）
- 颜色：跟随文字颜色
- 不使用 emoji 作为图标

## 动画规范

- 过渡时间：150-300ms
- 缓动函数：`cubic-bezier(0.4, 0, 0.2, 1)`
- 仅用于：hover、dropdown、drawer、modal、page transition、loading
- 禁止：粒子背景、大面积浮动、强烈视差、自动播放动画

## 响应式断点

| 断点 | 宽度 | 用途 |
|------|------|------|
| xs | 1024px | 最小支持 |
| sm | 1280px | 小桌面 |
| md | 1366px | 标准笔记本 |
| lg | 1440px | 标准桌面 |
| xl | 1920px | 大桌面 |

## 设计原则

1. **信息密度优先**：高密度后台，充分利用屏幕空间
2. **视觉层级清晰**：通过大小、间距、对比度建立层级
3. **操作效率**：减少操作步骤，提供快捷方式
4. **状态完整**：Loading、Empty、Error、Success 全覆盖
5. **无障碍**：对比度 4.5:1，键盘导航，焦点状态
6. **克制设计**：不使用 AI 炫技风格，保持专业克制
