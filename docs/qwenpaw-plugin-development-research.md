# QwenPaw 插件开发调研

> 调研日期：2026-09-22  
> 目标文档：[QwenPaw Plugins](https://qwenpaw.agentscope.io/docs/plugins)  
> 稳定版本基线：QwenPaw 2.2.1

## 1. 调研结论

QwenPaw 插件不是浏览器扩展，而是加载到 QwenPaw 进程中的扩展包。插件可以同时扩展：

- Agent 工具（Tool）
- LLM Provider
- Slack、LINE 等消息渠道（Channel）
- `/slash` 命令和控制命令
- FastAPI HTTP 接口
- 启动、关闭、卸载及工作区创建钩子
- AgentScope Middleware
- 记忆后端
- Skills
- Agent Mode、运行时 Hook、停止处理器和系统提示词
- Web Console 页面、菜单和聊天界面

其基本加载流程为：

1. 将插件安装到 QwenPaw 插件目录；
2. 读取插件根目录下的 `plugin.json`；
3. 检查插件 ID、版本、入口和 QwenPaw 兼容范围；
4. 安装或检查 Python 依赖；
5. 动态导入后端入口模块；
6. 查找入口模块导出的 `plugin` 对象；
7. 调用 `plugin.register(api)`；
8. 插件通过 `PluginApi` 注册工具、路由、Hook 等能力；
9. 停用或卸载时撤销注册并执行清理逻辑。

截至 2026-09-22，最新稳定版为 **QwenPaw 2.2.1**，仓库中同时存在 **2.2.2-beta.3** 预发布版。插件开发应优先以稳定版本标签为基线，不要直接依赖持续变化的 `main` 分支。

## 2. 插件目录结构

最小后端插件：

```text
my-plugin/
├── plugin.json
├── plugin.py
├── requirements.txt    # 可选
└── README.md           # 推荐
```

同时包含前后端的插件：

```text
my-plugin/
├── plugin.json
├── plugin.py
├── requirements.txt
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   └── index.tsx
└── dist/
    └── index.js
```

后端入口文件必须导出名为 `plugin` 的对象：

```python
class MyPlugin:
    def register(self, api):
        # 在这里注册扩展能力
        pass


plugin = MyPlugin()
```

QwenPaw 会将不同插件放入独立的模块命名空间，从而减少插件内部模块名称冲突。插件内部应优先使用相对导入：

```python
from .client import ApiClient
from .tools import query_data
```

## 3. `plugin.json` 清单

一个面向 QwenPaw 2.2.x 的示例：

```json
{
  "id": "hello-tool",
  "name": {
    "zh-CN": "Hello 工具",
    "en-US": "Hello Tool"
  },
  "version": "1.0.0",
  "type": "tool",
  "description": {
    "zh-CN": "一个简单的示例工具",
    "en-US": "A simple example tool"
  },
  "author": "Your Name",
  "entry": {
    "backend": "plugin.py"
  },
  "dependencies": [],
  "qwenpaw_version": {
    "min": "2.2.1",
    "max": "2.3.0"
  },
  "meta": {}
}
```

主要字段：

| 字段 | 说明 |
|---|---|
| `id` | 全局唯一插件 ID，建议仅使用小写字母、数字和连字符 |
| `name` | 插件显示名称，可使用多语言对象 |
| `version` | 插件语义化版本 |
| `type` | 如 `tool`、`provider`、`hook`、`command`、`channel`、`memory`、`frontend`、`general` |
| `entry.backend` | Python 后端入口文件 |
| `entry.frontend` | 编译后的前端 ES Module |
| `dependencies` | Python 依赖声明 |
| `qwenpaw_version.min` | 最低兼容版本，包含此版本 |
| `qwenpaw_version.max` | 首个不兼容版本，不包含此版本 |
| `meta` | UI 展示、工具配置表单等元数据 |

### 3.1 版本兼容注意事项

官方文档中的部分示例仍然使用：

```json
"qwenpaw_version": {
  "min": "1.0.0",
  "max": "2.1.0"
}
```

因为 `max` 是排他上限，这个声明不兼容当前 2.2.x 稳定版，不能直接照抄。若插件已经在整个 2.2.x 系列测试通过，可以使用：

```json
"qwenpaw_version": {
  "min": "2.2.1",
  "max": "2.3.0"
}
```

发布前应分别测试声明范围中的最低版本和当前最新稳定版本。

## 4. 最小工具插件

### 4.1 `plugin.json`

```json
{
  "id": "hello-tool",
  "name": {
    "zh-CN": "Hello 工具",
    "en-US": "Hello Tool"
  },
  "version": "1.0.0",
  "type": "tool",
  "description": "Return a greeting message",
  "author": "Your Name",
  "entry": {
    "backend": "plugin.py"
  },
  "dependencies": [],
  "qwenpaw_version": {
    "min": "2.2.1",
    "max": "2.3.0"
  },
  "meta": {
    "tools": [
      {
        "name": "say_hello",
        "description": "Return a greeting message",
        "icon": "👋",
        "requires_config": false
      }
    ]
  }
}
```

### 4.2 `plugin.py`

```python
# -*- coding: utf-8 -*-

from qwenpaw.plugins.api import PluginApi


def say_hello(name: str = "World") -> str:
    """Return a greeting.

    Args:
        name: The name to greet.
    """
    return f"Hello, {name}!"


class HelloToolPlugin:
    def register(self, api: PluginApi) -> None:
        api.register_tool(
            tool_name="say_hello",
            tool_func=say_hello,
            description="Return a greeting message",
            icon="👋",
            enabled=False,
            tool_type="internal",
        )


plugin = HelloToolPlugin()
```

工具开发建议：

- `tool_name` 必须全局唯一；
- 最好让 `tool_name` 与 Python 函数名保持一致；
- 参数应有完整的类型注解；
- docstring 应清楚描述用途及每个参数，因为这些信息会影响模型如何调用工具；
- 默认使用 `enabled=False`，由用户明确启用；
- 对参数进行严格校验，不要假设模型生成的参数总是正确；
- 返回稳定、易理解、可序列化的数据结构；
- 不要把异常堆栈、密钥或内部路径直接暴露给模型和终端用户。

工具治理类型包括：

- `internal`：内部计算，不访问外部网络或文件；
- `network`：访问外部网络；
- `file`：读写文件；
- `shell`：执行系统命令。

对于 URL、文件路径或命令等目标参数，可通过 `target_param` 指定用于治理检查的核心参数。

## 5. 带配置项的工具

配置表单声明在 `plugin.json` 的 `meta.tools` 中：

```json
{
  "meta": {
    "tools": [
      {
        "name": "query_service",
        "description": "Query an external service",
        "icon": "🌐",
        "requires_config": true,
        "config_fields": [
          {
            "name": "api_key",
            "label": "API Key",
            "type": "password",
            "required": true,
            "placeholder": "Enter API key"
          },
          {
            "name": "endpoint",
            "label": "Endpoint",
            "type": "text",
            "required": false,
            "placeholder": "https://api.example.com"
          },
          {
            "name": "timeout",
            "label": "Timeout",
            "type": "number",
            "required": false,
            "min": 5,
            "max": 300
          }
        ]
      }
    ]
  }
}
```

运行时读取当前 Agent 的工具配置：

```python
from qwenpaw.plugins import get_tool_config


async def query_service(query: str) -> dict:
    config = get_tool_config("query_service") or {}

    api_key = config.get("api_key")
    endpoint = config.get("endpoint", "https://api.example.com")
    timeout = int(config.get("timeout", 60))

    if not api_key:
        return {
            "ok": False,
            "error": "query_service 尚未配置 API Key",
        }

    # 在这里调用外部服务。
    return {
        "ok": True,
        "query": query,
        "endpoint": endpoint,
        "timeout": timeout,
    }
```

配置通常按 Agent 保存。API Key 等敏感值不应写入源码、`plugin.json`、日志或错误响应。

## 6. 后端扩展 API

基础公开能力包括：

| API | 用途 |
|---|---|
| `register_tool()` | 注册 Agent 工具 |
| `register_provider()` | 注册模型 Provider |
| `register_channel()` | 注册消息渠道 |
| `register_http_router()` | 注册 FastAPI 路由 |
| `register_startup_hook()` | 注册应用启动钩子 |
| `register_shutdown_hook()` | 注册应用关闭钩子 |
| `register_uninstall_hook()` | 注册插件卸载清理逻辑 |
| `register_workspace_created_hook()` | 注册 Agent 工作区创建钩子 |
| `register_control_command()` | 注册传统控制命令 |
| `register_middleware()` | 注入 AgentScope Middleware |
| `register_memory_backend()` | 注册记忆后端 |
| `get_tool_config()` | 读取按 Agent 保存的工具配置 |
| `set_tool_config()` | 更新工具配置 |

当前 `main` 分支源码还包含以下高级接口：

- `register_slash_command()`
- `register_mode()`
- `register_runtime_hook()`
- `register_agent_stop_handler()`
- `register_prompt_section()`
- `register_skill_provider()`

这些接口可以深入修改 Agent 循环、停止判定、系统提示词和 Skill 来源。不过它们在文档中的覆盖度不如基础 API 完整。正式项目应查看目标稳定版本标签中的 `PluginApi` 源码，而不是只根据 `main` 分支开发。

## 7. 注册 HTTP API

插件可以向 QwenPaw 的 FastAPI 应用注册路由：

```python
from fastapi import APIRouter
from qwenpaw.plugins.api import PluginApi

router = APIRouter()


@router.get("/health")
async def health():
    return {"ok": True}


class ApiPlugin:
    def register(self, api: PluginApi) -> None:
        api.register_http_router(
            router,
            prefix="/my-plugin",
            tags=["my-plugin"],
        )


plugin = ApiPlugin()
```

最终接口地址：

```text
GET /api/my-plugin/health
```

注意事项：

- `prefix` 必须以 `/` 开头；
- 不能直接使用 `/`；
- 每个路由前缀只能由一个插件占用；
- 插件路由共享 QwenPaw 的 FastAPI、CORS、认证和 OpenAPI 环境；
- 插件卸载时路由会自动移除；
- 不要绕过宿主认证机制暴露敏感接口；
- 对外部回调接口应增加签名、时间戳和重放保护。

## 8. Middleware

Middleware 适合拦截推理、工具调用或 Agent 生命周期：

```python
def build_middleware(ctx, agent_config):
    if ctx.agent_id != "target-agent":
        return None

    return MyMiddleware()


api.register_middleware(
    build_middleware,
    priority=50,
)
```

Middleware 工厂会在 Agent 构建时调用。返回 `None` 表示跳过当前 Agent。优先级数字越小，越靠近洋葱模型外层，也越早进入。

Middleware 应避免：

- 执行长时间同步阻塞操作；
- 悄悄修改关键消息而不留审计信息；
- 吞掉异常后返回不一致状态；
- 在全局对象中保存无法安全并发的数据；
- 假设 Middleware 只会被初始化一次。

## 9. Channel 插件

Channel 用于接入 Slack、LINE 或自定义消息平台。Channel 配置传入形式通常不是字典，而是 `types.SimpleNamespace`，应使用：

```python
token = getattr(config, "bot_token", "")
```

不要使用：

```python
token = config["bot_token"]
```

Channel 需要重点处理：

- 入站事件验证；
- 用户和会话映射；
- 消息去重；
- 消息顺序；
- 平台限流；
- 超长消息拆分；
- 富文本或附件降级；
- 重连和关闭清理；
- webhook 签名和重放保护。

## 10. 前端插件

前端插件一般使用 TypeScript、React 和 Vite：

```text
my-frontend-plugin/
├── plugin.json
├── src/
│   └── index.tsx
├── package.json
├── tsconfig.json
├── vite.config.ts
└── dist/
    └── index.js
```

`plugin.json`：

```json
{
  "id": "my-frontend-plugin",
  "name": "My Frontend Plugin",
  "version": "1.0.0",
  "type": "frontend",
  "entry": {
    "frontend": "dist/index.js"
  },
  "qwenpaw_version": {
    "min": "2.2.1",
    "max": "2.3.0"
  }
}
```

前端通过全局 `window.QwenPaw` 注册能力：

```tsx
const { React, antd } = window.QwenPaw.host;
const pluginId = "my-frontend-plugin";

function MyPage() {
  return <antd.Card title="Plugin Page">Hello QwenPaw</antd.Card>;
}

window.QwenPaw.route.add(pluginId, {
  id: "my-frontend-plugin.page",
  path: "/my-plugin",
  component: MyPage,
});

window.QwenPaw.menu.add(pluginId, {
  id: "my-frontend-plugin.menu",
  label: "My Plugin",
  route: "my-frontend-plugin.page",
  location: "primary.settings",
});
```

主要前端扩展点包括：

- `window.QwenPaw.host`
- `window.QwenPaw.menu`
- `window.QwenPaw.route`
- `window.QwenPaw.slot`
- `window.QwenPaw.chat.welcome`
- `window.QwenPaw.chat.sender`
- `window.QwenPaw.chat.actions`
- `window.QwenPaw.chat.requestPayload`
- `window.QwenPaw.chat.toolRender`
- `window.QwenPaw.memoryBackends`
- `window.QwenPaw.audit`

React、ReactDOM、Ant Design 由宿主提供，插件不应重复打包。Vite 应输出 ES Module，并使用 classic JSX runtime：

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react({ jsxRuntime: "classic" })],
  build: {
    lib: {
      entry: "src/index.tsx",
      formats: ["es"],
      fileName: () => "index.js",
    },
    rollupOptions: {
      external: ["react", "react-dom"],
    },
  },
});
```

注册操作通常会返回带 `dispose()` 的对象。插件卸载时也会按 `pluginId` 清理对应注册。

## 11. 安装与调试

```bash
# 安装本地插件
qwenpaw plugin install ./hello-tool

# 覆盖安装
qwenpaw plugin install ./hello-tool --force

# 查看插件列表
qwenpaw plugin list

# 查看插件详情
qwenpaw plugin info hello-tool

# 启动应用
qwenpaw app

# 卸载插件
qwenpaw plugin uninstall hello-tool
```

如果 QwenPaw 正在运行，CLI 会尝试调用热安装 API；未运行时则复制插件文件，等待下次启动时加载。插件还可以打包为 ZIP，或者从 URL 安装。

日志排查：

```bash
tail -f ~/.qwenpaw/logs/qwenpaw.log | grep -i plugin
```

推荐开发循环：

1. 锁定目标 QwenPaw 稳定版本；
2. 创建最小 `plugin.json` 和入口文件；
3. 第一次只实现一个扩展能力；
4. 本地安装；
5. 检查日志中的加载和注册信息；
6. 在控制台中启用并配置；
7. 测试正常调用和异常输入；
8. 测试重启、热安装和覆盖安装；
9. 测试停用和卸载；
10. 测试多个 Agent 的配置隔离；
11. 测试依赖缺失、配置缺失和外部服务超时；
12. 最后打 ZIP 发布。

## 12. 安全与工程风险

### 12.1 插件没有进程级安全隔离

Python 后端插件直接运行在 QwenPaw 进程中，通常具有与 QwenPaw 相同的文件、网络和环境变量访问权限。因此：

- 只安装可信来源的插件；
- 发布前进行依赖和源码审计；
- 尽量使用最小权限；
- 不读取与插件无关的文件或环境变量；
- 不记录访问令牌、Cookie、API Key 或用户原始敏感内容。

### 12.2 名称和前缀冲突

以下标识必须按全局唯一设计：

- 工具名；
- HTTP 路由前缀；
- 命令名；
- 前端路由 ID；
- 菜单项 ID；
- Slot 注册 ID。

建议全部使用插件 ID 作为前缀：

```text
acme-search.query
acme-search.settings
/acme-search
```

### 12.3 不要直接修改宿主内部配置

不要直接编辑 `agent.json` 或修改宿主内部 Registry，应通过 `PluginApi`、工具配置接口和工作区 Hook 完成扩展。

### 12.4 不要依赖内部模块

优先从稳定公开路径导入接口。例如记忆插件应优先从 `qwenpaw.memory` 导入公开契约，不要依赖容易变化的内部实现路径。

### 12.5 清理后台资源

如果插件创建了以下资源，应同时实现关闭和卸载清理：

- 后台任务；
- 定时器；
- HTTP Client；
- 数据库连接池；
- WebSocket；
- 临时文件；
- 工作区生成文件；
- 外部 webhook 注册。

### 12.6 依赖版本冲突

插件依赖安装到宿主运行环境后，可能与 QwenPaw 或其他插件发生冲突。应：

- 尽量减少第三方依赖；
- 设置合理的版本范围；
- 避免强行升级宿主核心依赖；
- 对大型 SDK 考虑使用 HTTP API 替代；
- 在干净环境中重复安装测试。

## 13. 建议的实施路线

### 第一阶段：工具插件

实现：

- `register_tool()`；
- `meta.tools.config_fields`；
- 按 Agent 保存配置；
- 参数验证；
- 网络请求、超时、重试和错误处理。

### 第二阶段：后端接口

实现：

- `register_http_router()`；
- 健康检查；
- 前端所需 API；
- 外部系统 webhook。

### 第三阶段：前端管理界面

实现：

- `window.QwenPaw.route`；
- `window.QwenPaw.menu`；
- 使用宿主请求接口访问插件后端；
- 展示配置状态、调用日志和健康状态。

### 第四阶段：高级 Agent 集成

按需实现：

- Middleware；
- Runtime Hook；
- Prompt Section；
- Skill Provider；
- Agent Mode；
- Agent Stop Handler。

对于多数业务插件，推荐的完整形态是：

```text
后端工具 + FastAPI 接口 + 前端管理页面
```

## 14. 发布前检查清单

- [ ] 插件 ID 全局唯一且命名稳定；
- [ ] `plugin.json` 字段完整；
- [ ] 兼容范围覆盖实际测试版本；
- [ ] 没有照抄过期的 `max: 2.1.0`；
- [ ] 工具默认关闭或符合安全预期；
- [ ] 所有参数有类型注解和描述；
- [ ] 配置缺失时返回清晰错误；
- [ ] API Key 未出现在源码和日志中；
- [ ] 网络请求设置连接和读取超时；
- [ ] 路由具有必要的认证或签名校验；
- [ ] 工具名、命令名和路由前缀不存在冲突；
- [ ] 后台任务和连接可以正常关闭；
- [ ] 覆盖安装不会残留旧状态；
- [ ] 卸载后没有残留路由、任务和文件；
- [ ] 已在最低支持版本测试；
- [ ] 已在最新稳定版本测试；
- [ ] 已测试多个 Agent 的配置隔离；
- [ ] 已测试依赖缺失、外部服务失败和超时；
- [ ] README 包含安装、配置、权限和卸载说明。

## 15. 参考资料

- [QwenPaw 插件文档](https://qwenpaw.agentscope.io/docs/plugins)
- [QwenPaw GitHub 仓库](https://github.com/agentscope-ai/QwenPaw)
- [QwenPaw Releases](https://github.com/agentscope-ai/QwenPaw/releases)
- [插件文档源文件](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md)
- [PluginApi 源码](https://github.com/agentscope-ai/QwenPaw/blob/main/src/qwenpaw/plugins/api.py)
- [官方 GPT Image 2 插件清单](https://github.com/agentscope-ai/QwenPaw/blob/main/plugins/tool/gpt-image2/plugin.json)
- [官方 GPT Image 2 插件实现](https://github.com/agentscope-ai/QwenPaw/blob/main/plugins/tool/gpt-image2/gpt_image2.py)
