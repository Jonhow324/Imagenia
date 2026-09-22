import type * as ReactNamespace from "react"
import type * as ReactDOMNamespace from "react-dom"

declare global {
  interface Window {
    QwenPaw: {
      host: {
        React: typeof ReactNamespace
        ReactDOM: typeof ReactDOMNamespace
      }
      route: {
        add: (pluginId: string, route: { id: string; path: string; component: ReactNamespace.ComponentType }) => unknown
      }
      menu: {
        add: (pluginId: string, item: { id: string; label: string; icon?: string; route: string; location: string }) => unknown
      }
    }
  }
}

export {}
