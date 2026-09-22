# QwenPaw 2.2.1 集成验证记录

- 目标稳定版本：QwenPaw 2.2.1
- 插件版本：Imagenia 0.1.0
- 插件兼容声明：`>=2.2.1, <2.3.0`
- 宿主验证日期：2026-09-22
- 记录更新日期：2026-09-22
- 当前状态：Issue #3 的宿主加载、页面渲染和前后端 HTTP 接缝均已验证

## 验证结论

QwenPaw 2.2.1 能够发现并加载 Imagenia，调用后端 `register(api)`，通过 `register_http_router` 暴露 HTTP 契约，并在插件数据目录创建 SQLite 数据库和图片目录。创建生成任务会返回 `202 Accepted` 并持久化 `pending` 任务；当前骨架不会调用真实 OpenAI API。

后台 worker、任务轮询、实际图像生成和浏览器内工作台交互不属于本次已通过范围。

## 已验证项

| 项目 | 结果 | 验证证据 |
|---|---|---|
| manifest 解析 | 通过 | 宿主插件列表包含 `imagenia`、`type=general` 和 `frontend/index.js` |
| 版本兼容声明 | 通过 | QwenPaw 2.2.1 满足 `>=2.2.1, <2.3.0` |
| 后端入口 | 通过 | 宿主调用 `register(api)` 后创建数据库和图片目录 |
| HTTP 注册 API | 通过 | `register_http_router(router, prefix=..., tags=...)` 与宿主方法签名一致 |
| 插件发现目录 | 通过 | 宿主扫描 `/app/working/plugins/`，符号链接安装可用 |
| 健康检查 | 通过 | `GET /api/imagenia/health` 返回 `200` 和正常状态 |
| 设置占位接口 | 通过 | `GET /api/imagenia/settings` 返回未配置状态 |
| 资产列表占位接口 | 通过 | `GET /api/imagenia/assets` 返回空列表 |
| 创建生成任务 | 通过 | `POST /api/imagenia/jobs/generate` 返回 `202` 和 `pending` 任务 |
| SQLite 初始化 | 通过 | `schema_version=1`，`generation_jobs` 表存在且任务写入成功 |
| 图片目录初始化 | 通过 | 插件启动时创建 `images/` |
| FastAPI 依赖 | 通过 | 宿主环境中的 FastAPI 满足插件声明范围 |
| 本地 HTTP 测试 | 通过 | `python -m pytest plugin/tests -q`：3 passed |
| 菜单注册 | 通过 | 宿主侧边栏显示 Imagenia 菜单项 |
| 页面路由与渲染 | 通过 | 点击菜单后 Imagenia mock 骨架页面正常打开 |
| 前端请求后端 | 通过 | 宿主页面实际请求 `/api/imagenia/health` 并收到 `status=ok` |

## 待验证或待实现

| 项目 | 状态 | 说明 |
|---|---|---|
| 后台 worker | 未实现 | 任务当前会停留在 `pending` |
| 任务轮询接口 | 未实现 | `GET /api/imagenia/jobs/{job_id}` 尚未提供 |
| 图片实际落盘 | 未实现 | 依赖 worker 和 provider 执行链 |
| OpenAI 配置 | 未实现/未验证 | 环境变量和权限为 `0600` 的私有配置文件路径均待后续工单实现 |

## 已确认的宿主集成约定

- 插件扫描目录：`/app/working/plugins/`
- 开发环境可将仓库的 `plugin/` 符号链接到扫描目录中的 `imagenia`
- 后端路由通过 `api.register_http_router(...)` 注册
- 插件数据目录可通过 `IMAGENIA_DATA_DIR` 覆盖
- 未设置覆盖变量时，当前实现默认写入 `~/.qwenpaw/plugins/imagenia`
- 容器部署应优先把 `IMAGENIA_DATA_DIR` 指向持久化 volume 下的目录

## 复验清单

```bash
# 插件代码已位于宿主可访问的仓库目录时：
ln -sfn /path/to/Imagenia/plugin /app/working/plugins/imagenia

# 插件自测
python -m pytest plugin/tests -q

# 重启宿主后，在已配置认证的客户端中验证：
curl http://127.0.0.1:8088/api/imagenia/health
curl http://127.0.0.1:8088/api/imagenia/settings
curl http://127.0.0.1:8088/api/imagenia/assets
curl -X POST http://127.0.0.1:8088/api/imagenia/jobs/generate \
  -H 'content-type: application/json' \
  -d '{"prompt":"host verification image","size":"square","quality":"standard"}'
```

认证信息应通过环境变量、凭据文件或交互式输入提供，不写入仓库文档、命令历史或测试输出。
