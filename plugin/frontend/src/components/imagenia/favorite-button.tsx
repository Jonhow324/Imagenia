import * as React from "react"
import { HeartIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export function FavoriteButton({
  active,
  onToggle,
  className,
}: {
  active: boolean
  onToggle: () => void
  className?: string
}) {
  const label = active ? "取消收藏" : "收藏图片"
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          size="icon-sm"
          variant="outline"
          aria-label={label}
          aria-pressed={active}
          onClick={(event) => {
            event.stopPropagation()
            onToggle()
          }}
          className={cn("bg-background/90 backdrop-blur", active && "text-rose-600", className)}
        >
          <HeartIcon className={cn(active && "fill-current")} aria-hidden="true" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}
