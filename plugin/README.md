# Imagenia 插件

Imagenia 以 QwenPaw `general` 类型插件的形式发布：后端负责图像服务调用、任务队列、SQLite 元数据与本地文件存储，前端是运行在宿主 iframe 中的 React 单页工作台。项目定位、截图与完整文档索引见 [仓库 README](../README.md)。

## 安装与卸载

安装命令与发布包获取见 [仓库 README 的安装一节](../README.md#安装)。安装后需要知道的语义：

- **升级**：覆盖安装会运行 SQLite 迁移（当前 schema v4），保留图片、收藏、提示词与任务；升级前的 `pending` 任务会标记失败并要求确认后重新提交，迁移前请先备份数据目录。
- **界面卸载**：宿主会同时删除插件目录及其中的 `data/`，SQLite、服务配置与图片一并消失，卸载前请先备份。
- **命令行卸载**：`qwenpaw plugin uninstall imagenia` 只卸载插件并保留插件目录；此时重装会报目录已存在，需先手动删除残留目录或使用 `--force`。

需要跨卸载保留数据时，把 `IMAGENIA_DATA_DIR` 指向安装目录之外的持久化目录；完整规则见 [数据迁移与安装生命周期](../docs/plugin-architecture.md#数据迁移与安装生命周期issue-10)。

## 配置

服务配置保存在数据目录的 `config/services.json`（目录 `0700`、文件 `0600`），HTTP 接口不返回密钥；`IMAGENIA_OPENAI_*` 环境变量可提供只读配置。服务协议、模型能力与连接测试的细节见 [多图像服务与模型选择](../docs/plugin-architecture.md#多图像服务与模型选择)。

## 本地开发

在仓库根目录安装开发依赖：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r plugin/requirements-dev.txt
cd plugin/frontend && npm install
```

两个终端分别启动后端与前端：

```bash
.venv/bin/python plugin/dev.py --reload    # 终端一：后端
cd plugin/frontend && npm run dev          # 终端二：前端
```

浏览器打开 `http://127.0.0.1:5173`。默认是 fake 离线模式：不需要 API Key，不产生费用，首次启动会生成示例图片。需要真实生图时改用 `.venv/bin/python plugin/dev.py --provider openai --reload`。fake 模式的种子参数、数据目录与宿主联调注意事项见 [本地开发与验证](../docs/plugin-architecture.md#本地开发与验证)。

## 测试与构建

```bash
python -m pytest plugin/tests -q
cd plugin/frontend && npm run typecheck && npm run build
```

常规测试显式注入 `FakeImageProvider`，不访问 OpenAI、不产生费用。`npm run build` 依次类型检查、构建 `dist/app/`、构建 `dist/index.js` 并运行产物与配置请求测试。

## 打包与发布

`plugin/frontend/dist/` 已被 Git 忽略，发布前必须先执行 `npm install && npm run build` 生成产物。正式发布包为 `imagenia-<tag>.zip`（清单、后端入口、依赖声明、README、侧边栏图标与两个前端产物），由 GitHub Actions 在推送 `v*` 标签时组装，tag 必须与 `plugin.json` 的 `version` 一致。发布包内容、平台限制与上传步骤见 [发布清单](../docs/plugin-release.md)。

## 相关文档

| 文档 | 内容 |
| --- | --- |
| [plugin-architecture.md](../docs/plugin-architecture.md) | 架构、子系统、存储与迁移、开发与测试 |
| [plugin-release.md](../docs/plugin-release.md) | 发布包组装与平台上传步骤 |
| [qwenpaw-2.2.1-verification.md](docs/qwenpaw-2.2.1-verification.md) | QwenPaw 2.2.1 宿主验证记录 |
| [CONTEXT.md](../CONTEXT.md) | 项目目标、已确认决策、领域词汇 |

许可证：[Apache License 2.0](../LICENSE)。
