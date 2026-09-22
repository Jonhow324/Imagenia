# Imagenia QwenPaw 插件

Imagenia 是面向 QwenPaw 2.2.1 的本地 AI 图像工作台。当前仓库包含已经通过真实宿主验证的插件骨架，以及 Issue #2 的 React + Vite + Tailwind CSS + shadcn/ui mock 工作台。

## 前端工作台

前端源码位于 `plugin/frontend/src/`，生产入口是 `plugin/frontend/dist/index.js`。QwenPaw 提供 React/ReactDOM；生产 bundle 将二者标记为 external，避免在宿主中加载第二份 React。

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

Tailwind preflight 已关闭，生成的选择器统一限制在 `.imagenia-root` 下；Radix 的 Select、Tooltip、Sheet 和 AlertDialog 使用插件自己的 portal 容器，避免样式泄漏到 QwenPaw Console。

## 后端测试

在仓库根目录执行：

```bash
python -m pip install -r plugin/requirements-dev.txt
python -m pytest plugin/tests -q
```

当前后端仍是 Issue #3 的 HTTP 测试接缝和确定性 `FakeImageProvider`，不会调用 OpenAI，也不会产生费用。真实宿主验证记录见 `plugin/docs/qwenpaw-2.2.1-verification.md`。
