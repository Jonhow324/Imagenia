# Imagenia 技术设计

- 日期：2026-09-22
- 状态：设计已确认，尚未进入实现

## 1. 模块边界

```text
plugin.py
├── config       全局配置读取、保存和脱敏状态
├── api          HTTP 路由与请求校验
├── jobs         SQLite 任务队列和单 worker
├── provider     OpenAI Images API 适配器
├── assets       图片文件存储与 ImageAsset 服务
├── repositories SQLite Repository 和迁移
└── frontend     单页面生成、编辑、瀑布流工作台
```

前端不能直接调用 OpenAI、读取 API Key、访问 SQLite 或本地文件。所有操作经过后端 API。

## 2. 数据模型

### `image_assets`

```text
id                 UUID 主键
kind               generated | edited
source_asset_id    可空，直接来源资产
prompt             可空，删除资产时清除
model              使用的默认模型
size               square | landscape | portrait
quality            standard | high
width              整数
height             整数
file_path          插件数据目录下的相对路径
mime_type          例如 image/png
file_size          字节数
is_favorite        布尔值
favorited_at      可空时间
created_at         时间
updated_at         时间
```

索引：`(created_at DESC, id DESC)`、`(is_favorite, created_at DESC, id DESC)`、`source_asset_id`。

### `generation_jobs`

```text
id                 UUID 主键
kind               generate | edit
status             pending | running | succeeded | failed
source_asset_id    可空
result_asset_id    可空
prompt             执行期间保存，资产删除后清除
request_json       执行期间保存，完成后按隐私策略清理
error_code         可空稳定错误码
error_message      可空用户安全文案
error_detail       可空，仅写日志或受限诊断
created_at         时间
started_at         可空时间
finished_at        可空时间
```

任务与资产是一对零或一：一个任务最多产生一个结果资产。

## 3. API 契约

```text
POST  /api/imagenia/jobs/generate
POST  /api/imagenia/jobs/edit
GET   /api/imagenia/jobs/{job_id}
GET   /api/imagenia/assets?limit=30&cursor=...&favorite=true&kind=edited
GET   /api/imagenia/assets/{asset_id}
GET   /api/imagenia/assets/{asset_id}/content
PATCH /api/imagenia/assets/{asset_id}
DELETE /api/imagenia/assets/{asset_id}
GET   /api/imagenia/settings
PUT   /api/imagenia/settings/openai
POST  /api/imagenia/settings/openai/test
```

创建任务返回 `202 Accepted`：

```json
{"job_id":"uuid","status":"pending"}
```

列表使用 `created_at DESC, id DESC` 的不透明游标，每页默认 30 条。收藏通过 PATCH 更新 `is_favorite`。删除会移除文件和资产，解除后代来源引用，并保留脱敏的最小任务记录。

## 4. Worker 生命周期

插件启动时：

1. 执行未应用的 SQLite 迁移；
2. 将遗留 `running` 任务标记为 `failed/interrupted`；
3. 恢复 `pending` 任务；
4. 启动一个串行 worker。

单任务超时 10 分钟，最多 50 个 `pending` 任务，超出返回 `429`。不自动重试。

## 5. 前端状态与 UI 基线

单页面包含生成/编辑表单、任务状态、瀑布流和详情面板。前端提交后每 1～2 秒轮询 Job；成功后更新并高亮新资产，不自动打开详情。编辑只能从已有资产详情进入，并创建新资产。

第一版表单只开放提示词、`square/landscape/portrait` 和 `standard/high`。模型由后端配置，不允许用户自由输入。

实现功能页面前先建立独立的 UI 基线：确定工作台信息架构、关键流程线框、颜色与间距等设计令牌，以及按钮、输入框、图片卡片、任务状态、详情面板和确认对话框的组件规范。设计必须覆盖空状态、加载、排队、生成中、失败、无配置、无结果和删除确认，不应只规定一组视觉风格。

第一版采用 **shadcn/ui 风格**，但不把它理解为简单套用组件。shadcn/ui 提供可组合、可访问且可直接定制的组件基础；Imagenia 应在此基础上形成自己的图片工作台界面，而不是引入一套无法修改的黑盒主题。

### UI 设计约束

- **视觉基线**：使用中性灰阶、细边框、适度圆角、低强度阴影和清晰的 primary/destructive 状态；支持浅色和深色主题，但第一版优先保证浅色主题。
- **布局**：桌面端采用左侧生成控制区、右侧资料库的双栏布局；详情使用 `Sheet` 或 `Dialog`；窄屏退化为上下单列。
- **组件**：优先使用或仿照 shadcn/ui 的 `Button`、`Textarea`、`Select`、`Card`、`Badge`、`Tabs`、`Sheet`、`Dialog`、`Alert`、`Skeleton`、`Toast` 和 `Tooltip`。组件应保留源码并允许 Imagenia 定制。
- **图片内容**：图片是页面主角，卡片不堆叠过多文字；收藏、编辑和删除使用图标按钮，但必须提供 `Tooltip`、可访问名称和明确的确认反馈。
- **状态**：必须设计未配置、空资料库、加载、排队、生成中、成功、失败、无结果和删除确认，不允许只设计成功态。
- **交互**：生成按钮在请求期间显示 loading 和禁用状态；任务卡显示状态和错误摘要；成功后刷新并高亮新资产；删除使用 `AlertDialog` 二次确认。
- **可访问性**：保留键盘焦点、语义化表单标签、足够的颜色对比度和不依赖颜色的状态表达。

### 第一版页面与组件清单

1. **工作台页**：`Sidebar`/顶部工具栏、生成表单、任务状态列表、资料库筛选栏和瀑布流。
2. **生成表单**：提示词 `Textarea`、画幅 `Select`、质量 `Select`、生成 `Button`、配置缺失 `Alert`。
3. **资产卡片**：图片、收藏 `Button`、状态 `Badge`、详情入口；悬停操作不应是唯一操作方式。
4. **详情面板**：图片预览、提示词、尺寸、模型、创建时间、来源资产、编辑/收藏/删除操作。
5. **通用状态**：`Skeleton`、空状态插画或占位区、错误 `Alert`、成功/失败 `Toast`。

具体组件名称以目标前端技术栈的 shadcn/ui 实现为准；如果 QwenPaw 前端不是 React，不强行引入 React，而是复用同样的设计令牌、组件行为和视觉规则。
