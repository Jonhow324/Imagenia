import assert from "node:assert/strict"
import { test } from "node:test"
import { enqueueGeneration, getJob, listAssets, listJobs } from "../src/services/generation.ts"

test("iframe submits and polls with host Bearer token and loads authenticated image", async () => {
  const calls = []
  globalThis.localStorage = { getItem: () => "session-secret" }
  URL.createObjectURL = () => "blob:verified-image"
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init })
    if (url.endsWith("/generate")) return Response.json({ job_id: "job-1", status: "pending" }, { status: 202 })
    if (url.endsWith("/jobs/job-1")) return Response.json({ id: "job-1", kind: "generate", prompt: "blue sky", status: "succeeded", created_at: "now", result_asset_id: "asset-1", error_message: null })
    if (url.endsWith("/jobs")) return Response.json({ items: [] })
    if (url.endsWith("/assets")) return Response.json({ items: [{ id: "asset-1", kind: "generated", prompt: "blue sky", model: "gpt-image-1", size: "square", width: 1, height: 1, created_at: "now", is_favorite: false, source_asset_id: null }] })
    if (url.endsWith("/content")) return new Response(new Blob(["png"], { type: "image/png" }), { headers: { "content-type": "image/png" } })
    throw new Error("unexpected URL")
  }
  assert.equal(await enqueueGeneration({ prompt: "blue sky", size: "square", quality: "standard" }), "job-1")
  assert.equal((await getJob("job-1")).status, "succeeded")
  assert.deepEqual(await listJobs(), [])
  assert.equal((await listAssets())[0].imageUrl, "blob:verified-image")
  assert.ok(calls.every(({ init }) => init.headers.Authorization === "Bearer session-secret"))
  assert.ok(calls.every(({ url }) => !url.includes("session-secret")))
  assert.deepEqual(JSON.parse(calls[0].init.body), { prompt: "blue sky", size: "square", quality: "standard" })
})

test("generation 401 remains safe and does not parse or echo server body", async () => {
  globalThis.localStorage = { getItem: () => "session-secret" }
  globalThis.fetch = async () => new Response("Authorization: Bearer session-secret", { status: 401 })
  await assert.rejects(getJob("job-1"), err => err.code === "unauthorized" && !String(err).includes("session-secret"))
  await assert.rejects(enqueueGeneration({ prompt: "blue sky", size: "square", quality: "standard" }), err => err.code === "unauthorized" && !String(err).includes("session-secret"))
})

test("edit submits only the source ID and options, then polls an edit job", async () => {
  const calls = []
  globalThis.localStorage = { getItem: () => "session-secret" }
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init })
    if (url.endsWith("/edit")) return Response.json({ job_id: "edit-1", status: "pending" }, { status: 202 })
    if (url.endsWith("/jobs/edit-1")) return Response.json({ id: "edit-1", kind: "edit", prompt: "make blue", status: "succeeded", created_at: "now", result_asset_id: "edited-1", error_message: null })
    throw new Error("unexpected request")
  }
  assert.equal(await enqueueGeneration({ prompt: "make blue", sourceAssetId: "source-1", size: "square", quality: "standard" }), "edit-1")
  const requestBody = JSON.parse(calls[0].init.body)
  assert.deepEqual(requestBody, { prompt: "make blue", size: "square", quality: "standard", source_asset_id: "source-1" })
  assert.equal(calls[0].init.headers["Content-Type"], "application/json")
  assert.equal(calls[0].init.headers.Authorization, "Bearer session-secret")
  assert.deepEqual(await getJob("edit-1"), { id: "edit-1", kind: "edit", prompt: "make blue", status: "succeeded", createdAt: "now", errorMessage: undefined, resultAssetId: "edited-1" })
})
