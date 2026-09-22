# Imagenia 插件骨架

这是 Issue #3 的可加载插件骨架和后端 HTTP 测试接缝。当前阶段只提供本地 mock 工作台、健康检查、任务创建边界和确定性的 `FakeImageProvider`；不会调用 OpenAI，也不会产生费用。

## 本地测试

在仓库根目录执行：

```bash
python -m pip install -r plugin/requirements-dev.txt
python -m pytest plugin/tests -q
```

测试会为每个用例创建临时 SQLite 数据库和临时图片目录。真实 provider 尚未接入，测试不需要 API Key。

## QwenPaw 加载

插件清单是 `plugin/plugin.json`，后端入口是 `plugin/plugin.py`，前端入口是 `plugin/frontend/index.js`；`index.html` 是脱离 QwenPaw 的本地 mock 预览。数据目录可由 `IMAGENIA_DATA_DIR` 覆盖；未配置时使用 `~/.qwenpaw/plugins/imagenia`。

`plugin.py` 通过 QwenPaw 2.2.x 的 `register_http_router` 注册 FastAPI 路由；依赖无关的 ASGI 应用仍用于本地 HTTP 测试。该注册方式已在 QwenPaw 2.2.1 宿主中完成后端加载、HTTP 契约、菜单注册、页面渲染和前端健康检查请求验证，见 `docs/qwenpaw-2.2.1-verification.md`。
