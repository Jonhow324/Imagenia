# ADR 0002：任务、API 与数据生命周期

- 状态：已接受
- 日期：2026-09-22

## 决策

1. 第一版使用 OpenAI Images API；服务调用通过适配器封装，未来可增加其他接口或服务商。
2. 收藏是 `ImageAsset` 的全局状态，第一版使用 `is_favorite` 和 `favorited_at`，不建立独立收藏表。
3. QwenPaw 启动时恢复 `pending` 任务；遗留的 `running` 任务标记为 `failed/interrupted`，不自动重试，避免重复生成和计费。
4. 删除资产时删除图片文件并解除后代资产的来源引用；保留脱敏的最小任务记录，清空提示词、完整请求参数和结果引用。
5. API Key 优先从 `IMAGENIA_OPENAI_API_KEY` 环境变量读取，其次从插件数据目录下权限为 `0600` 的私有配置文件读取。API 不返回完整密钥。
6. 使用异步 Job 资源和 Asset 资源：创建任务返回 `202 Accepted` 与 `job_id`，前端通过轮询读取状态。
7. SQLite 使用带版本号的前向迁移；每个迁移在事务中执行，迁移失败则阻止插件后端注册。

## API 资源

```text
POST  /api/imagenia/jobs/generate
POST  /api/imagenia/jobs/edit
GET   /api/imagenia/jobs/{job_id}
GET   /api/imagenia/assets
GET   /api/imagenia/assets/{asset_id}
GET   /api/imagenia/assets/{asset_id}/content
PATCH /api/imagenia/assets/{asset_id}
DELETE /api/imagenia/assets/{asset_id}
GET   /api/imagenia/settings
PUT   /api/imagenia/settings/openai
```
