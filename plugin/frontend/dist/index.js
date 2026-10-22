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
	let e = window.QwenPaw.host.React, t = () => {};
	function n(e) {
		if (t(), !e) return;
		let n = () => {
			let t = e.parentElement && Number.parseFloat(window.getComputedStyle(e.parentElement).paddingBottom) || 0, n = Math.max(0, window.innerHeight - Math.max(0, e.getBoundingClientRect().top) - t);
			e.style.height = `${n}px`;
		};
		n(), window.addEventListener("resize", n);
		let r = new ResizeObserver(n);
		e.parentElement && r.observe(e.parentElement), t = () => {
			window.removeEventListener("resize", n), r.disconnect();
		};
	}
	return e.createElement("iframe", {
		ref: n,
		title: "Imagenia 工作台",
		src: "/api/frontend_plugin/imagenia/files/frontend/dist/app/index.html",
		style: {
			display: "block",
			width: "100%",
			height: "100%",
			minHeight: 0,
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
