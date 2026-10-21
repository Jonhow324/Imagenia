//#region src/index.ts
var e = "imagenia";
function t() {
	return window.QwenPaw.host.React.createElement("img", {
		src: "/api/frontend_plugin/imagenia/files/icon.svg",
		width: 20,
		height: 20,
		alt: "",
		"aria-hidden": !0,
		style: {
			display: "block",
			flexShrink: 0
		}
	});
}
function n() {
	return window.QwenPaw.host.React.createElement("iframe", {
		title: "Imagenia 工作台",
		src: "/api/frontend_plugin/imagenia/files/frontend/dist/app/index.html",
		style: {
			display: "block",
			width: "100%",
			height: "100vh",
			minHeight: "600px",
			border: 0
		}
	});
}
window.QwenPaw.route.add(e, {
	id: "imagenia.home",
	path: "/imagenia",
	component: n
}), window.QwenPaw.menu.add(e, {
	id: "imagenia.home",
	label: "Imagenia",
	icon: t,
	route: "imagenia.home",
	location: "primary.settings"
});
//#endregion
