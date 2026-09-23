import assert from "node:assert/strict"
import { test } from "node:test"
import { getAsset, listAssetPage } from "../src/services/generation.ts"

const resource = (id, kind = "generated") => ({ id, kind, prompt: "view", model: "model",
  size: "square", width: 1024, height: 1024, created_at: "2026-09-24", is_favorite: true,
  source_asset_id: kind === "edited" ? "source-1" : null })

function fixture() {
  const calls = []
  const revoked = []
  let created = 0
  globalThis.localStorage = { getItem: () => "private-session" }
  URL.createObjectURL = () => `blob:asset-${++created}`
  URL.revokeObjectURL = (url) => revoked.push(url)
  return { calls, revoked }
}

test("filtered cursor page and direct detail use authenticated content without token URLs", async () => {
  const { calls } = fixture()
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init })
    if (url.includes("?")) return Response.json({ items: [resource("edited-1", "edited")], next_cursor: "opaque-next" })
    if (url.endsWith("/content")) return new Response(new Blob(["png"], { type: "image/png" }),
      { headers: { "content-type": "image/png" } })
    if (url.endsWith("/assets/source-1")) return Response.json(resource("source-1"))
    throw Error("unexpected URL")
  }
  const page = await listAssetPage({ favorite: true, kind: "edited", cursor: "opaque-prev" })
  assert.equal(page.nextCursor, "opaque-next")
  assert.equal(page.items[0].imageUrl, "blob:asset-1")
  assert.equal(page.items[0].sourceAssetId, "source-1")
  assert.equal((await getAsset("source-1")).imageUrl, "blob:asset-2")
  assert.equal(calls[0].url, "/api/imagenia/assets?favorite=true&kind=edited&cursor=opaque-prev")
  assert.ok(calls.every(({ url, init }) => init.headers.Authorization === "Bearer private-session" && !url.includes("private-session")))
})

test("partial page failure revokes every created object URL and preserves safe 401", async () => {
  const { revoked } = fixture()
  globalThis.fetch = async (url) => {
    if (url.endsWith("/assets")) return Response.json({ items: [resource("good"), resource("bad")], next_cursor: null })
    if (url.endsWith("/good/content")) return new Response(new Blob(["png"]), { headers: { "content-type": "image/png" } })
    if (url.endsWith("/bad/content")) return new Response("private-session", { status: 401 })
    throw Error("unexpected URL")
  }
  await assert.rejects(listAssetPage(), (error) => error.code === "unauthorized" && !String(error).includes("private-session"))
  assert.deepEqual(revoked, ["blob:asset-1"])
})

test("aborted image page revokes completed image URLs", async () => {
  const { revoked } = fixture()
  const controller = new AbortController()
  globalThis.fetch = async (url) => {
    if (url.endsWith("/assets")) return Response.json({ items: [resource("one")], next_cursor: null })
    controller.abort()
    return new Response(new Blob(["png"]), { headers: { "content-type": "image/png" } })
  }
  await assert.rejects(listAssetPage({ signal: controller.signal }))
  assert.deepEqual(revoked, []) // abort before createObjectURL: nothing to revoke
})

test("favorite and deletion send authenticated mutation and preserve safe failures", async () => {
  const { favoriteAsset, deleteAsset } = await import("../src/services/generation.ts")
  const { calls } = fixture()
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init })
    if (init.method === "PATCH") return Response.json({ ...resource("one"), is_favorite: false })
    if (init.method === "DELETE") return Response.json({ deleted: true })
    throw Error("unexpected URL")
  }
  assert.equal((await favoriteAsset("one", false)).isFavorite, false)
  await deleteAsset("one")
  assert.equal(calls[0].init.body, '{"is_favorite":false}')
  assert.equal(calls[0].init.headers.Authorization, "Bearer private-session")
  assert.equal(calls[1].init.method, "DELETE")
  assert.equal(calls[1].init.headers.Authorization, "Bearer private-session")
  globalThis.fetch = async () => Response.json({ error: { code: "not_found" } }, { status: 404 })
  await assert.rejects(favoriteAsset("one", true), (error) => error.code === "not_found")
  await assert.rejects(deleteAsset("one"), (error) => error.code === "not_found")
})
