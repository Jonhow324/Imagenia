# Imagenia 插件发布清单

发布要求来自 [qwenpaw-plugin-publish-research.md](qwenpaw-plugin-publish-research.md)（AgentScope Platform 发布页与 QwenPaw 官方开发文档核查）。本文只记录已确认的要求和本仓库的落地方式；研究文档第 5 节列出的未验证部分不在本文推断。

## 发布渠道与硬性限制

- 渠道：AgentScope Platform 插件发布页，支持 File Upload 或 URL Upload。
- 上传包必须是 ZIP，且不超过 10MB；CI 在打包后校验大小，超限直接失败。
- 上传时必须确认拥有发布权利，并同意以 Apache 2.0 授权发布。仓库尚未添加 LICENSE 文件，正式发布前需由维护者确认后补齐（见下文“待决策”）。

## plugin.json 要求

| 要求 | 本仓库现状 |
| --- | --- |
| 唯一插件 ID，小写连字符 | `imagenia` |
| 语义版本号 | `0.1.0` |
| 至少提供一个入口；`type` 支持 `general` | `general`，前后端入口齐备 |
| 入口路径相对插件目录，前端入口指向构建产物 | `plugin.py`、`frontend/dist/index.js` |
| `qwenpaw_version` 声明兼容范围，`min` 含下界、`max` 不含上界 | `>=2.2.1, <2.3.0` |
| Python 依赖经 `dependencies` 或 `requirements.txt` 声明 | `dependencies` 为空，`requirements.txt` 声明 `fastapi>=0.115,<1` |

## 发布包内容

CI 在打包前把运行材料整理到单独的暂存目录 `imagenia/`，再从暂存目录的父目录压缩：

```text
imagenia/
├── plugin.json
├── plugin.py
├── requirements.txt
├── README.md
├── src/imagenia_plugin/
└── frontend/dist/
    ├── index.js
    └── app/
```

不要只打包 `frontend/dist/index.js`：`plugin.json` 声明的前端入口是它，但工作台页面资源在 `frontend/dist/app/`，两部分都来自 `npm run build`。打包排除 `node_modules/`、虚拟环境、`__pycache__/`、`data/`、`.env`、API Key 与本机配置。`plugin.py` 以 `src.imagenia_plugin` 导入后端包，暂存目录结构不能改动。

## 版本与标签

- 版本号以 `plugin.json` 的 `version` 为准，遵循语义化版本。
- 发布 tag 使用 `v<version>` 形式（如 `v0.1.0`）；CI 在 release 任务中校验 tag 与 `plugin.json` 版本一致，不一致直接失败。
- 更新日志在平台表单中手工填写；发布前应把本次变更整理成一段可直接粘贴的文案。

## 发布操作步骤

1. 确认 `plugin/plugin.json` 的 `version` 已更新，并核对 README 中的验收状态。
2. 提交变更，创建并推送 `v<version>` 标签。
3. GitHub Actions 构建前端、组装 `imagenia-<tag>.zip` 并附到对应 Release；从 Release 下载该 ZIP。
4. 在平台发布页上传 ZIP（或填入可直连的 ZIP 地址），核对自动解析的名称、版本、作者、前后端入口、依赖与兼容信息。
5. 填写插件类型（必填）、描述（不超过 2000 字）、仓库 URL 和更新日志，勾选 Apache 2.0 授权确认。
6. 保存草稿并预览，确认后提交安全扫描；扫描通过前插件保持私有。
7. 将 Release ZIP 安装到真实 QwenPaw，完成插件 README 中列出的 iframe 鉴权、真实图像服务与安装/升级/卸载数据保留验收。

## 待决策

- LICENSE 类型：平台强制以 Apache 2.0 授权发布，仓库需在正式发布前添加对应 LICENSE 文件，并核对需随包保留的第三方依赖许可。
- 首个发布版本号：当前清单为 `0.1.0`，首个 tag 预计为 `v0.1.0`。
- 研究文档第 5 节的未验证事项（URL 上传托管要求、扫描规则、同 ID 新版本发布与下架流程等）需在登录平台后确认。
