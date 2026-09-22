import * as React from "react"
import "./styles.css"

import { ImageniaWorkbench } from "@/components/imagenia/workbench"

const pluginId = "imagenia"

window.QwenPaw.route.add(pluginId, {
  id: "imagenia.home",
  path: "/imagenia",
  component: ImageniaWorkbench,
})

window.QwenPaw.menu.add(pluginId, {
  id: "imagenia.home",
  label: "Imagenia",
  route: "imagenia.home",
  location: "primary.agentScoped",
})
