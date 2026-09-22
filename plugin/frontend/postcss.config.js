import autoprefixer from "autoprefixer"
import tailwindcss from "tailwindcss"

function splitSelectorList(selector) {
  const parts = []
  let start = 0
  let depth = 0
  for (let index = 0; index < selector.length; index += 1) {
    const character = selector[index]
    if (character === "(" || character === "[") depth += 1
    if (character === ")" || character === "]") depth -= 1
    if (character === "," && depth === 0) {
      parts.push(selector.slice(start, index))
      start = index + 1
    }
  }
  parts.push(selector.slice(start))
  return parts
}

const scopeImageniaCss = {
  postcssPlugin: "scope-imagenia-css",
  Rule(rule) {
    let parent = rule.parent
    while (parent) {
      if (parent.type === "atrule" && /keyframes$/i.test(parent.name)) return
      parent = parent.parent
    }

    rule.selector = splitSelectorList(rule.selector)
      .map((selector) => {
        const normalized = selector.trim()
        if (!normalized || normalized.includes(".imagenia-root")) return normalized
        if (normalized === ":root" || normalized === "html" || normalized === "body") return ".imagenia-root"
        return `.imagenia-root ${normalized}`
      })
      .join(", ")
  },
}

export default {
  plugins: [tailwindcss(), autoprefixer(), scopeImageniaCss],
}
