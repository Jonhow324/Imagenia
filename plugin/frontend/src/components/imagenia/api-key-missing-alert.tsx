import * as React from "react"
import { KeyRoundIcon } from "lucide-react"

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

export function ApiKeyMissingAlert({ onConfigure }: { onConfigure: () => void }) {
  return (
    <Alert className="border-amber-500/30 bg-amber-500/5 text-amber-950">
      <KeyRoundIcon aria-hidden="true" />
      <AlertTitle>还没有配置图像服务</AlertTitle>
      <AlertDescription>
        添加 OpenAI API Key 后才能创建任务。密钥只由后端保存，页面不会回显完整内容。
      </AlertDescription>
      <AlertAction>
        <Button size="sm" variant="outline" onClick={onConfigure}>
          去配置
        </Button>
      </AlertAction>
    </Alert>
  )
}
