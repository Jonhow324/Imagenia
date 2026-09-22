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

## 5. 前端状态

单页面包含生成/编辑表单、任务状态、瀑布流和详情面板。前端提交后每 1～2 秒轮询 Job；成功后更新并高亮新资产，不自动打开详情。编辑只能从已有资产详情进入，并创建新资产。

第一版表单只开放提示词、`square/landscape/portrait` 和 `standard/high`。模型由后端配置，不允许用户自由输入。
