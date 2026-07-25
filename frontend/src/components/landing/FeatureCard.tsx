import type { LucideIcon } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"

type FeatureCardProps = {
  icon: LucideIcon
  title: string
  description: string
}

export default function FeatureCard({ icon: Icon, title, description }: FeatureCardProps) {
  return (
    <Card className="group h-full transition-all duration-300 ease-out hover:-translate-y-0.5">
      <CardContent className="p-6">
        <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-md border border-border bg-muted dark:bg-white/[0.04] dark:border-white/[0.08] dark:backdrop-blur-sm">
          <Icon className="h-5 w-5 text-foreground dark:text-emerald-400" />
        </div>
        <h3 className="mb-2 text-base font-medium text-foreground">{title}</h3>
        <p className="text-sm leading-relaxed text-muted-foreground md:text-base">{description}</p>
      </CardContent>
    </Card>
  )
}
