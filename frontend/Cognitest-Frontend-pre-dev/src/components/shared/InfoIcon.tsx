import { useState } from "react"
import { Info } from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

interface InfoIconProps {
  title?: string
  description: string
  side?: "top" | "right" | "bottom" | "left"
  align?: "start" | "center" | "end"
}

export function InfoIcon({
  title,
  description,
  side = "right",
  align = "start",
}: InfoIconProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button
          className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-700 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300 flex-shrink-0"
          aria-label="More information"
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            setIsOpen(!isOpen)
          }}
        >
          <Info className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        side={side}
        align={align}
        className="w-80 p-4 bg-white border border-slate-200 rounded-lg shadow-md z-50 space-y-3"
      >
        {title && (
          <h4 className="font-semibold text-sm text-slate-900">
            {title}
          </h4>
        )}
        <p className="text-sm text-slate-700 leading-relaxed">
          {description}
        </p>
      </PopoverContent>
    </Popover>
  )
}
