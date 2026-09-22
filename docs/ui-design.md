# Imagenia V1 UI 设计基线

## 技术边界

前端采用 TypeScript、React、Vite、Tailwind CSS 和 shadcn/ui。QwenPaw 宿主负责 React/ReactDOM、插件加载、菜单和路由注册；Vite 输出 ES Module，React/ReactDOM 作为 external，不在插件 bundle 中重复打包。shadcn 组件源码放在插件自己的 `frontend/` 工程内。

不要使用 shadcn `Sidebar` 替代 QwenPaw 宿主主导航；Imagenia 应通过 QwenPaw 菜单 API 注册入口。后端请求方式以目标 QwenPaw 稳定版本公开 API 为准，不预先假设某个未验证的宿主 fetch API。

## 设计方向

Imagenia 使用 shadcn/ui 风格：克制、清晰、可组合、图片优先。这里的“使用 shadcn”指采用其视觉语言、组件行为和可访问性约束；如果目标前端技术栈支持，则直接引入并保留组件源码，以便后续定制，而不是把 UI 锁定在不可修改的黑盒主题中。

## 页面布局

- **桌面端**：左侧为生成控制区，右侧为资料库瀑布流；顶部显示插件名称、配置入口和收藏筛选。
- **窄屏**：控制区、任务列表和资料库改为单列；详情使用抽屉或全屏面板。
- **图片详情**：使用 `Sheet` 或 `Dialog`，展示大图、提示词、尺寸、模型、创建时间和来源图片，并提供编辑、收藏、删除操作。

## 组件与状态

优先使用 shadcn/ui 对应的 `Button`、`Textarea`、`Select`、`Card`、`Badge`、`Tabs`、`Sheet`、`AlertDialog`、`Alert`、`Skeleton`、`Toast`、`Tooltip` 和 `Sidebar`。

必须覆盖：

- 未配置 API Key；
- 空资料库；
- 表单校验失败；
- 排队、生成中、成功和失败；
- 生成中按钮禁用与 loading；
- 删除二次确认；
- 收藏成功或失败反馈；
- 加载更多和加载失败。

## 视觉约束

- 使用中性灰阶、细边框、适度圆角和低强度阴影。
- 使用明确的 primary、success、warning、destructive 状态颜色。
- 图片卡片减少文字堆叠，悬停操作不能是唯一操作入口。
- 图标按钮必须有可访问名称和 Tooltip。
- 保留键盘焦点、语义化表单标签和足够的文字对比度。

## 样式隔离

由于插件运行在 QwenPaw Console 内，必须验证 Tailwind 样式不会污染宿主。优先尝试 Shadow DOM；如果宿主不支持，则使用 Tailwind 前缀和插件根节点作用域 CSS variables。

## 工单交付物

UI 工单不要求先做完整视觉稿，交付以下内容即可：

1. 本文档中的布局、组件和状态约束；
2. 使用 mock 数据的工作台静态页面或组件展示页；
3. 桌面端和窄屏截图；
4. 生成、编辑、收藏、删除四条关键流程的交互说明。

实现前端时，先完成这些 mock 状态，再接入后端 HTTP API。

## QwenPaw 集成策略

QwenPaw 前端插件通过 `plugin.json` 的 `entry.frontend` 加载 JavaScript bundle，并由宿主提供 React、ReactDOM 和 Ant Design。Imagenia 不应修改 QwenPaw Console，也不应把 React/ReactDOM 重复打包。

建议在插件内建立独立的 `frontend/` Vite + React + TypeScript 工程：

1. 使用 shadcn 的 Vite 初始化流程建立 Tailwind 和 `components.json`；
2. 只添加 Imagenia 实际需要的组件；
3. Vite 使用 classic JSX runtime，并 externalize `react` 和 `react-dom`，直接使用 QwenPaw 宿主版本；
4. 将 Tailwind 生成的 CSS 随插件 bundle 注入插件页面，避免依赖 QwenPaw 全局样式；
5. 通过 `window.QwenPaw.menu.add` 注册侧边栏入口，通过 `window.QwenPaw.route.add` 注册 Imagenia 页面；
6. 后端请求方式以目标 QwenPaw 稳定版本的公开 API 为准，不预先假设存在 `window.QwenPaw.host.fetch`。

因此，Imagenia 使用的是“插件内的 shadcn 组件源码 + Tailwind 样式”，React 渲染运行时复用 QwenPaw 宿主，不把 shadcn 安装到 QwenPaw 主仓库。QwenPaw 的路由和菜单注册沿用宿主 API；后端 HTTP 调用则在插件骨架工单中根据稳定版本 API 完成验证。
