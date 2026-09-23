# Imagenia QwenPaw 插件

Imagenia 是面向 QwenPaw 2.2.1 的本地 AI 图像工作台。当前仓库包含已经通过真实宿主验证的插件骨架，以及 React + Vite + Tailwind CSS + shadcn/ui 工作台。配置及生成任务链路已接入插件 HTTP API；收藏、删除与编辑将在后续工单实现。

## 前端工作台

前端源码位于 `plugin/frontend/src/`，构建产物分为两部分：

- `plugin/frontend/dist/index.js`：不引入工作台或第三方运行时的宿主薄入口。宿主通过 Blob `import()` 加载它，它使用 `window.QwenPaw.host.React` 注册 `/imagenia` 路由与侧边栏菜单，并渲染 iframe。
- `plugin/frontend/dist/app/index.html` 和 `assets/`：同源 iframe 中的独立 SPA，包含自己的 React/ReactDOM、shadcn/Radix、Tailwind CSS 和字体；静态资源使用相对路径，不与宿主共享 React dispatcher。入口 URL 为 `/api/frontend_plugin/imagenia/files/frontend/dist/app/index.html`。

`plugin.json` 仍以 `frontend/dist/index.js` 为插件入口。不要把工作台组件导入宿主入口，也不要将 iframe SPA 的 React 设为 external。当前 iframe 从同源插件 API 读取和保存全局 OpenAI 配置，使用 QwenPaw 2.2.1 的 `qwenpaw_auth_token` 发送 Bearer 认证；图片与任务使用后端资源；收藏、删除、编辑尚未开放。宿主联调还需验证实际 iframe 的读写鉴权与 401 反馈。

工作台沿用原型组件；生成表单、任务、图片资料库已接入真实后端：

- API Key 配置状态通过同源 HTTP API 读取，且缺失时禁用生成入口；
- 表单校验与生成任务提交（编辑尚未开放）；
- `pending`、`running`、`succeeded`、`failed` 任务；
- 经 Bearer 认证的图片加载、空结果和类型筛选；完整分页与收藏属于后续工单；
- 详情 Sheet；收藏、编辑、删除仅提示尚未开放，不修改持久化数据；
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

## 全局 OpenAI 配置（Issue #4）

QwenPaw 管理员可在 iframe 工作台的“配置”中保存或覆盖一份全局 API Key。优先使用插件进程中的 `IMAGENIA_OPENAI_API_KEY` 环境变量；否则使用插件数据目录的 `config/openai.json`。该目录权限为 `0700`，文件权限为 `0600`。设置 API 仅返回 `configured` 和 `source`（`none`/`file`/`environment`），不返回密钥。若环境变量已配置，保存文件不会覆盖当前生效的环境变量。请勿把数据目录或密钥纳入 Git。

仅点击“测试连接”时后端才以当前生效密钥对 `GET https://api.openai.com/v1/models` 发起一次只读认证请求（5 秒超时）；加载和保存配置都不会调用 OpenAI，测试不会请求图像生成。正式宿主中提交生成任务会调用 OpenAI Images API，**可能产生费用**。测试环境使用 fake provider 不会产生费用。

宿主验收：同步完整插件到 QwenPaw 2.2.1 后登录，打开 iframe；分别验证无配置、保存、覆盖、环境变量优先，以及点击测试连接的结果。登出或使登录 token 失效后，确认读取/写入遭宿主拒绝且页面显示安全的登录失效提示；本地 ASGI 测试不模拟宿主鉴权。

## 生成链路（Issue #5）

生成提交 `POST /api/imagenia/jobs/generate` 返回 `202` 与 `job_id`；后台独立单 worker 将任务从 `pending` 处理到 `running`、`succeeded` 或 `failed`，前端每 1.5 秒通过 `GET /api/imagenia/jobs/{job_id}` 轮询。重新打开页面时通过 `GET /api/imagenia/jobs` 恢复近期任务。成功后从 `GET /api/imagenia/assets` 刷新资料库，图片字节从需要同一 Bearer token 的 `/api/imagenia/assets/{id}/content` 获取；新资产高亮、不自动弹详情。资产文件按年月与 UUID 保存在插件数据目录，元数据在 SQLite 中。上次运行遗留的 `running` 标记为 `interrupted`，`pending` 恢复执行。队列最多允许 50 个待处理任务。

正式宿主默认模型固定为 `gpt-image-1`，画幅分别映射 1024×1024、1536×1024、1024×1536；质量 `standard` 映射 OpenAI 的 `medium`，`high` 对应 `high`。生成调用可能收费，请使用可用密钥和低成本提示词谨慎验证。端到端验收需在 QwenPaw iframe 验证任务提交、轮询、重启恢复、图片展示及登录失效后的安全反馈；本机自动化不代表宿主验收完成。
