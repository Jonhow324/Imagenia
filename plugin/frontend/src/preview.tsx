import * as React from "react"
import { createRoot } from "react-dom/client"
import "./styles.css"

import { ImageniaWorkbench } from "@/components/imagenia/workbench"

const root = document.querySelector<HTMLDivElement>("#root")
if (!root) throw new Error("Preview root not found")

createRoot(root).render(<ImageniaWorkbench />)
