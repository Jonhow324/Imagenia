// The host loads this file via a Blob URL. Keep it self-contained: no imports,
// JSX transform, workbench components, or bundled React runtime belong here.
const pluginId = "imagenia"
const workbenchUrl = "/api/frontend_plugin/imagenia/files/frontend/dist/app/index.html"

function ImageniaRoute() {
  const React = window.QwenPaw.host.React

  return React.createElement("iframe", {
    title: "Imagenia 工作台",
    src: workbenchUrl,
    style: {
      display: "block",
      width: "100%",
      height: "100vh",
      minHeight: "600px",
      border: 0,
    },
  })
}

window.QwenPaw.route.add(pluginId, {
  id: "imagenia.home",
  path: "/imagenia",
  component: ImageniaRoute,
})

window.QwenPaw.menu.add(pluginId, {
  id: "imagenia.home",
  label: "Imagenia",
  route: "imagenia.home",
  location: "primary.settings",
})
