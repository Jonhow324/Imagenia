import * as React from "react"

export type WorkbenchTheme = "light" | "dark"

const ThemeContext = React.createContext<WorkbenchTheme>("light")
const STORAGE_KEY = "imagenia-theme"

export function readStoredTheme(): WorkbenchTheme {
  if (typeof window === "undefined") return "light"
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === "light" || stored === "dark") return stored
  } catch {
    // Private mode can reject storage; follow the system theme instead.
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function persistTheme(theme: WorkbenchTheme) {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // The choice still applies for this visit.
  }
}

export function WorkbenchThemeProvider({ theme, children }: { theme: WorkbenchTheme; children: React.ReactNode }) {
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>
}

export function useWorkbenchTheme() {
  return React.useContext(ThemeContext)
}
