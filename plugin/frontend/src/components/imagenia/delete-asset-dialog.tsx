import * as React from "react"
import { Trash2Icon } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

export function DeleteAssetDialog({
  assetLabel,
  onConfirm,
  triggerVariant = "outline",
}: {
  assetLabel: string
  onConfirm: () => void
  triggerVariant?: "outline" | "ghost"
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button type="button" variant={triggerVariant} size={triggerVariant === "ghost" ? "icon-sm" : "default"} aria-label="删除图片">
          <Trash2Icon aria-hidden="true" />
          {triggerVariant === "outline" ? "删除" : null}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogMedia className="bg-destructive/10 text-destructive">
            <Trash2Icon aria-hidden="true" />
          </AlertDialogMedia>
          <AlertDialogTitle>永久删除这张图片？</AlertDialogTitle>
          <AlertDialogDescription>
            “{assetLabel}”的本地文件和元数据都会被删除。由它编辑出的图片会保留，但不再显示来源。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>保留图片</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={onConfirm}>确认删除</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
