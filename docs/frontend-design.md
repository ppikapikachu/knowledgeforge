# AI 面试题库系统

## Vue3 管理后台完整设计文档 V1.0

> 本文用于指导 Claude Code 完成 AI 面试题库系统管理后台 Web。
>
> 开发目标：
>
> 构建一个专业、清晰、现代化的桌面端管理后台，用于管理知识库、面试题库、知识关系以及文档导入任务。
>
> 后端当前已经完成 V1.0 基础能力：
>
> * 管理员登录
> * JWT 认证
> * 知识点 CRUD
> * 知识点关系
> * 题目 CRUD
> * 文件导入任务
> * Dashboard 统计
>
> 后端现有 API 以 `/api/v1` 为前缀，Swagger 可用于核对实际接口。后端 README 已列出认证、知识点、题目、导入任务和 Dashboard API。
>
> 当前阶段：
>
> **先完成 Vue3 管理后台，不开发 Flutter，不开发 AI Agent。**

---

# 1. 项目定位

这是一个：

> **AI 面试题库与知识库管理系统**

当前管理后台面向：

```text
管理员
```

主要工作：

```text
管理知识
管理题目
管理知识关系
导入题库文档
查看导入任务
查看系统数据
```

未来才会加入：

```text
AI 知识提取
AI 知识去重
AI 知识关系
AI 题目生成
AI 题目评价
```

因此当前界面应该：

> **像一个专业的知识库 / 内容运营 / AI 数据管理后台，而不是普通 CRUD Demo。**

---

# 2. 技术栈

必须使用：

```text
Vue 3
TypeScript
Vite
Element Plus
Vue Router
Pinia
Axios
```

建议：

```text
ESLint
Prettier
```

图标优先使用：

```text
Lucide
```

或者项目已有的可靠 SVG 图标方案。

---

# 3. UI/UX 设计工具

当前项目使用：

```text
UI UX Pro Max
```

GitHub：

```text
https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
```

该 Skill 当前支持 Vue 技术栈，并提供 Design System Generation、视觉风格、配色、字体、图表、UX guidelines 和 anti-pattern 等设计能力。

---

# 4. UI/UX Pro Max 使用要求

这是本项目非常重要的一项要求。

**不要直接开始写页面。**

Claude Code 在开始实现页面之前必须先使用 UI/UX Pro Max 对项目进行设计分析。

先完成：

```text
产品类型判断
↓
设计风格
↓
Design System
↓
颜色
↓
字体
↓
间距
↓
圆角
↓
阴影
↓
组件层级
↓
页面布局
↓
交互状态
```

然后再开始代码实现。

---

# 5. 产品类型判断

将当前项目识别为：

```text
B2B SaaS / Knowledge Management / AI Operations Admin
```

属于：

```text
知识库管理
内容管理
题库管理
AI 数据管理
```

而不是：

```text
营销官网
电商
社交
博客
个人 Dashboard
```

---

# 6. 推荐设计方向

整体视觉建议：

```text
现代
专业
克制
清晰
高信息密度
易操作
```

优先考虑：

```text
Minimalism
Modern SaaS
Editorial / Knowledge Management
Professional Dashboard
```

不建议过度使用：

```text
Glassmorphism
Neumorphism
大面积渐变
强烈霓虹色
过多动画
大量装饰性卡片
```

界面重点应该放在：

```text
数据
层级
信息结构
操作效率
```

---

# 7. AI 产品视觉不要俗套

这是一个 AI 项目。

但是：

**不要默认使用紫色渐变 + 星空 + 发光 AI 背景。**

AI 相关区域可以通过：

```text
AI 图标
AI 状态
智能标签
任务状态
轻量强调色
```

体现 AI 属性。

不要让整个后台变成：

```text
“AI 炫技网站”
```

---

# 8. UI/UX 设计原则

必须考虑：

```text
信息密度
视觉层级
可读性
响应式
键盘操作
焦点状态
加载状态
空状态
错误状态
成功状态
禁用状态
```

交互必须明确：

```text
hover
active
focus
disabled
loading
success
error
empty
```

不要只实现“正常状态”。

---

# 9. 响应式目标

后台主要针对桌面端。

优先：

```text
1440 × 900
1920 × 1080
1366 × 768
```

同时保证至少：

```text
1024px
```

下不会严重破坏布局。

不要过度追求手机端。

这是：

```text
Admin Web
```

不是移动端 Web App。

---

# 10. 整体布局

采用经典后台结构，但需要做得现代一些：

```text
┌──────────────────────────────────────────────────────────┐
│ Logo / 项目名称        面包屑         管理员 / 用户菜单 │
├───────────────┬──────────────────────────────────────────┤
│               │                                          │
│ Dashboard     │                                          │
│               │                                          │
│ 知识库        │               页面内容                   │
│  ├ 知识点     │                                          │
│  └ 知识关系   │                                          │
│               │                                          │
│ 题库          │                                          │
│  └ 题目       │                                          │
│               │                                          │
│ 导入任务      │                                          │
│               │                                          │
│ 系统          │                                          │
│  └ 管理员     │                                          │
│               │                                          │
└───────────────┴──────────────────────────────────────────┘
```

---

# 11. 左侧 Sidebar

要求：

```text
固定
可折叠
```

展开：

```text
Dashboard

知识库
  知识点
  知识关系

题库
  题目

导入任务

系统
  管理员
```

当前管理员功能很少，所以不要制造过多菜单层级。

---

# 12. 顶部 Header

包含：

```text
面包屑
当前页面标题
管理员头像
管理员昵称
下拉菜单
退出登录
```

可以预留：

```text
通知入口
```

但当前没有通知功能，可以暂不启用。

---

# 13. 页面内容区

内容区域应该：

```text
padding
```

统一。

建议：

```text
24px
```

页面最大宽度不要过于限制。

Dashboard 可以充分利用屏幕宽度。

---

# 14. 路由结构

推荐：

```text
/
├── /login
│
└── /dashboard
    ├── /overview
    │
    ├── /knowledge
    ├── /knowledge/create
    ├── /knowledge/:id
    ├── /knowledge/:id/edit
    │
    ├── /knowledge-relations
    │
    ├── /questions
    ├── /questions/create
    ├── /questions/:id
    ├── /questions/:id/edit
    │
    ├── /import-tasks
    ├── /import-tasks/:id
    │
    └── /admin
```

---

# 15. 登录页

路由：

```text
/login
```

功能：

```text
用户名
密码
登录
```

布局不要做成：

```text
传统后台白色表单 + 大 Logo
```

应该有一定产品感。

但不要设计复杂营销式登录页。

推荐：

```text
左侧品牌/产品介绍
右侧登录表单
```

或者：

```text
居中登录卡片
+
简洁背景
```

由 UI/UX Pro Max 最终确定。

---

# 16. 登录页交互

支持：

```text
输入校验
密码显示/隐藏
登录 loading
登录失败提示
网络错误提示
```

登录成功：

```text
保存 access_token
获取管理员信息
跳转 Dashboard
```

---

# 17. Token 管理

Axios 请求自动加入：

```http
Authorization: Bearer <token>
```

如果：

```text
401
```

则：

```text
清除 Token
清除管理员状态
跳转 /login
```

避免重复请求。

---

# 18. Dashboard

这是管理员进入系统后的首页。

不要单纯做：

```text
四个数字卡片
```

应该体现：

> 当前题库和知识库的整体状态。

---

# 19. Dashboard 第一层

顶部统计：

```text
知识点总数
题目总数
单选题
多选题
判断题
简答题
导入任务
```

不要全部设计成巨大卡片。

根据设计系统可以采用：

```text
Metric Cards
+
Compact Stats
```

---

# 20. Dashboard 第二层

推荐：

```text
题目类型分布
知识库规模
```

可以使用图表。

例如：

```text
题型分布
```

建议：

```text
Donut / Pie
```

题目总量：

```text
Trend / Bar
```

如果后端暂时没有历史数据：

**不要伪造趋势数据。**

可以只展示：

```text
当前统计
```

---

# 21. Dashboard 第三层

显示：

```text
最近导入任务
最近创建知识点
最近创建题目
```

例如：

```text
最近导入
━━━━━━━━━━━━━━━━━━━━
Android面试题.pdf     SUCCESS
Java面试题.docx        RUNNING
Flutter面试题.pdf      FAILED
```

---

# 22. Dashboard 空状态

例如没有数据：

```text
暂无知识点
```

不要留下巨大的空白区域。

应该：

```text
图标
说明
操作建议
```

例如：

```text
还没有知识点
先创建第一个知识点
[创建知识点]
```

---

# 23. 知识点列表页

路由：

```text
/knowledge
```

这是最重要的管理页面之一。

---

# 24. 页面结构

推荐：

```text
页面标题
说明
                  [新增知识点]

筛选区
────────────────────────────────────
搜索
难度
状态
来源
[搜索] [重置]

数据表
────────────────────────────────────
知识点名称
摘要
难度
来源
状态
题目数
更新时间
操作

分页
```

---

# 25. 搜索

搜索：

```text
知识点名称
```

前端对应：

```text
GET /api/v1/knowledge
```

参数：

```text
page
page_size
keyword
difficulty
status
```

后端 README 已提供这些筛选能力。

---

# 26. 知识点列表

字段建议：

```text
名称
摘要
难度
来源
状态
关联题目数量
更新时间
```

来源显示：

```text
手工
导入
AI
```

难度不要只显示：

```text
1
2
3
```

而应该转换为：

```text
简单
中等
困难
```

---

# 27. 状态展示

状态不能只依赖颜色。

例如：

```text
● 正常
● 禁用
```

需要：

```text
文字 + Badge
```

同时保证无障碍和色盲情况下仍能理解。

---

# 28. 知识点操作

行操作：

```text
查看
编辑
关系
禁用
```

危险操作需要：

```text
确认弹窗
```

不要点击删除后直接执行。

---

# 29. 知识点编辑页

路由：

```text
/knowledge/create
/knowledge/:id/edit
```

表单：

```text
名称
摘要
详细内容
难度
状态
来源
关键词
```

---

# 30. content 编辑器

知识内容是重要数据。

不要只使用一个非常小的 textarea。

建议：

```text
Textarea
```

或者：

```text
Markdown Editor
```

如果项目暂时不引入额外编辑器：

第一版可以使用：

```text
多行 textarea
```

但页面必须给足可编辑空间。

---

# 31. keywords

使用 Tag 输入。

例如：

```text
ThreadPoolExecutor
线程池
Java并发
```

允许：

```text
输入
Enter
生成 Tag
删除
```

---

# 32. 知识点详情

路由：

```text
/knowledge/:id
```

建议使用：

```text
基本信息
详细内容
关键词

知识关系
├ 前置知识
├ 相关知识
├ 扩展知识
└ 对比知识

关联题目
```

这是知识管理的核心详情页。

---

# 33. 知识关系 UI

不要做成简单的：

```text
source
target
type
```

虽然数据层是这样。

UI 上要具有：

```text
知识关系可视化
```

但 V1.0 不需要复杂图谱。

可以：

```text
左侧当前知识点
右侧关系列表
```

例如：

```text
Java线程池

前置知识
┌───────────────────┐
│ Java多线程        │
└───────────────────┘

相关知识
┌───────────────────┐
│ synchronized      │
└───────────────────┘
```

后期再增加真正知识图谱。

---

# 34. 添加知识关系

弹窗：

```text
目标知识点
关系类型
```

关系：

```text
前置知识
相关知识
扩展知识
对比知识
```

交互：

```text
选择知识点
+
选择关系
+
确认
```

---

# 35. 题目列表

路由：

```text
/questions
```

结构：

```text
页面标题                           [新增题目]

筛选
题型
难度
状态
来源
知识点
关键词
[搜索] [重置]

题目列表

题目
题型
难度
来源
状态
关联知识点
质量
使用次数
更新时间
操作
```

---

# 36. 题目列表不要显示完整长文本

如果题目很长：

```text
最多显示 1~2 行
```

超出：

```text
ellipsis
```

点击进入详情。

不要让表格被超长题目撑爆。

---

# 37. 题型视觉

使用：

```text
Tag / Badge
```

例如：

```text
单选题
多选题
判断题
简答题
```

不要全部使用相同颜色。

但不要为了区分题型使用过多颜色。

---

# 38. 题目详情

建议：

```text
题目内容

题型
难度
状态
来源

选项

正确答案

题目解析

关联知识点

质量评分
使用次数
正确次数
```

---

# 39. 新增题目

路由：

```text
/questions/create
```

必须根据：

```text
question_type
```

动态改变表单。

---

# 40. 单选题

显示：

```text
题目内容

选项
A
B
C
D

正确答案
```

允许：

```text
新增选项
删除选项
调整顺序
```

只能选择一个正确答案。

---

# 41. 多选题

显示：

```text
A
B
C
D
```

可以选择多个正确答案。

---

# 42. 判断题

只显示：

```text
题目内容

正确答案：
○ 正确
○ 错误
```

不要显示选项编辑器。

---

# 43. 简答题

显示：

```text
题目内容
标准答案
解析
```

不显示选项。

---

# 44. 题目与知识点关联

使用：

```text
多选 Select
```

或者：

```text
可搜索 Cascader / Select
```

允许一个题目关联多个知识点。

---

# 45. 题目表单校验

前端必须校验。

例如：

```text
题目不能为空
难度必须有效
单选必须且只能有一个正确答案
多选至少一个正确答案
判断题不能出现 options
简答题答案不能为空
```

但是：

> 前端校验不能取代后端校验。

后端仍然是最终数据约束。

---

# 46. 导入任务页面

路由：

```text
/import-tasks
```

---

# 47. 导入页面顶部

提供：

```text
[上传题库]
```

支持：

```text
PDF
DOCX
TXT
MD
```

后端已经提供上传任务接口。

---

# 48. 文件上传 UX

不要只使用 Element Plus 默认 Upload 样式。

需要体现：

```text
拖拽上传
点击上传
文件格式
文件大小限制
上传状态
```

例如：

```text
┌──────────────────────────────┐
│                              │
│       拖拽文件到这里          │
│                              │
│    或 点击选择文件            │
│                              │
│ PDF / DOCX / TXT / MD        │
│                              │
└──────────────────────────────┘
```

---

# 49. 上传成功

上传成功后：

```text
创建 Import Task
```

跳转：

```text
/import-tasks/:id
```

或者进入任务详情。

---

# 50. 导入任务列表

字段：

```text
文件名
文件类型
文件大小
状态
进度
当前步骤
创建人
创建时间
完成时间
操作
```

状态：

```text
PENDING
RUNNING
SUCCESS
PARTIAL_SUCCESS
FAILED
CANCELLED
```

使用：

```text
Badge
Progress
```

---

# 51. 导入任务详情

这是后续 Agent 最重要的页面之一。

因此 V1.0 就应该把它设计好。

页面：

```text
文件信息
        ↓
任务状态
        ↓
处理进度
        ↓
当前步骤
        ↓
错误信息
```

例如：

```text
Android面试题.pdf

● RUNNING

━━━━━━━━━━━━━━━━━━ 62%

当前步骤
正在处理知识点

处理阶段
✓ 文件解析
✓ 文本提取
● 知识点处理
○ 题目处理
○ 完成
```

---

# 52. 模拟任务

后端当前提供：

```text
POST /api/v1/import-tasks/{id}/simulate
```

因此 V1.0 前端可以提供：

```text
[模拟执行]
```

但它只能作为：

```text
开发 / 测试功能
```

不要设计成正式业务核心入口。

后续真正接 Agent 后，这个按钮会被真正的：

```text
开始处理
```

或者：

```text
Agent Workflow
```

取代。

---

# 53. 状态轮询

当前后端没有 Redis/WebSocket。

因此 V1.0：

```text
前端轮询
```

例如：

```text
RUNNING
 ↓
每 2 秒
GET /import-tasks/{id}
 ↓
更新 progress
```

任务完成：

```text
SUCCESS / FAILED / CANCELLED
```

立即停止轮询。

---

# 54. 不要为了任务状态引入 WebSocket

V1.0 不需要：

```text
WebSocket
SSE
Redis
```

简单轮询已经够用。

---

# 55. 管理员页面

路由：

```text
/admin
```

第一版只需要：

```text
当前管理员信息
用户名
昵称
最后登录时间
```

可以提供：

```text
退出登录
```

暂时不要做：

```text
复杂 RBAC
角色管理
权限矩阵
```

---

# 56. API 层结构

建议：

```text
src/
├── api/
│   ├── auth.ts
│   ├── knowledge.ts
│   ├── question.ts
│   ├── importTask.ts
│   └── dashboard.ts
```

不要：

```text
页面组件里直接 axios
```

页面：

```text
View
 ↓
API
 ↓
Axios
 ↓
Backend
```

---

# 57. Axios 封装

建立：

```text
src/utils/request.ts
```

实现：

```text
baseURL
token
request interceptor
response interceptor
401 handling
统一错误处理
```

---

# 58. 环境变量

使用：

```text
.env.development
.env.production
```

例如：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

不要把后端地址写死到业务文件里。

---

# 59. 类型设计

使用 TypeScript Interface。

例如：

```ts
interface Knowledge {
  id: number
  name: string
  summary?: string
  content?: string
  difficulty: number
  status: number
  source_type: string
  keywords?: string[]
}
```

API Response 也要类型化。

不要大量使用：

```ts
any
```

---

# 60. API 类型

建议建立：

```text
src/types/
├── auth.ts
├── knowledge.ts
├── question.ts
├── importTask.ts
└── dashboard.ts
```

保持前端数据模型清晰。

---

# 61. Pinia

第一版至少建立：

```text
authStore
```

负责：

```text
token
admin
login
logout
```

不要把所有页面的数据全部扔进 Pinia。

例如：

```text
知识点列表
题目列表
导入任务列表
```

这些属于页面状态。

---

# 62. 页面状态管理

每个页面必须考虑：

```text
loading
success
error
empty
```

例如知识点列表：

```text
Loading
↓
成功有数据
↓
Empty
```

不是只有：

```text
Table
```

---

# 63. Empty State

每个主要列表页面都必须设计 Empty State。

例如：

```text
暂无知识点

还没有创建知识点
先创建第一个知识点吧

[创建知识点]
```

---

# 64. Loading

使用：

```text
Skeleton
```

或者适当的：

```text
Loading
```

不要页面打开后长时间一片空白。

---

# 65. Error

API 请求失败：

```text
明确提示
```

不要只显示：

```text
Request failed
```

例如：

```text
获取知识点失败，请稍后重试
```

同时支持：

```text
重试
```

---

# 66. 删除 / 禁用交互

所有危险操作：

```text
确认弹窗
```

例如：

```text
确认禁用“Java线程池”？

禁用后将不会继续用于正常题库管理。
[取消] [确认禁用]
```

按钮文字要表达实际动作。

不要统一使用：

```text
确定
取消
```

---

# 67. Toast

成功：

```text
知识点创建成功
```

失败：

```text
知识点创建失败
```

不要频繁弹出不重要的 Toast。

---

# 68. 表格设计

不要过度使用边框。

推荐：

```text
轻边框
适当行高
Hover
固定操作列
```

操作列：

```text
查看
编辑
更多
```

避免一行塞 7 个按钮。

---

# 69. 表格分页

所有分页：

```text
page
page_size
total
```

与后端统一。

后端统一返回：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 100
}
```

前端统一分页组件。

---

# 70. 表格排序

如果后端当前没有排序 API：

不要在前端做假排序。

需要排序时：

```text
先更新 API
```

再实现。

不要让 UI 与实际数据能力脱节。

---

# 71. Dashboard 图表

如果使用 ECharts 或其他图表库：

必须确认：

```text
当前后端确实提供对应数据
```

没有数据的图表：

```text
不要伪造
```

宁可：

```text
暂无数据
```

---

# 72. 图标要求

不要使用：

```text
emoji
```

作为导航图标。

例如不要：

```text
📚 知识库
📝 题库
🤖 AI
```

应该使用：

```text
SVG icon
```

例如：

```text
BookOpen
FileText
Upload
Database
Settings
```

UI/UX Pro Max 当前设计检查项本身也强调不要用 emoji 代替 UI 图标。

---

# 73. 动画

后台不是展示型网站。

动画应该：

```text
少
快
有意义
```

主要：

```text
hover
dropdown
drawer
modal
page transition
loading
```

不要：

```text
粒子背景
大面积浮动
强烈视差
自动播放动画
```

---

# 74. 深色模式

V1.0：

```text
默认浅色
```

暂时不做完整深色模式。

不要为了“高级感”强行增加 Dark Mode。

如果 UI/UX Pro Max 推荐 Dark Mode，也要考虑本项目属于高信息密度后台，默认优先 Light。

---

# 75. 颜色

最终具体颜色由：

```text
UI/UX Pro Max Design System
```

确定。

要求：

```text
主色稳定
成功/警告/错误状态颜色明确
对比度合格
不要彩虹配色
```

尤其避免：

```text
AI 紫粉渐变
```

作为整个后台主色。

---

# 76. 字体

中文后台优先：

```text
系统中文字体
```

英文数字：

```text
合理 Sans-serif
```

不要为了视觉效果使用难阅读的装饰字体。

---

# 77. 圆角

统一设计系统。

不要出现：

```text
按钮 4px
卡片 20px
弹窗 32px
输入框 2px
```

这种混乱情况。

---

# 78. 间距

所有页面遵循统一 spacing system。

推荐：

```text
4
8
12
16
20
24
32
```

不要大量出现：

```text
17px
23px
29px
```

随机间距。

---

# 79. 页面复用

建立公共组件：

```text
AppLayout
PageHeader
SearchToolbar
DataTable
EmptyState
LoadingState
ConfirmDialog
StatusBadge
DifficultyBadge
Pagination
```

但不要为了复用而抽象成非常复杂的“万能组件”。

---

# 80. 知识点通用组件

建议：

```text
KnowledgeForm
KnowledgeDetail
KnowledgeRelationList
KnowledgeSelector
```

---

# 81. Question 通用组件

建议：

```text
QuestionForm
QuestionOptionEditor
QuestionTypeSelector
QuestionDetail
QuestionKnowledgeSelector
```

---

# 82. Import Task 通用组件

建议：

```text
FileUploader
TaskStatusBadge
TaskProgress
TaskStepTimeline
```

---

# 83. 目录结构

建议：

```text
admin-web/
├── src/
│   ├── api/
│   │   ├── auth.ts
│   │   ├── knowledge.ts
│   │   ├── question.ts
│   │   ├── importTask.ts
│   │   └── dashboard.ts
│   │
│   ├── assets/
│   │
│   ├── components/
│   │   ├── layout/
│   │   ├── common/
│   │   ├── knowledge/
│   │   ├── question/
│   │   └── import-task/
│   │
│   ├── layouts/
│   │   └── AdminLayout.vue
│   │
│   ├── router/
│   │   └── index.ts
│   │
│   ├── stores/
│   │   └── auth.ts
│   │
│   ├── types/
│   │   ├── auth.ts
│   │   ├── knowledge.ts
│   │   ├── question.ts
│   │   ├── importTask.ts
│   │   └── dashboard.ts
│   │
│   ├── utils/
│   │   ├── request.ts
│   │   └── storage.ts
│   │
│   ├── views/
│   │   ├── login/
│   │   ├── dashboard/
│   │   ├── knowledge/
│   │   ├── question/
│   │   ├── import-task/
│   │   └── admin/
│   │
│   ├── App.vue
│   └── main.ts
│
├── public/
├── .env.development
├── .env.production
├── package.json
├── vite.config.ts
└── README.md
```

---

# 84. API 映射

当前后端接口：

```text
认证

POST /api/v1/auth/login
GET  /api/v1/auth/me
```

知识：

```text
GET    /api/v1/knowledge
GET    /api/v1/knowledge/{id}
POST   /api/v1/knowledge
PUT    /api/v1/knowledge/{id}
DELETE /api/v1/knowledge/{id}

GET    /api/v1/knowledge/{id}/relations
POST   /api/v1/knowledge/{id}/relations
DELETE /api/v1/knowledge/{id}/relations/{relation_id}
```

题目：

```text
GET    /api/v1/questions
GET    /api/v1/questions/{id}
POST   /api/v1/questions
PUT    /api/v1/questions/{id}
DELETE /api/v1/questions/{id}
```

导入：

```text
POST /api/v1/import-tasks
GET  /api/v1/import-tasks
GET  /api/v1/import-tasks/{id}
POST /api/v1/import-tasks/{id}/simulate
```

Dashboard：

```text
GET /api/v1/dashboard/overview
```

这些接口对应后端当前 V1.0 README 的 API 能力。

---

# 85. 统一 API Response

前端按照：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

处理。

如果：

```text
code != 0
```

统一走错误提示。

分页：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 100
}
```

---

# 86. 不允许擅自修改后端 API

前端开发时：

如果发现 API 返回结构与设计文档不一致：

1. 先检查 Swagger。
2. 以实际后端接口为准。
3. 如果确实存在问题，再修改后端。
4. 不要在前端大量写兼容代码掩盖后端问题。

---

# 87. 第一阶段开发顺序

不要一次性实现全部页面。

严格：

```text
1. 初始化 Vue3
2. 安装 Element Plus
3. 路由
4. Pinia
5. Axios
6. UI/UX Pro Max Design System
7. Login
8. Admin Layout
9. Dashboard
10. Knowledge
11. Knowledge Relation
12. Question
13. Import Task
14. Admin
15. 全局状态优化
16. 全面测试
```

---

# 88. 第一阶段：UI/UX Design System

Claude Code 必须先完成：

```text
Design System
```

并在项目文档中保存，例如：

```text
docs/ui-design-system.md
```

记录：

```text
视觉风格
主色
辅助色
背景色
文字色
字体
字号
圆角
阴影
间距
按钮规范
表格规范
状态规范
图标规范
动画规范
```

不要只在聊天里告诉我设计方案。

需要落地为项目文档。

---

# 89. 第二阶段：基础框架

完成：

```text
Login
AdminLayout
Sidebar
Header
Breadcrumb
```

并确保：

```text
登录
Token
路由守卫
退出
```

真实可运行。

---

# 90. 第三阶段：Dashboard

完成：

```text
统计
最近任务
最近知识点
最近题目
```

所有数据来自真实 API。

禁止 mock 长期留在项目中。

开发时可以短暂 mock，但联调后必须替换。

---

# 91. 第四阶段：Knowledge

完整实现：

```text
列表
搜索
筛选
新增
编辑
查看
禁用
关系
分页
空状态
错误状态
```

---

# 92. 第五阶段：Question

完整实现：

```text
列表
搜索
筛选
新增
编辑
查看
禁用
分页
```

并正确支持：

```text
单选
多选
判断
简答
```

---

# 93. 第六阶段：Import Task

实现：

```text
上传
任务列表
任务详情
进度轮询
模拟任务
错误状态
```

---

# 94. 第七阶段：全面联调

必须真实启动：

```text
Vue
+
FastAPI
+
MySQL
```

然后验证：

```text
登录
知识点
知识关系
题目
导入任务
Dashboard
```

不能只检查页面能否打开。

---

# 95. 前端测试

至少验证：

```text
登录成功
登录失败
Token 过期
路由守卫
知识点 CRUD
关系 CRUD
题目 CRUD
不同题型
文件上传
任务轮询
Dashboard
退出登录
```

---

# 96. 错误处理

常见：

```text
401
403
404
409
422
500
```

必须有统一处理。

例如：

```text
401 → 返回登录页

404 → 页面/资源不存在提示

409 → 数据重复提示

422 → 参数错误

500 → 系统错误 + 重试
```

---

# 97. Loading / Empty / Error 全覆盖

每一个异步页面必须至少有：

```text
Loading
Success
Empty
Error
```

例如：

```text
知识点列表加载中
知识点列表为空
知识点请求失败
```

不能只实现 Success。

---

# 98. 最终质量要求

项目必须：

```text
无 TypeScript 明显错误
无控制台大量 warning
无明显布局错位
无溢出
无无效按钮
无假 API
无长期 Mock 数据
无明显重复代码
```

---

# 99. UI/UX Pro Max 最终检查

开发完成后，使用 UI/UX Pro Max 的设计检查能力进行审查。

重点检查：

```text
视觉一致性
色彩对比
按钮状态
焦点状态
响应式
文字换行
Tag / Badge
表格
空状态
Loading
Error
动画
图标
```

当前 Skill 文档明确包含响应式断点、无障碍、文本换行、Badge、动画和 anti-pattern 等检查项，应在最终验收阶段使用。

---

# 100. 禁止事项

禁止：

```text
使用 emoji 作为主要 UI 图标
大量渐变背景
大面积玻璃拟态
无意义动画
假数据长期存在
前端自己伪造后端能力
页面直接调用 axios
业务代码大量 any
所有页面全部堆 Card
一个页面塞大量操作按钮
手机端优先设计
```

---

# 101. 当前版本明确不实现

暂不做：

```text
AI Agent 页面
Agent Workflow 可视化
AI 生成题目
AI 评价
Embedding 管理
Vector DB 管理
Redis 管理
系统 RBAC
普通用户管理
Flutter
```

这些属于后续阶段。

---

# 102. 未来扩展预留

后续可能增加：

```text
AI 工作台
Agent 任务
知识图谱
题目生成
题目评价
模型配置
Prompt 管理
Token 统计
```

因此当前界面结构不要把：

```text
Sidebar
Dashboard
Knowledge
Question
Import Task
```

设计得无法扩展。

---

# 103. 前端交付标准

最终需要做到：

```text
[ ] Vue3 项目正常启动
[ ] TypeScript 正常
[ ] Element Plus 正常
[ ] UI/UX Design System 已落地
[ ] 登录正常
[ ] Token 正常
[ ] 路由守卫正常
[ ] Dashboard 正常
[ ] Knowledge 正常
[ ] Knowledge Relation 正常
[ ] Question 正常
[ ] Import Task 正常
[ ] Admin 正常
[ ] API 联调正常
[ ] Loading 正常
[ ] Empty 正常
[ ] Error 正常
[ ] 响应式正常
[ ] 无明显 UI/UX 问题
```

---

# 104. 给 Claude Code 的最终执行规则

开始开发前：

```text
1. 阅读本文
2. 阅读后端 README
3. 检查实际 API
4. 使用 UI/UX Pro Max 生成 Design System
5. 保存 Design System
6. 再开始编码
```

编码过程中：

```text
实现
↓
运行
↓
检查
↓
修复
↓
继续
```

不要一次生成全部页面后停止。

---

# 105. Claude Code 不允许做的事情

不要：

```text
擅自修改后端 API
擅自增加后端字段
擅自增加第三方库
擅自增加复杂状态管理
擅自引入 UI 框架
擅自使用 Mock 代替真实 API
```

如果确实发现当前后端 API 无法支持某个合理页面需求：

```text
先指出问题
再给出最小后端修改方案
然后继续开发
```

---

# 106. 最终启动

前端：

```bash
npm install
npm run dev
```

后端：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端通过：

```text
VITE_API_BASE_URL
```

连接后端。

---

# 107. 最终验收流程

必须实际完成：

```text
启动 FastAPI
↓
启动 Vue3
↓
登录
↓
进入 Dashboard
↓
创建知识点
↓
编辑知识点
↓
查看知识点
↓
创建知识关系
↓
创建单选题
↓
创建多选题
↓
创建判断题
↓
创建简答题
↓
修改题目
↓
上传题库文件
↓
查看 Import Task
↓
模拟任务
↓
查看任务进度
↓
Dashboard 查看统计
↓
退出登录
↓
重新登录
```

完成后才认为前端 V1.0 完成。

---

# 108. 最终交付报告

完成后输出：

## 1. 技术栈

## 2. 项目目录

## 3. Design System

## 4. 已完成页面

## 5. 已完成组件

## 6. API 对接情况

## 7. 测试情况

## 8. 已知问题

## 9. 后续建议

不得伪造测试结果。

实际没有验证的内容必须标记：

```text
未验证
```

---

# 109. 最核心原则

这个后台的目标不是：

> “把 Element Plus 组件拼起来。”

而是：

> **建立一个真正可以长期扩展的知识库 / 题库管理工作台。**

UI 应该服务于：

```text
管理知识
管理题目
发现问题
处理导入
查看系统状态
```

未来再逐渐加入：

```text
AI
Agent
知识图谱
智能题目生成
```

当前先把基础管理体验做扎实。

---

# 110. 开始执行

现在直接开始：

```text
读取后端 README
↓
检查 API
↓
使用 UI/UX Pro Max 生成 Design System
↓
初始化 Vue3 项目
↓
实现登录和后台 Layout
↓
实现 Dashboard
↓
实现 Knowledge
↓
实现 Question
↓
实现 Import Task
↓
实现 Admin
↓
真实联调
↓
测试
↓
修复
```

不要只输出实现计划。

**直接在当前项目目录实际创建和修改前端代码。**
