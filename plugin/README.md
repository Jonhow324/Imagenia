# Imagenia QwenPaw 插件

Imagenia 是面向 QwenPaw 2.2.1 的本地 AI 图像工作台。当前仓库包含已经通过真实宿主验证的插件骨架，以及 React + Vite + Tailwind CSS + shadcn/ui 工作台。配置、生成和基于已有图片的编辑任务已接入插件 HTTP API；收藏和删除也已接入 HTTP API，仍需宿主验收。

## 前端工作台

前端源码位于 `plugin/frontend/src/`，构建产物分为两部分：

- `plugin/frontend/dist/index.js`：不引入工作台或第三方运行时的宿主薄入口。宿主通过 Blob `import()` 加载它，它使用 `window.QwenPaw.host.React` 注册 `/imagenia` 路由与侧边栏菜单，并渲染 iframe。
- `plugin/frontend/dist/app/index.html` 和 `assets/`：同源 iframe 中的独立 SPA，包含自己的 React/ReactDOM、shadcn/Radix、Tailwind CSS 和字体；静态资源使用相对路径，不与宿主共享 React dispatcher。入口 URL 为 `/api/frontend_plugin/imagenia/files/frontend/dist/app/index.html`。

`plugin.json` 仍以 `frontend/dist/index.js` 为插件入口。不要把工作台组件导入宿主入口，也不要将 iframe SPA 的 React 设为 external。当前 iframe 从同源插件 API 读取和保存全局 OpenAI 配置，使用 QwenPaw 2.2.1 的 `qwenpaw_auth_token` 发送 Bearer 认证；图片与任务使用后端资源；收藏、删除由同源接口处理。宿主联调还需验证实际 iframe 的读写鉴权与 401 反馈。

工作台沿用原型组件；生成表单、任务、图片资料库已接入真实后端：

- API Key 配置状态通过同源 HTTP API 读取，且缺失时禁用生成入口；
- 表单校验与生成、编辑任务提交；
- `pending`、`running`、`succeeded`、`failed` 任务；
- 经 Bearer 认证的图片加载、游标分页、收藏/类型筛选、空结果和加载更多失败重试；收藏状态可修改；
- 详情 Sheet；从详情进入图片编辑、追溯直接来源；收藏和删除已可使用（删除需确认）；
- 成功后刷新并高亮新资产，不自动打开详情。

本地预览：

```bash
cd plugin/frontend
npm install
npm run dev
```

类型检查和生产构建：

```bash
cd plugin/frontend
npm run typecheck
npm run build
```

`npm run build` 依次类型检查、构建 `dist/app/`、构建 `dist/index.js` 并运行产物与配置请求测试。`npm run test:build` 可以在已有产物上单独运行。将整个 `plugin/`（包括两个前端产物）同步到宿主后重启插件，在 QwenPaw 2.2.1 验证侧边栏、iframe 加载、交互与浏览器控制台。

Tailwind preflight 已关闭，选择器限制在 `.imagenia-root` 下；Select、Tooltip、Sheet 和 AlertDialog 使用工作台自己的 portal 容器。iframe 进一步隔离了工作台样式和宿主页面。

## 后端测试

在仓库根目录执行：

```bash
python -m pip install -r plugin/requirements-dev.txt
python -m pytest plugin/tests -q
```

常规测试显式注入 `FakeImageProvider`，不访问 OpenAI、不会产生费用；QwenPaw 正式插件入口使用真实 `OpenAIImageProvider`。真实宿主验证记录见 `plugin/docs/qwenpaw-2.2.1-verification.md`。

## 全局 OpenAI 配置（Issues #4、#12）

QwenPaw 管理员可在 iframe 工作台的“配置”中保存或覆盖一份全局 API Key。优先使用插件进程中的 `IMAGENIA_OPENAI_API_KEY` 环境变量；否则使用插件数据目录的 `config/openai.json`。该目录权限为 `0700`，文件权限为 `0600`。设置 API 返回 `configured`、`source`（`none`/`file`/`environment`）以及当前生效的 `base_url` 和 `model`，不返回密钥。配置面板可保存 API Key、base URL 和默认模型；不输入新密钥时保存其余字段不会清除已有密钥。`IMAGENIA_OPENAI_BASE_URL`、`IMAGENIA_OPENAI_MODEL` 也分别覆盖文件值；默认分别为 `https://api.openai.com/v1` 和 `gpt-image-2.5`。生成请求仍不得指定模型。若环境变量已配置，保存文件不会覆盖当前生效的环境变量。请勿把数据目录或密钥纳入 Git。

仅点击“测试连接”时后端才以当前生效密钥对当前 `base_url` 的 `GET /models` 发起一次只读认证请求（5 秒超时）；加载和保存配置都不会调用 OpenAI，测试不会请求图像生成。正式宿主中提交生成任务会调用 OpenAI Images API，**可能产生费用**。测试环境使用 fake provider 不会产生费用。

宿主验收：同步完整插件到 QwenPaw 2.2.1 后登录，打开 iframe；分别验证无配置、保存、覆盖、环境变量优先，以及点击测试连接的结果。登出或使登录 token 失效后，确认读取/写入遭宿主拒绝且页面显示安全的登录失效提示；本地 ASGI 测试不模拟宿主鉴权。

## 图片资料库（Issue #6）

`GET /api/imagenia/assets` 默认返回至多 30 条，可用 `limit=1..100` 指定每页大小，按 `created_at DESC, id DESC` 排序；返回 `items` 和可为空的 `next_cursor`。将该游标原样传给 `cursor` 查询参数继续加载；`cursor=` 或 `cursor=null` 等同首次请求，其余非法游标仍返回 `422`。`favorite=true` 仅看收藏；`kind=generated|edited` 筛选类型，两者可组合。参数无效时返回 `422`；筛选在后端执行，不仅针对已加载图片。`GET /api/imagenia/assets/{id}` 查询详情，图片字节只通过需要认证的 `GET /api/imagenia/assets/{id}/content` 获取。前端经 Bearer `fetch` 创建临时 object URL，切换筛选、关闭详情、请求失败和卸载时回收 URL；不在图片地址中传入 token。

宿主联调：同步含 `frontend/dist/` 的整个插件并重启；在桌面和窄屏确认 30 张以上的“加载更多”、仅收藏与类型组合筛选、空库及筛选无结果；打开生成/编辑资产详情并追溯不在当前页的直接来源；切断网络验证加载更多错误与重试；退出登录或使 token 失效验证图片请求 401 提示，检查浏览器 Network 中 URL 无 token，并在切换筛选/关闭详情后检查 object URL 清理。收藏和删除的宿主验收见下文；编辑的宿主验收见下文。

## 生成链路（Issue #5）

生成提交 `POST /api/imagenia/jobs/generate` 返回 `202` 与 `job_id`；后台独立单 worker 将任务从 `pending` 处理到 `running`、`succeeded` 或 `failed`，前端每 1.5 秒通过 `GET /api/imagenia/jobs/{job_id}` 轮询。重新打开页面时通过 `GET /api/imagenia/jobs` 恢复近期任务。成功后从 `GET /api/imagenia/assets` 刷新资料库，图片字节从需要同一 Bearer token 的 `/api/imagenia/assets/{id}/content` 获取；新资产高亮、不自动弹详情。资产文件按年月与 UUID 保存在插件数据目录，元数据在 SQLite 中。上次运行遗留的 `running` 标记为 `interrupted`，`pending` 恢复执行。队列最多允许 50 个待处理任务（第 51 个返回 429）。运行中任务的 10 分钟截止时间到达后标记为 `failed/timeout`；不会强杀可能已经发出计费请求的 provider 调用，单 worker 在该调用返回前不会处理下一任务，迟到的结果不得写入资产。provider 429、超时、不可用及非预期响应分别映射为 `rate_limited`、`timeout`、`service_unavailable`、`invalid_response`，错误详情不包含上游异常文本、密钥或内部路径。

正式宿主使用配置的默认模型（当前默认 `gpt-image-2.5`），画幅分别映射 1024×1024、1536×1024、1024×1536；质量 `standard` 映射 OpenAI 的 `medium`，`high` 对应 `high`。生成调用可能收费，请使用可用密钥和低成本提示词谨慎验证。端到端验收需在 QwenPaw iframe 验证任务提交、轮询、重启恢复、图片展示及登录失效后的安全反馈；本机自动化不代表宿主验收完成。

接入兼容网关时请填写 API 根地址（包含 `/v1` 等必要前缀），不要填写 `/images/generations` 完整接口路径。连接测试仅能检验 `/models` 的认证，不保证网关支持图像生成；真实成功生图与计费行为需在宿主手动确认。

## 图片编辑与来源关系（Issue #7）

从图片详情选择“以此编辑”会单独读取已有源图，提交 `POST /api/imagenia/jobs/edit`（`source_asset_id`、`prompt`、`size`、`quality`），返回 `202` 与 `job_id`。只接受插件已有且可读取的 PNG 资产，不接受上传、蒙版、多图、请求指定模型或任意文件路径。编辑复用单 worker 和状态轮询，provider 以 multipart/form-data 将原图发至配置的 `/images/edits`；正式调用可能产生费用。完成后新建 `kind=edited` 资产并保存直接 `source_asset_id`，原图与其文件保持不变。来源缺失时提交返回安全的 404；排队后来源消失则任务安全失败且不生成资产。编辑来源缩略图有独立临时 URL，关闭编辑或卸载时回收。

本地 `python -m pytest plugin/tests -q` 覆盖成功、失败、原图保留、来源关系及无网络 multipart 请求。宿主验证时同步整个插件（含 `frontend/dist/`）并重启：从详情编辑已有图片，检查编辑任务状态、新资产、直接来源和原图未变；对已删除/不可读来源、失效登录和 provider 错误确认安全提示。自动测试不代表真实宿主与网关的编辑端点已验证，验证通过前不要关闭 #7。

## 存储权限与并发核查（Issue #14）

首次启动时，插件数据根目录及图片子目录限制为 `0700`，SQLite 与新写入 PNG 为 `0600`；在默认权限掩码 `022` 下也生效。对旧目录及数据库/图片先核验所有权、类型和符号链接，再收紧权限；不更改插件数据目录**以外**的父目录。遇到不属于当前进程的路径、符号链接或硬链接会安全拒绝启动，不应对任意自定义路径盲目 `chmod`。更改旧权限前，请由管理员确认 `IMAGENIA_DATA_DIR` 指向正确的插件专属目录；无法修复时需先安全迁移数据，勿改用放宽权限绕过。已有 `config/` 和私有配置文件继续由配置模块检查权限。

运行 `python plugin/tests/storage_probe.py` 可获得可重跑的本地基线：阻塞 fake provider 期间 50 次 `GET /assets` 延迟分布，以及人为持有约 120 ms `BEGIN EXCLUSIVE` 写事务时的读等待。一次本地运行采用 `journal_mode=delete`，等待 provider 时 GET p50/p95/max 为 0.034/0.050/0.146 ms，人为长写事务时约 129 ms；该数值不代表真实宿主负载。worker 在 provider 调用前已提交任务领取事务，没有证据证明启用 WAL 必要，暂不修改日志模式。

当前 QwenPaw 适配器是 `async def` 路由，同一事件循环内同步调用 `app.handle()`；共享连接仍保持 SQLite 默认的 `check_same_thread=True`。`test_storage_privacy.py` 故意从异线程调用以记录条件性 `ProgrammingError`，**不是声称宿主已经出现该错误**。宿主复核可临时设置 `IMAGENIA_THREAD_PROBE=1` 并重启插件，在服务端日志中读取 `create`、`handle`、`content`、`unregister` 的线程 ID（不输出提示词/密钥），复核后关闭该开关；再并发请求与运行长耗时 provider，对比服务器异常和 GET 延迟。如三处线程不一致，应改为请求范围连接并验证并发读写/卸载，不要只设置 `check_same_thread=False`。真机核验数据目录、数据库、图片的模式和属主后再验收 #14。

## 收藏与永久删除（Issue #8）

`PATCH /api/imagenia/assets/{id}` 只接受布尔字段 `{"is_favorite": true|false}`，更新资产收藏状态与时间；资料库可用 `favorite=true` 筛选。`DELETE /api/imagenia/assets/{id}` 成功返回 `200 {"deleted": true}`，移除图片文件和元数据，解除编辑后代的直接来源引用；相关生成/编辑任务保留 ID、类型和状态等最小记录，清除提示词、完整请求参数、来源与结果 ID，仍在队列或执行中的来源编辑任务安全失败。对不可信文件路径返回安全的 `409`，不触及目录之外的文件。前端删除需经过 AlertDialog 确认，成功/失败都有反馈；列表、筛选、任务和详情随后刷新。

自动化覆盖成功/失败、筛选、文件删除、后代保留、任务脱敏与编辑执行期间删除；并不模拟 QwenPaw 的授权。宿主验收时请以非敏感测试图片检查收藏/取消及仅收藏筛选，删除前取消对话框应不变；确认删除后检查本地文件消失、子图片仍在但来源解除、任务提示词不再可见，并复核权限与服务端日志。
