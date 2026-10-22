// The host loads this file via a Blob URL. Keep it self-contained: no imports,
// JSX transform, workbench components, or bundled React runtime belong here.
const pluginId = "imagenia"
const workbenchUrl = "/api/frontend_plugin/imagenia/files/frontend/dist/app/index.html"

function ImageniaIcon() {
  const React = window.QwenPaw.host.React

  return React.createElement("img", {
    src: "/api/frontend_plugin/imagenia/files/icon.svg",
    width: 20,
    height: 20,
    alt: "",
    "aria-hidden": true,
    style: { display: "block", flexShrink: 0 },
  })
}

function ImageniaRoute() {
  const React = window.QwenPaw.host.React
  let detach = () => {}

  function attach(element: HTMLIFrameElement | null) {
    detach()
    if (!element) return
    const resize = () => {
      const bottomPadding = element.parentElement
        ? Number.parseFloat(window.getComputedStyle(element.parentElement).paddingBottom) || 0
        : 0
      // The route sits below host navigation; 100vh would make the host scroll.
      const height = Math.max(0, window.innerHeight - Math.max(0, element.getBoundingClientRect().top) - bottomPadding)
      element.style.height = `${height}px`
    }
    resize()
    window.addEventListener("resize", resize)
    const observer = new ResizeObserver(resize)
    if (element.parentElement) observer.observe(element.parentElement)
    detach = () => {
      window.removeEventListener("resize", resize)
      observer.disconnect()
    }
  }

  return React.createElement("iframe", {
    ref: attach,
    title: "Imagenia 工作台",
    src: workbenchUrl,
    style: {
      display: "block",
      width: "100%",
      height: "100%",
      minHeight: 0,
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
  icon: ImageniaIcon,
  route: "imagenia.home",
  location: "primary.settings",
})
