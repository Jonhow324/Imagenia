import assert from "node:assert/strict"
import { test } from "node:test"
import { getSettings, saveSettings, testConnection } from "../src/services/settings.ts"

test("iframe sends bearer authorization for status, save and explicit connection test", async () => {
  const calls = []
  globalThis.localStorage = { getItem: (name) => name === "qwenpaw_auth_token" ? "host-session-token" : null }
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return new Response(JSON.stringify(url.endsWith("/test") ? { status: "ok" } : { openai: { configured: true, source: "file", base_url: "https://proxy.example/v1", model: "gpt-image-2.5" } }), { status: 200 })
  }
  const initial = await getSettings()
  const updated = await saveSettings({ api_key: "sk-sensitive", base_url: "https://proxy.example/v1", model: "gpt-image-2.5-flare" })
  await testConnection()
  assert.equal(initial.openai.base_url, "https://proxy.example/v1")
  assert.equal(updated.openai.model, "gpt-image-2.5")
  assert.deepEqual(calls.map(({ url }) => url), [
    "/api/imagenia/settings", "/api/imagenia/settings/openai", "/api/imagenia/settings/openai/test",
  ])
  assert.ok(calls.every(({ options }) => options.headers.Authorization === "Bearer host-session-token"))
  assert.deepEqual(JSON.parse(calls[1].options.body), { api_key: "sk-sensitive", base_url: "https://proxy.example/v1", model: "gpt-image-2.5-flare" })
  assert.ok(calls.every(({ url }) => !url.includes("sk-sensitive") && !url.includes("host-session-token")))
})

test("401 is a safe login-expired error, never exposing a token or response body", async () => {
  globalThis.localStorage = { getItem: () => "secret-session" }
  globalThis.fetch = async () => new Response("authorization: secret-session", { status: 401 })
  await assert.rejects(getSettings(), error => error.code === "unauthorized" && !String(error).includes("secret-session"))
})
