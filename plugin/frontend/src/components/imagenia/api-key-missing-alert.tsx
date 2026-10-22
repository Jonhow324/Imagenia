import * as React from "react"
import { KeyRoundIcon } from "lucide-react"

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

export function ApiKeyMissingAlert({ onConfigure }: { onConfigure: () => void }) {
  return (
    <Alert className="border-amber-500/30 bg-amber-500/5 text-amber-950">
      <KeyRoundIcon aria-hidden="true" />
      <AlertTitle>没有可用的图像服务</AlertTitle>
      <AlertDescription>
        请添加并启用一套图像服务，或检查现有配置。密钥只由后端保存，页面不会回显完整内容。
      </AlertDescription>
      <AlertAction>
        <Button size="sm" variant="outline" onClick={onConfigure}>
          去配置
        </Button>
      </AlertAction>
    </Alert>
  )
}
