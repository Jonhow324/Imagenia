# Imagenia

Imagenia 是面向 QwenPaw 2.2.1 的本地优先 AI 图像工作台：以 `general` 类型插件运行，后端调用 OpenAI、MiniMax 或自定义兼容图像服务，前端是宿主 iframe 中的 React 单页资料库。图片、提示词与服务配置都留在本机数据目录。

![Imagenia 工作台界面：左侧为「创造新图像」生成表单，右侧为图片资料库，顶部为任务队列、仅看收藏与配置入口](https://res.cloudinary.com/dt9epxgj9/image/upload/v1792740301/Screenshot_From_2026-10-22_15-46-16_zdtra2.png)

## 核心能力

- **多图像服务接入**：每套服务可选 `openai`（预设 `gpt-image-1`）、`minimax`（预设 `image-01`）或 `custom`（任意 OpenAI Images 兼容根地址），每个模型声明各自支持的画幅、质量与编辑能力。
- **生成与编辑**：表单只开放提示词、画幅（方形／横向／纵向）与质量（标准／高质量）；编辑从已有资产进入，结果作为新资产保存并保留直接来源，不覆盖原图。
- **后台任务队列**：提交返回 `202` 与 `job_id`，单 worker 串行执行，前端轮询 `pending`／`running`／`succeeded`／`failed`；重启后恢复排队任务。
- **图片资料库**：全局共享，游标分页，支持提示词搜索、「全部／生成／编辑」筛选、「仅看收藏」、详情中的下载与复制提示词、再次创作，以及浅色／深色外观。
- **本地优先与隐私**：图片按年月与 UUID 存放在插件数据目录，元数据在 SQLite；提示词只留在本机，HTTP 接口不返回密钥。
- **宿主样式隔离**：工作台在独立 iframe SPA 中运行，样式不污染 QwenPaw Console。

## 安装

从 GitHub Release 下载与版本对应的 `imagenia-<tag>.zip` 后安装：

```bash
qwenpaw plugin install /path/to/imagenia-v0.1.0.zip
```

也可以把 ZIP 放到可直连的 URL 后执行 `qwenpaw plugin install <url>`。升级前请先备份数据目录；卸载语义、配置、本地开发与打包说明见 [插件说明](plugin/README.md)，内部实现见 [架构与实现参考](docs/plugin-architecture.md)。

## 快速开始

1. 安装后在 QwenPaw 侧边栏打开「Imagenia」。
2. 在右上角「配置」新增图像服务，填写 API 根地址、API Key 与模型列表；协议差异与模型能力见 [多图像服务与模型选择](docs/plugin-architecture.md#多图像服务与模型选择)。
3. 选择服务与模型，填写画面描述、画幅与质量，点击「开始生成」；任务完成后在资料库详情中选择「以此编辑」可生成新版本。

## 当前状态

V1 核心功能已实现并通过本地自动化测试；真实宿主验收（iframe 鉴权、真实网关生成／编辑、容器持久化）仍待补齐，范围与限制见 [当前状态与限制](docs/plugin-architecture.md#当前状态与限制)。

## 要求与兼容性

| 项目 | 要求 |
| --- | --- |
| QwenPaw | `>=2.2.1, <2.3.0` |
| Python | 3.11+ |
| Node.js | 22（前端测试依赖 `--experimental-strip-types`） |
| 图像服务 | OpenAI Images、MiniMax 或任意 OpenAI Images 兼容服务 |

## 项目结构

- `plugin/`：QwenPaw 插件本体，包含宿主入口、`src/imagenia_plugin/` 后端、React 前端与测试。
- `docs/`：架构、技术设计、UI 基线、ADR、发布清单与宿主验证记录。
- `CONTEXT.md`：项目目标、已确认决策与领域词汇。

## 文档

| 文档 | 内容 |
| --- | --- |
| [plugin/README.md](plugin/README.md) | 插件安装与卸载语义、配置、本地开发、测试与打包 |
| [docs/plugin-architecture.md](docs/plugin-architecture.md) | 架构、子系统（服务／任务／资料库／编辑／删除）、存储与迁移、开发与测试 |
| [docs/technical-design.md](docs/technical-design.md) | 模块边界、数据模型、API 契约、worker 生命周期 |
| [docs/ui-design.md](docs/ui-design.md) | 工作台布局、组件与状态约束 |
| [docs/imagenia-v1-spec.md](docs/imagenia-v1-spec.md) | V1 功能范围 |
| [docs/adr/](docs/adr/) | 架构决策记录（核心架构、任务与生命周期、界面边界、隐私、多服务、内置预设） |
| [docs/plugin-release.md](docs/plugin-release.md) | 发布包组装与平台上传步骤 |
| [plugin/docs/qwenpaw-2.2.1-verification.md](plugin/docs/qwenpaw-2.2.1-verification.md) | QwenPaw 2.2.1 宿主验证记录 |
| [CONTEXT.md](CONTEXT.md) | 项目目标、已确认决策、领域词汇 |

## 许可证

本插件以 Apache License 2.0 发布，与 QwenPaw 平台的发布要求一致；许可证全文见 [LICENSE](LICENSE)。
