# QwenPaw 插件发布流程核查

核查日期：2026-10-22。

本次只查看官方发布页、官方开发文档和本仓库现状，没有上传文件、保存平台草稿、提交扫描或发布插件。

## 1. 官方发布入口与流程

入口为 [AgentScope Platform 插件发布页](https://platform.agentscope.io/plugins/publish)。本次首次加载时读取到了完整的上传表单，随后跳转到登录页；继续操作需要登录。[1]

页面介绍的流程为：上传原生代码插件 → 保存草稿、预览 → 提交安全扫描。页面明确说明，扫描通过前插件保持私有。不能据此断言扫描通过后自动公开，也不能确认是否还需要人工审核。[1]

| 阶段 | 已确认的操作或要求 |
| --- | --- |
| 登录 | 发布入口会跳转至登录页，并携带返回发布页的参数 |
| 提供插件 | 支持 URL Upload / Parse URL，或 File Upload |
| 文件上传 | 必须为 ZIP，文件大小不能超过 10MB |
| 检查元数据 | 页面展示名称、版本、作者、前后端入口、依赖和 QwenPaw 兼容信息 |
| 补充信息 | 插件类型带必填标记；可编辑描述、仓库 URL 和更新日志 |
| 许可证 | 必须确认拥有发布权利，并同意以 Apache 2.0 发布 |
| 草稿与后续流程 | 页面提供 Drafts、Save Draft 和 Next；页面说明支持预览和提交安全扫描 |

以上为发布页直接观察，均来自来源 [1]。未登录、未提供插件包时，保存草稿和下一步按钮不可用，不能仅凭此状态推断每个字段的必填规则。

## 2. 表单材料

发布页中，名称、版本、作者、前后端入口、依赖、兼容信息和最低版本为禁用输入框；应先在插件清单与发布包中准备准确值，上传后核对。由于本次没有实际上传，字段自动解析的具体规则尚未验证。[1]

可直接编辑的材料包括：[1]

- 插件类型：页面标记为必填；本次未展开选项，不推断平台具体枚举。
- 描述：页面显示 `0 / 2000` 字数计数。
- 仓库 URL。
- 更新日志。
- Apache 2.0 发布授权勾选项。

发布页未在本次可见表单中列出截图、图标、隐私政策或审核时限要求；登录后的后续页面是否要求这些材料尚未确认。

## 3. 官方插件包要求

官方开发文档要求清单包含唯一插件 ID 和语义版本号，并至少提供一个前端或后端入口。入口路径相对插件目录；前端入口应指向构建产物。`type` 支持 `general`，适合本项目现有的前后端插件声明。[2]

官方文档介绍了 `dependencies` 中的 Python 依赖，以及通过 `requirements.txt` 安装额外依赖的方式。发布包应保留运行所需的依赖声明，不需要携带开发环境或 `node_modules`。[2] 排除本地开发环境属于本项目打包建议，不是本次确认的平台扫描规则。

`qwenpaw_version.min` 包含下界，`max` 不包含上界，即 `>=min, <max`。官方文档推荐使用这一兼容声明；`min_version` 是兼容旧插件的字段。[2]

官方打包示例是在插件目录的父目录运行 ZIP 命令，压缩单个插件目录。文档同时给出从 ZIP URL 安装的方式：[2]

```bash
qwenpaw plugin install https://example.com/my-plugin-1.0.0.zip
```

不能把普通 ZIP 分发、宿主本地安装与市场公开发布混为一谈。市场上传大小限制和许可要求来自发布平台，而上述入口和依赖规则来自宿主开发文档。[1][2]

## 4. Imagenia 的现状与发布准备

本仓库当前清单声明如下：[3]

| 项目 | 当前值 |
| --- | --- |
| 插件 ID | `imagenia` |
| 版本 | `0.1.0` |
| 类型 | `general` |
| 后端入口 | `plugin.py` |
| 前端入口 | `frontend/dist/index.js` |
| 兼容范围 | `>=2.2.1, <2.3.0` |
| 清单依赖 | `[]`；另有 `requirements.txt` 声明 FastAPI 范围 |

本次只做文件存在性检查：清单、后端入口、`src/imagenia_plugin/`、宿主前端入口和 `frontend/dist/app/` 均存在。这不等于构建产物已与当前源码同步，也不等于通过发布包安装验证。[3][4]

建议发布包至少包含以下运行材料，形成单独的暂存目录后再压缩：[3][4]

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

不要只打包前端宿主入口：工作台页面资源也在 `frontend/dist/app/`。本项目 README 的构建命令会同时生成两部分产物：[4]

```bash
cd plugin/frontend
npm run build
```

打包时应排除 `node_modules/`、虚拟环境、`__pycache__/`、`data/`、`.env`、API Key 和本机配置；这是本项目的数据和密钥边界要求。[4] 本次没有生成 ZIP，也没有验证最终压缩大小或执行构建与测试。

`plugin/` 中未发现 `LICENSE` 或 `LICENSE.txt`。平台要求接受 Apache 2.0；应在实际发布前确认项目采用该许可证，并检查需随包保留的第三方许可信息。本次没有替项目选择许可证或添加授权文件。[1][3]

现有 README 仍要求在真实 QwenPaw 中验收 iframe 鉴权、真实图像服务及安装、升级和卸载时的数据保留。历史宿主验证记录只证明当时的骨架能力，不应视为当前版本完整功能已经验收。[4][5]

## 5. 尚待登录或实际发布包验证的部分

- URL 上传具体接受哪些托管服务，以及是否必须提供直接下载地址。
- 上传后的清单解析、目录层级兼容和最终 ZIP 大小。
- 预览页的具体字段，以及是否要求图标、截图等额外材料。
- 安全扫描的详细规则、耗时、失败后的修改与重提流程。
- 扫描通过后是自动公开还是另需操作或人工审核。
- 同 ID 新版本发布、版本撤回和下架流程。

这些部分没有在本次可见页面和已读取的官方开发文档中得到完整证实，不填入推测性操作步骤。

## 来源

1. [AgentScope Platform 插件发布页](https://platform.agentscope.io/plugins/publish)：2026-10-22 浏览器直接读取初始表单，随后被重定向到登录页。
2. [QwenPaw 官方插件开发文档源文件](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md)：2026-10-22 读取 `main` 版本；重点为 Manifest Field Reference、Dependency Management、Plugin Packaging。对应[文档入口](https://qwenpaw.agentscope.io/docs/plugins)。未用旧研究笔记中的历史版本号推断当前最新版。
3. 本地 [plugin.json](../plugin/plugin.json)、[requirements.txt](../plugin/requirements.txt) 与插件文件存在性检查；核查时工作区存在尚未提交的其他修改。
4. 本地 [插件 README](../plugin/README.md) 和 [前端构建脚本](../plugin/frontend/package.json)。
5. 本地 [QwenPaw 2.2.1 集成验证记录](../plugin/docs/qwenpaw-2.2.1-verification.md)。
