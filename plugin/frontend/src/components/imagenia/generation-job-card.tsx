import * as React from "react"
import { CircleCheckIcon, CircleXIcon, Clock3Icon, LoaderCircleIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import type { GenerationJob, JobStatus } from "@/mocks/imagenia-service"

const statusMeta: Record<JobStatus, { label: string; icon: typeof Clock3Icon; className: string }> = {
  pending: { label: "排队中", icon: Clock3Icon, className: "border-amber-500/30 bg-amber-500/10 text-amber-800" },
  running: { label: "生成中", icon: LoaderCircleIcon, className: "border-blue-500/30 bg-blue-500/10 text-blue-800" },
  succeeded: { label: "已完成", icon: CircleCheckIcon, className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-800" },
  failed: { label: "失败", icon: CircleXIcon, className: "border-destructive/30 bg-destructive/10 text-destructive" },
}

export function GenerationJobCard({ job }: { job: GenerationJob }) {
  const meta = statusMeta[job.status]
  const Icon = meta.icon

  if (job.status === "failed") {
    return (
      <Alert variant="destructive">
        <CircleXIcon aria-hidden="true" />
        <AlertTitle className="line-clamp-1">{job.prompt}</AlertTitle>
        <AlertDescription>{job.errorMessage}</AlertDescription>
      </Alert>
    )
  }

  return (
    <Card size="sm" className="bg-card/80">
      <CardContent className="flex items-start gap-3">
        <div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-muted">
          {job.status === "running" ? <Spinner className="size-4" aria-label="任务进行中" /> : <Icon className="size-4" aria-hidden="true" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-sm font-medium">{job.prompt}</p>
            <Badge variant="outline" className={meta.className}>{meta.label}</Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{job.kind === "edit" ? "图片编辑" : "图像生成"} · {formatTime(job.createdAt)}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(value))
}
