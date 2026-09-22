// QwenPaw frontend extension entry. The host supplies React and ReactDOM.
const pluginId = "imagenia";
const { React } = window.QwenPaw.host;

function ImageniaPage() {
  return React.createElement(
    "div",
    { style: { maxWidth: 1180, margin: "0 auto", padding: 32 } },
    React.createElement("h1", null, "Imagenia"),
    React.createElement("p", null, "本地 AI 图像工作台（mock 骨架）"),
    React.createElement("p", null, "后端健康检查：/api/imagenia/health"),
  );
}

window.QwenPaw.route.add(pluginId, {
  id: "imagenia.home",
  path: "/imagenia",
  component: ImageniaPage,
});
window.QwenPaw.menu.add(pluginId, {
  id: "imagenia.home",
  label: "Imagenia",
  icon: "image",
  route: "imagenia.home",
  location: "primary.agentScoped",
});
