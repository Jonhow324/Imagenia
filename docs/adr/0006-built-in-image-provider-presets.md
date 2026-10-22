# ADR 0006：内置图像服务协议与预设

- 状态：已接受
- 日期：2026-10-22
- 扩展：ADR 0005 的多服务配置；任务绑定、排队保护、删除保留历史及旧配置升级规则继续适用。

ADR 0005 把所有服务视为同一种 OpenAI Images 兼容接口。实际使用中，OpenAI 与 MiniMax 的官方接口在端点、请求字段和响应结构上不同，而用户仍需要一个可填写任意兼容网关的“自定义”入口。因此每套服务增加 `provider` 协议类型，用于选择适配器并提供可发现的内置预设；不引入自动协议探测、参数猜测或失败后切换服务。

## 决策

服务配置新增 `provider`，取值为 `openai`、`minimax` 或 `custom`。`services.json` 升级为 `version: 2`。读取旧 `version: 1` 文件时，现有服务（包括 `legacy` 与环境配置）按 `custom` 处理，即继续使用原有 OpenAI Images 兼容适配器，行为不变；下次保存时写成版本 2。

- `openai`：`POST {base_url}/images/generations`，编辑使用 multipart `POST {base_url}/images/edits`；默认根地址 `https://api.openai.com/v1`，预设模型 `gpt-image-1`。生成响应读取 `data[0].b64_json`。
- `minimax`：`POST {base_url}/image_generation`，默认根地址 `https://api.minimax.cn/v1`（国际版为 `https://api.minimax.io/v1`），预设模型 `image-01`。请求发送 `model`、`prompt`、`aspect_ratio`、`response_format: "base64"` 和 `n: 1`；响应读取 `data.image_base64[0]`，并检查 `base_resp.status_code`。MiniMax 没有质量参数和图片编辑接口，因此预设只声明 `standard` 质量且不启用编辑。
- `custom`：保留原有行为，任意 OpenAI Images 兼容根地址、密钥和模型能力声明；适配器仍为 `OpenAIImageProvider`。

`GET /api/imagenia/services` 在原有 `services` 和 `default` 之外返回 `providers` 预设（不含密钥）。预设只用于创建服务时填充名称、根地址和模型，保存后仍是独立服务；界面允许修改地址、模型与能力声明。服务类型创建后不在界面修改，需要更换协议时新增服务。

连接指纹对 `custom` 保持原来的三元组 `[base_url, api_key, model]`，避免升级使已排队任务失效；`openai` 和 `minimax` 在末尾追加协议名。任务执行时按提交时的 `provider` 建立对应适配器，仍不自动切换或重试。

图像生成结果不再限定 PNG。工作线程验证 PNG 与 JPEG 的实际字节和尺寸，按真实格式保存 `.png` 或 `.jpg` 并记录 `mime_type`；内容接口返回对应媒体类型。这样 MiniMax 返回的 base64 JPEG 可直接保存，不需要引入图像转码依赖。OpenAI 兼容编辑以来源图片的真实媒体类型发送 multipart；MiniMax 模型不声明编辑能力。

连接测试仍只对已保存服务发出只读 `GET {base_url}/models` 请求；MiniMax 提供同路径的 OpenAI 兼容模型列表接口。测试认证通过不代表生成或编辑能力已验证。

## 后果

- 现有配置与已排队任务无需手工迁移；旧服务显示为“自定义”。
- 设置接口和前端需要处理 `provider` 与 `providers`；旧客户端省略 `provider` 时新服务默认 `custom`，更新时保留原值。
- MiniMax 的 `standard`/`high` 没有 API 级差异；预设只暴露 `standard`，自定义服务若声明 `high`，适配器仍不发送质量字段。
- 有活动任务时禁止更改 `provider`、地址、密钥，或移除／重命名已有模型；这与 ADR 0005 的连接保护一致。
- 图像库现在可能包含 JPEG；删除、恢复和来源编辑都按实际后缀与媒体类型处理。

## 参考

- OpenAI Images API：<https://developers.openai.com/api/reference/resources/images>
- MiniMax 图片生成指南：<https://platform.minimax.cn/docs/guides/image-generation>
- MiniMax 文生图接口：<https://platform.minimax.cn/docs/api-reference/image-generation-t2i>
- MiniMax OpenAI 兼容模型列表（用于只读连接测试）：<https://platform.minimax.io/docs/api-reference/models/openai/list-models>
