# QwenPaw 2.2.1 集成验证记录

- 目标稳定版本：QwenPaw 2.2.1
- 插件兼容声明：`>=2.2.1, <2.3.0`
- 记录日期：2026-09-22
- 当前状态：插件内契约已验证；宿主运行时验证待执行（HTTP API 方法已按官方插件契约调整）

| 项目 | 当前记录 | 验证方式 |
|---|---|---|
| manifest | `plugin/plugin.json`，`type=general`，后端和前端入口均声明 | 静态 JSON 检查 |
| 后端入口 | `plugin/plugin.py` 导出 `plugin`，实现 `register(api)` | Python 导入检查 |
| 前端入口 | `frontend/index.js` 注册 `window.QwenPaw.menu` 和 `window.QwenPaw.route` | 静态入口检查 |
| HTTP 路由 | `/api/imagenia/health` 等契约由依赖无关 ASGI app 提供 | `plugin/tests/test_http.py` |
| 数据目录 | `IMAGENIA_DATA_DIR` 可覆盖；默认插件专属目录 | `plugin.py` 和临时目录测试 |
| 菜单/页面 | manifest 声明 `meta.menu`；页面为 mock 工作台 | 宿主加载测试待执行 |
| 宿主注册方法 | 使用 `api.register_http_router(router, prefix="/imagenia", tags=["imagenia"])` | 文档契约；需在 2.2.1 宿主运行加载测试 |

宿主验证完成前，不把 `register_router` 的候选实现描述为 QwenPaw 已确认 API；集成测试应使用真实 QwenPaw 2.2.1 安装执行一次加载、菜单打开、健康检查和数据目录写入。
