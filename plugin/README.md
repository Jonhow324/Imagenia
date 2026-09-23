# Imagenia QwenPaw 插件

Imagenia 是面向 QwenPaw 2.2.1 的本地 AI 图像工作台。当前仓库包含已经通过真实宿主验证的插件骨架，以及 Issue #2 的 React + Vite + Tailwind CSS + shadcn/ui mock 工作台。

## 前端工作台

前端源码位于 `plugin/frontend/src/`，构建产物分为两部分：

- `plugin/frontend/dist/index.js`：不引入工作台或第三方运行时的宿主薄入口。宿主通过 Blob `import()` 加载它，它使用 `window.QwenPaw.host.React` 注册 `/imagenia` 路由与侧边栏菜单，并渲染 iframe。
- `plugin/frontend/dist/app/index.html` 和 `assets/`：同源 iframe 中的独立 SPA，包含自己的 React/ReactDOM、shadcn/Radix、Tailwind CSS 和字体；静态资源使用相对路径，不与宿主共享 React dispatcher。入口 URL 为 `/api/frontend_plugin/imagenia/files/frontend/dist/app/index.html`。

`plugin.json` 仍以 `frontend/dist/index.js` 为插件入口。不要把工作台组件导入宿主入口，也不要将 iframe SPA 的 React 设为 external。当前 iframe 仅展示 mock 数据；后续 HTTP 接口联调应验证 iframe 内 Bearer 认证、401 反馈和受控图片加载。

工作台目前使用 mock 数据覆盖：

- API Key 已配置与未配置；
- 表单校验、生成和编辑提交；
- `pending`、`running`、`succeeded`、`failed` 任务；
- 图片加载、空结果、类型/收藏筛选和加载更多失败；
- 详情 Sheet、一级来源跳转、收藏反馈和删除确认；
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

`npm run build` 依次类型检查、构建 `dist/app/`、构建 `dist/index.js` 并运行产物接缝测试。`npm run test:build` 可以在已有产物上单独运行。将整个 `plugin/`（包括两个前端产物）同步到宿主后重启插件，在 QwenPaw 2.2.1 验证侧边栏、iframe 加载、交互与浏览器控制台。

Tailwind preflight 已关闭，选择器限制在 `.imagenia-root` 下；Select、Tooltip、Sheet 和 AlertDialog 使用工作台自己的 portal 容器。iframe 进一步隔离了工作台样式和宿主页面。

## 后端测试

在仓库根目录执行：

```bash
python -m pip install -r plugin/requirements-dev.txt
python -m pytest plugin/tests -q
```

当前后端仍是 Issue #3 的 HTTP 测试接缝和确定性 `FakeImageProvider`，不会调用 OpenAI，也不会产生费用。真实宿主验证记录见 `plugin/docs/qwenpaw-2.2.1-verification.md`。
