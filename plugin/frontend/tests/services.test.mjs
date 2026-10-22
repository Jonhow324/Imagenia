import assert from "node:assert/strict"
import { test } from "node:test"
import { getServices, saveService, deleteService, setDefaultService, testServiceConnection } from "../src/services/settings.ts"
import { initialServiceSelection, rememberServiceSelection, selectedServiceModel } from "../src/services/service-selection.ts"
import { enqueueGeneration, getJob } from "../src/services/generation.ts"

const model = { id: "model-a", name: "image-model", sizes: ["square"], qualities: ["standard"], supports_edit: false }
const service = { id: "a", provider: "openai", name: "Service A", configured: true, enabled: true, read_only: false, active_jobs: 0, models: [model] }
const providers = [
  { id: "openai", name: "OpenAI 图像", base_url: "https://api.openai.com/v1", models: [{ ...model, supports_edit: true }] },
  { id: "minimax", name: "MiniMax 图像", base_url: "https://api.minimax.cn/v1", models: [{ ...model, name: "image-01" }] },
  { id: "custom", name: "自定义兼容服务", base_url: "", models: [] },
]
const catalog = { services: [service], default: { service_id: "a", model_id: "model-a" }, providers }

test("service CRUD/default are authenticated and connection checks happen only explicitly", async () => {
  const calls = []
  globalThis.localStorage = { getItem: () => "session-secret" }
  globalThis.fetch = async (url, init) => { calls.push({ url, init }); return Response.json(catalog) }
  await getServices()
  await saveService({ provider: "minimax", name: "Service A", api_key: "sk-private", base_url: "https://a.example/v1", models: [model], enabled: true })
  await saveService({ provider: "custom", name: "renamed", base_url: "https://a.example/v1", models: [model], enabled: true }, "a")
  await setDefaultService(catalog.default)
  assert.ok(calls.every(call => !call.url.endsWith("/test")))
  await testServiceConnection("a")
  await deleteService("a")
  assert.deepEqual(calls.map(call => [call.init.method ?? "GET", call.url]), [
    ["GET", "/api/imagenia/services"], ["POST", "/api/imagenia/services"], ["PUT", "/api/imagenia/services/a"],
    ["PUT", "/api/imagenia/services/default"], ["POST", "/api/imagenia/services/a/test"], ["DELETE", "/api/imagenia/services/a"],
  ])
  assert.ok(calls.every(call => call.init.headers.Authorization === "Bearer session-secret" && !call.url.includes("sk-private")))
  assert.equal(JSON.parse(calls[1].init.body).provider, "minimax")
  assert.equal(JSON.parse(calls[2].init.body).api_key, undefined)
})

test("remembered unavailable choices never silently fall back to the global default", () => {
  let remembered = null
  globalThis.localStorage = { getItem: () => remembered, setItem: (_, value) => { remembered = value } }
  assert.deepEqual(initialServiceSelection(catalog), catalog.default)
  const removed = { service_id: "deleted", model_id: "old-model" }
  rememberServiceSelection(removed)
  assert.deepEqual(initialServiceSelection(catalog), removed)
  assert.equal(selectedServiceModel(catalog, removed, false).valid, false)
  rememberServiceSelection(catalog.default)
  assert.equal(selectedServiceModel(catalog, initialServiceSelection(catalog), false).valid, true)
  assert.equal(selectedServiceModel(catalog, initialServiceSelection(catalog), true).valid, false)
  assert.equal(selectedServiceModel({ ...catalog, services: [{ ...service, enabled: false }] }, catalog.default, false).valid, false)
})

test("restricted storage does not prevent an explicit service selection", () => {
  globalThis.localStorage = { getItem() { throw Error("disabled") }, setItem() { throw Error("disabled") } }
  assert.deepEqual(initialServiceSelection(catalog), catalog.default)
  assert.doesNotThrow(() => rememberServiceSelection(catalog.default))
})

test("generation and edits submit the exact service/model and preserve failure retry context", async () => {
  const calls = []
  globalThis.localStorage = { getItem: () => null }
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init })
    if (url.endsWith("/generate") || url.endsWith("/edit")) return Response.json({ job_id: "job" }, { status: 202 })
    return Response.json({ id: "job", kind: "edit", prompt: "original prompt", status: "failed", created_at: "now",
      error_message: "服务配置已变化", service_id: "a", model_id: "model-a", service_name: "Service A", model: "image-model",
      options: { size: "square", quality: "standard" }, source_asset_id: "source" })
  }
  const input = { prompt: "original prompt", serviceId: "a", modelId: "model-a", size: "square", quality: "standard" }
  await enqueueGeneration(input)
  await enqueueGeneration({ ...input, sourceAssetId: "source" })
  assert.deepEqual(JSON.parse(calls[0].init.body), { prompt: input.prompt, size: "square", quality: "standard", service_id: "a", model_id: "model-a" })
  assert.equal(JSON.parse(calls[1].init.body).source_asset_id, "source")
  const failed = await getJob("job")
  assert.equal(failed.serviceId, "a")
  assert.equal(failed.modelId, "model-a")
  assert.equal(failed.sourceAssetId, "source")
  assert.deepEqual(failed.options, { size: "square", quality: "standard" })
  assert.equal(calls.length, 3, "reading a failed job never triggers automatic retries")
})

test("configuration conflicts and auth errors remain safe", async () => {
  globalThis.localStorage = { getItem: () => "session-secret" }
  globalThis.fetch = async () => Response.json({ error: { code: "service_in_use", message: "sk-sensitive /private/path" } }, { status: 409 })
  await assert.rejects(deleteService("a"), error => error.code === "service_in_use" && !String(error).includes("sk-sensitive"))
  globalThis.fetch = async () => new Response("session-secret", { status: 401 })
  await assert.rejects(getServices(), error => error.code === "unauthorized" && !String(error).includes("session-secret"))
})
