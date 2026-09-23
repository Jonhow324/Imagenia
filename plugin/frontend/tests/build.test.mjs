import assert from "node:assert/strict"
import { readFile, readdir } from "node:fs/promises"
import { test } from "node:test"

const output = new URL("../dist/", import.meta.url)

test("Blob-loaded host entry registers the menu and route without importing another React", async () => {
  const source = await readFile(new URL("index.js", output), "utf8")
  assert.doesNotMatch(source, /\b(?:import|export)\s+(?:[^('"`]|$)/m)
  assert.doesNotMatch(source, /react-dom|useState|workbench/i)

  const registrations = { routes: [], menus: [] }
  const calls = []
  globalThis.window = {
    QwenPaw: {
      host: { React: { createElement: (...args) => { calls.push(args); return args } } },
      route: { add: (...args) => registrations.routes.push(args) },
      menu: { add: (...args) => registrations.menus.push(args) },
    },
  }
  try {
    // A data: URL models the host's import(Blob URL) without filesystem-relative imports.
    await import(`data:text/javascript,${encodeURIComponent(source)}`)
    assert.equal(registrations.routes.length, 1)
    assert.equal(registrations.menus.length, 1)
    assert.equal(registrations.routes[0][0], "imagenia")
    assert.equal(registrations.routes[0][1].path, "/imagenia")
    assert.equal(registrations.menus[0][1].route, "imagenia.home")
    assert.equal(registrations.menus[0][1].location, "primary.settings")
    registrations.routes[0][1].component()
    assert.equal(calls[0][0], "iframe")
    assert.equal(calls[0][1].src, "/api/frontend_plugin/imagenia/files/frontend/dist/app/index.html")
    assert.ok(calls[0][1].title)
  } finally {
    delete globalThis.window
  }
})

test("SPA has relative JS/CSS assets and a bundled React runtime", async () => {
  const app = new URL("app/", output)
  const html = await readFile(new URL("index.html", app), "utf8")
  assert.match(html, /(?:src|href)="\.\/assets\//)
  const files = await readdir(new URL("assets/", app))
  assert.ok(files.some(file => file.endsWith(".js")))
  assert.ok(files.some(file => file.endsWith(".css")))
  const scripts = await Promise.all(files.filter(file => file.endsWith(".js")).map(file => readFile(new URL(`assets/${file}`, app), "utf8")))
  assert.ok(scripts.some(source => source.includes("react-dom")), "React DOM should be inside the iframe SPA")
})
