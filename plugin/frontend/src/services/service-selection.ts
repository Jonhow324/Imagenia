import type { CatalogStatus, ServiceSelection } from "./settings.ts"

const storageKey = "imagenia.image-service-selection"

/** Invalid remembered choices remain visible errors instead of silently changing providers. */
export function initialServiceSelection(catalog: CatalogStatus): ServiceSelection | null {
  try {
    const value = localStorage.getItem(storageKey)
    if (value) {
      const parsed: unknown = JSON.parse(value)
      if (typeof parsed === "object" && parsed !== null &&
          "service_id" in parsed && typeof parsed.service_id === "string" &&
          "model_id" in parsed && typeof parsed.model_id === "string") {
        return { service_id: parsed.service_id, model_id: parsed.model_id }
      }
    }
  } catch { /* Restricted storage must not prevent choosing a service. */ }
  return catalog.default
}

export function rememberServiceSelection(selection: ServiceSelection): void {
  try { localStorage.setItem(storageKey, JSON.stringify(selection)) } catch { /* Storage is optional. */ }
}

export function selectedServiceModel(catalog: CatalogStatus | null, selection: ServiceSelection | null, editing: boolean) {
  const service = catalog?.services.find(item => item.id === selection?.service_id)
  const model = service?.models.find(item => item.id === selection?.model_id)
  const valid = Boolean(service?.configured && service.enabled && model && (!editing || model.supports_edit))
  return { service, model, valid }
}
