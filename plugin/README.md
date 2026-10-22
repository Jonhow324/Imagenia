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

工作台采用固定视口布局：顶部和左侧表单保持可见，仅图片资产区滚动；“任务队列”入口位于顶部，点击可查看最近任务及恢复失败参数。窄屏或可用高度不足时，通过顶部“创作”打开表单面板，关闭后保留当前草稿。宿主入口按导航下方的可用高度调整 iframe，避免宿主与图库双重滚动。

## 本地开发与验证

日常界面和业务流程修改可以直接在本机验证，无需拉取到 QwenPaw 或重启宿主。使用两个终端分别运行本地后端和 Vite。以下命令从仓库根目录开始执行。

首次安装开发依赖（Python 3.11+）：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r plugin/requirements-dev.txt
cd plugin/frontend
npm install
```

终端一，在仓库根目录启动后端：

```bash
.venv/bin/python plugin/dev.py --reload
```

终端二启动前端：

```bash
cd plugin/frontend
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`。Vite 将 `/api/imagenia` 代理到 `127.0.0.1:8765`；前端改动热更新，Python 改动由 `--reload` 自动重启后端。后端复用正式插件的 FastAPI 路由、SQLite、后台 worker 和文件存储。

默认是 **fake 离线模式**：

- 无需 QwenPaw 登录或真实 API Key；自动配置一个本地演示占位值。
- 首次启动创建 36 张不同颜色和画幅的 PNG，包含收藏和直接编辑来源，便于测试第二页加载。
- 可测试生成、编辑、任务轮询、收藏、筛选、详情、分页、删除及刷新后的数据保留。生成和编辑返回彩色占位图，不模拟图像模型的创作效果；连接测试也不访问外部服务。
- 数据保存到 Git 忽略的 `plugin/.local-data/fake/`，重启保留数据，已有任务时不会重新填充。此入口不读取宿主的 `IMAGENIA_DATA_DIR`。
- `--seed 0` 可在一个新的数据目录中测试空库；例如 `plugin/dev.py --reload --seed 0 --data-dir /tmp/imagenia-empty`。`--seed` 仅影响首次空库初始化，范围为 0～100。

需要真实生图时，先停止 fake 后端，再显式启动：

```bash
.venv/bin/python plugin/dev.py --provider openai --reload
```

此模式默认使用独立的 `plugin/.local-data/openai/`，不会自动创建样本。可在页面配置 API Key、base URL 和模型，或使用 `IMAGENIA_OPENAI_*` 环境变量。生成和编辑将调用配置的服务，可能产生费用。

本地后端只监听 `127.0.0.1`，不模拟 QwenPaw 的登录鉴权。菜单/路由注册、宿主内 iframe 行为、登录失效及宿主安装/卸载仍需在 QwenPaw 中验收。常规样式、文案、表单、图库和业务逻辑改动可先完成本地验证，再集中到宿主做一次集成回归。

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

## 多图像服务与模型选择

配置面板可新增多套 OpenAI Images 兼容服务，每套配置独立名称、API 根地址、API Key 和模型列表。每个模型勾选支持的方形／横图／竖图、标准／高质量和图片编辑；新模型默认关闭编辑。兼容服务需支持目前的图像生成／multipart 编辑请求以及 base64 PNG 响应，不自动适配其他协议。

保存后可设置全局默认服务／模型，或在生成表单中自行选择。浏览器记住最近选择；失效、停用或不支持编辑时要求重新选择，不自动切换服务。编辑可使用其他服务的模型，原图保留。任务和图片详情显示提交时的服务名称及模型；失败任务可恢复原参数到表单，确认后再提交。

每个任务绑定服务、模型和地址／密钥／模型的连接指纹。存在未完成任务时，后端拒绝更改地址、Key、移除或重命名原有模型及删除服务；新增模型、改服务名称、调整能力声明和停用仍可进行。停用仅阻止新任务，排队任务继续完成。配置在运行期间被外部修改或重启后发生变化时，未执行任务标记 `configuration_changed`；不重试、不自动切换。

服务配置保存在持久化数据目录 `config/services.json`（目录 `0700`、文件 `0600`），HTTP 不返回密钥。务必把整个数据目录保存在 Docker 持久化挂载中。旧 `config/openai.json` 首次迁移为“默认图像服务”，保留兼容设置接口；已有编辑能力保留。环境变量 `IMAGENIA_OPENAI_*` 形成只读“环境配置”，不把环境密钥复制到文件；环境中未指定的字段继续遵循旧配置的回退规则。

旧设置接口 `/settings/openai` 继续返回原有单服务契约并作为旧配置的兼容镜像；新界面使用 `/services`。新目录存在后只迁移一次，不自动合并后来手动编辑的旧文件。删除旧服务会清除它的兼容文件；历史资产及服务名称快照保留。

点击某一服务的“测试已保存的连接”只向该服务请求 `GET /models`；加载、保存、设置默认都不发起外部请求。只读认证通过不等于模型一定能生成或编辑，能力由用户配置，实际任务由用户显式提交。

| 接口 | 行为 |
| --- | --- |
| `GET /api/imagenia/services` | 服务列表、脱敏状态、模型、活动任务数和全局默认项 |
| `POST /api/imagenia/services` | 新增服务 |
| `PUT /api/imagenia/services/{id}` | 修改服务，省略 Key 时保留已有密钥 |
| `DELETE /api/imagenia/services/{id}` | 无未完成任务时删除配置和密钥，保留资产／任务 |
| `PUT /api/imagenia/services/default` | 设置 `{service_id, model_id}` 默认组合 |
| `POST /api/imagenia/services/{id}/test` | 显式只读认证测试 |

生成／编辑任务支持 `service_id` 和 `model_id`，前端每次显式发送。兼容旧客户端未传这两个字段时使用全局默认，禁止只传其中一个或任意覆盖模型名。模型声明的画幅、质量和编辑能力均由后端校验。

新增回归：`python -m pytest plugin/tests/test_multi_services_http.py -q`、前端 `npm run test:services`。本地 fake 模式可测试完整设置、服务切换和跨服务编辑；正式宿主仍需验收 iframe 鉴权、真实兼容服务的生成／编辑和容器持久化。

## 旧版 OpenAI 设置兼容接口（Issues #4、#12）

旧客户端仍可通过 `/settings`、`/settings/openai`、`/settings/openai/test` 读取状态、保存旧默认服务和显式测试连接。新工作台使用前述多服务接口；旧设置接口不代表当前生成表单选择的服务。

兼容配置位于数据目录 `config/openai.json`，目录权限 `0700`、文件权限 `0600`。`IMAGENIA_OPENAI_API_KEY`、`IMAGENIA_OPENAI_BASE_URL`、`IMAGENIA_OPENAI_MODEL` 分别覆盖对应文件字段；未指定地址和模型时仍使用旧默认值。设置接口不回显密钥，省略密钥时保留原值。通过兼容接口保存时同步更新迁移出的默认服务；该服务或环境配置有未完成任务时，返回 `409 service_in_use`。

旧连接测试仍只发出一次只读 `GET /models` 请求（5 秒超时），不请求图像生成。正式宿主显式提交生成／编辑任务可能产生费用；常规测试使用 fake provider。

宿主验收需检查 iframe 的读写鉴权与登录失效提示；本地 ASGI 测试不模拟宿主鉴权。

## 图片资料库（Issue #6）

`GET /api/imagenia/assets` 默认返回至多 30 条，可用 `limit=1..100` 指定每页大小，按 `created_at DESC, id DESC` 排序；返回 `items` 和可为空的 `next_cursor`。将该游标原样传给 `cursor` 查询参数继续加载；`cursor=` 或 `cursor=null` 等同首次请求，其余非法游标仍返回 `422`。`favorite=true` 仅看收藏；`kind=generated|edited` 筛选类型，两者可组合。参数无效时返回 `422`；筛选在后端执行，不仅针对已加载图片。`GET /api/imagenia/assets/{id}` 查询详情，图片字节只通过需要认证的 `GET /api/imagenia/assets/{id}/content` 获取。前端经 Bearer `fetch` 创建临时 object URL，切换筛选、关闭详情、请求失败和卸载时回收 URL；不在图片地址中传入 token。

宿主联调：同步含 `frontend/dist/` 的整个插件并重启；在桌面和窄屏确认 30 张以上的“加载更多”、仅收藏与类型组合筛选、空库及筛选无结果；打开生成/编辑资产详情并追溯不在当前页的直接来源；切断网络验证加载更多错误与重试；退出登录或使 token 失效验证图片请求 401 提示，检查浏览器 Network 中 URL 无 token，并在切换筛选/关闭详情后检查 object URL 清理。收藏和删除的宿主验收见下文；编辑的宿主验收见下文。

## 生成链路（Issue #5）

生成提交 `POST /api/imagenia/jobs/generate` 返回 `202` 与 `job_id`；后台独立单 worker 将任务从 `pending` 处理到 `running`、`succeeded` 或 `failed`，前端每 1.5 秒通过 `GET /api/imagenia/jobs/{job_id}` 轮询。重新打开页面时通过 `GET /api/imagenia/jobs` 恢复近期任务。成功后从 `GET /api/imagenia/assets` 刷新资料库，图片字节从需要同一 Bearer token 的 `/api/imagenia/assets/{id}/content` 获取；新资产高亮、不自动弹详情。资产文件按年月与 UUID 保存在插件数据目录，元数据在 SQLite 中。上次运行遗留的 `running` 标记为 `interrupted`，`pending` 恢复执行。队列最多允许 50 个待处理任务（第 51 个返回 429）。运行中任务的 10 分钟截止时间到达后标记为 `failed/timeout`；不会强杀可能已经发出计费请求的 provider 调用，单 worker 在该调用返回前不会处理下一任务，迟到的结果不得写入资产。provider 429、超时、不可用及非预期响应分别映射为 `rate_limited`、`timeout`、`service_unavailable`、`invalid_response`，错误详情不包含上游异常文本、密钥或内部路径。

正式宿主使用任务提交时选定的服务和模型，旧配置默认模型为 `gpt-image-2.5`；画幅分别映射 1024×1024、1536×1024、1024×1536；质量 `standard` 映射 OpenAI 的 `medium`，`high` 对应 `high`。生成调用可能收费，请使用可用密钥和低成本提示词谨慎验证。端到端验收需在 QwenPaw iframe 验证任务提交、轮询、重启恢复、图片展示及登录失效后的安全反馈；本机自动化不代表宿主验收完成。

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

## 数据迁移与安装生命周期（Issue #10）

SQLite schema 当前版本为 **v4**。首次安装自动建立 v1，再按顺序应用 v2、v3、v4；每个版本在独立事务中完成，失败则回滚当前版本并阻止后端 HTTP 路由注册。错误只指出失败的迁移版本，不把 SQL、数据路径、配置或提示词输出到普通日志。v3 为资产来源、任务来源和任务结果建立外键（删除引用资产时 `SET NULL`），并保留资产分页、收藏和来源查询索引。v4 增加任务服务绑定、连接指纹、重试参数及资产来源快照；旧图片、收藏、提示词和任务均保留，来源未记录时显示“历史配置”。**升级前的 `pending` 任务缺少可靠绑定，将明确标记失败并要求确认后重新提交**；不会猜测服务并继续调用。重复启动已完成版本不会重建表；升级时保留图片元数据及图片文件。迁移前请备份持久化数据目录，**不要**在失败后手工修改 `schema_version` 来跳过迁移，应先检查备份、磁盘空间、文件权限和旧库的一致性。

数据目录优先使用 `IMAGENIA_DATA_DIR`；该变量已设置但为空或仅含空格时拒绝启动，避免误写工作目录。未设置时，新安装默认使用 **`plugin.py` 所在安装目录下的 `data/`**，不再默认写入容器用户的家目录。本地开发入口仍使用独立的 `plugin/.local-data/`。

例如插件安装目录为 `/app/working/plugins/imagenia/` 时，默认结构为：

```text
/app/working/plugins/imagenia/data/
├── config/services.json     # 多服务配置、Key、模型与默认项
├── config/openai.json       # 迁移保留的旧设置兼容文件（如存在）
├── imagenia.sqlite3         # 图片元数据、收藏、提示词和任务
└── images/YYYY/MM/UUID.png  # 生成或编辑结果
```

**Docker 部署必须确认上述数据目录位于实际的持久化挂载中**；仅安装到这个路径不等于已配置挂载。如果插件安装目录已经持久化，`data/` 会随它保留。也可以在现有 QwenPaw Compose 服务的 `environment` 中明确指定：

```yaml
environment:
  IMAGENIA_DATA_DIR: /app/working/plugins/imagenia/data
```

此设置只选择容器内路径，不创建 Docker 挂载，也不迁移旧数据。升级、覆盖安装及容器重建时必须保留同一数据目录、挂载和文件属主；更新代码时保留 `data/`，不要用清空整个安装目录的方式更新。`data/` 已由 Git 忽略，发布插件时也不要把运行数据和密钥打包进去。

### 旧版本数据迁移

旧默认目录为运行 QwenPaw 用户的 `~/.qwenpaw/plugins/imagenia`。未指定 `IMAGENIA_DATA_DIR`、新目录没有数据且旧目录存在数据库、配置或图片目录时，插件继续读取旧目录，并在日志中提示迁移。这是避免升级后切换到空图库的兼容行为，**不会使旧目录自动获得 Docker 持久化能力**。新目录已有数据时优先使用新目录，不自动合并两套图库。

迁移前停用插件并确认后台进程已停止，备份旧数据目录；将 `config/`、`imagenia.sqlite3`、数据库伴随文件（若存在）和 `images/` 一起复制到持久化安装目录的 `data/`。目标已有数据时不要直接覆盖或合并。保持数据属主与容器运行用户一致，目录权限为 `0700`、配置文件/数据库/图片为 `0600`。然后显式设置上面的 `IMAGENIA_DATA_DIR`，重新启用插件，检查 API 配置状态、图片、收藏与任务；核验前保留旧副本。旧容器已经删除且没有保留数据目录或备份时，更换路径不能找回已丢失文件。

### 停用和卸载

插件停用会停止领取新任务，运行中任务标记 `failed/interrupted` 且不会自动重试；已有 `pending` 在下次启用时恢复。插件自身的 `unregister()` **不会删除**密钥配置、SQLite 或 PNG，重新注册同一数据目录可继续使用。卸载由宿主管理插件代码/路由；插件不主动清理数据，**但宿主若删除整个插件安装目录，也会删除其中的 `data/`**。需要跨插件卸载保留数据时，将 `IMAGENIA_DATA_DIR` 指向插件安装目录外的独立持久化目录。卸载前先备份并核对持久化挂载；需要彻底删除数据时由管理员在卸载和备份确认后单独清理，不自动执行不可逆操作。

本地回归 `python -m pytest plugin/tests -q` 覆盖首次安装、v1/v2 升级、幂等重启、迁移回滚与阻止注册、约束/外键/索引、配置/任务/收藏/图片保留、模拟停用和重装；不模拟 QwenPaw 的真实卸载文件策略。真机验收请在测试 volume 上备份后，核对覆盖安装、重启、停用与重装前后的配置状态、任务、收藏、图片可读性和文件权限，并确认卸载是否会连带删除默认目录，再决定生产数据路径。
