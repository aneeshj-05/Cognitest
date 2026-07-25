import { useState, type ChangeEvent, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import {
  Mail, Phone, Send, CheckCircle2, Loader2, Building2, Clock,
} from "lucide-react"

import type { LucideIcon } from "lucide-react"

interface ContactInfoItem {
  icon: LucideIcon
  label: string
  value: string
  href?: string
  multiline?: boolean
  accent?: boolean
}

const CONTACT_INFO: ContactInfoItem[] = [
  {
    icon: Building2,
    label: "Office Address",
    value: "Cognitest Technologies Pvt. Ltd.\n4th Floor, Tower B, Tech Park\nWhitefield, Bangalore 560066\nKarnataka, India",
    multiline: true,
  },
  {
    icon: Mail,
    label: "Email",
    value: "support@cognitest.io",
    href: "mailto:support@cognitest.io",
  },
  {
    icon: Phone,
    label: "WhatsApp",
    value: "+91 98765 43210",
    href: "https://wa.me/919876543210",
    accent: true,
  },
  {
    icon: Mail,
    label: "Gmail",
    value: "cognitest.team@gmail.com",
    href: "mailto:cognitest.team@gmail.com",
  },
  {
    icon: Clock,
    label: "Business Hours",
    value: "Mon – Fri, 9:00 AM – 6:00 PM IST",
  },
]

const ContactPage = () => {
  const [name, setName] = useState<string>("")
  const [email, setEmail] = useState<string>("")
  const [subject, setSubject] = useState<string>("")
  const [message, setMessage] = useState<string>("")
  const [sending, setSending] = useState<boolean>(false)
  const [sent, setSent] = useState<boolean>(false)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!name.trim() || !email.trim() || !message.trim()) return
    setSending(true)
    setTimeout(() => {
      setSending(false)
      setSent(true)
      setName("")
      setEmail("")
      setSubject("")
      setMessage("")
      setTimeout(() => setSent(false), 5000)
    }, 1000)
  }

  const handleInputChange = (setter: (value: string) => void) => (event: ChangeEvent<HTMLInputElement>) => {
    setter(event.target.value)
  }

  const handleMessageChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(event.target.value)
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-10 lg:grid-cols-5">
          {/* Contact Info Cards */}
          <div className="lg:col-span-2">
            <Card className="border-border/40 bg-card/80 h-full">
              <CardContent className="p-6 sm:p-8">
                <h2 className="text-xl font-semibold mb-1">Contact Information</h2>
                <p className="text-sm text-muted-foreground mb-6">
                  Find us at our office or reach out via email or phone.
                </p>
                <div className="space-y-6">
                  {CONTACT_INFO.map((item) => (
                    <div key={item.label} className="flex items-start gap-4">
                      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                        item.accent ? "bg-green-500/10" : "bg-secondary"
                      }`}>
                        <item.icon className={`h-5 w-5 ${item.accent ? "text-green-400" : "text-muted-foreground"}`} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1">
                          {item.label}
                        </p>
                        {item.href ? (
                          <a href={item.href} target="_blank" rel="noopener noreferrer" className="text-sm text-foreground hover:text-emerald-400 transition-colors break-all">
                            {item.value}
                          </a>
                        ) : item.multiline ? (
                          <p className="text-sm text-foreground whitespace-pre-line leading-relaxed">{item.value}</p>
                        ) : (
                          <p className="text-sm text-foreground">{item.value}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Form */}
          <div className="lg:col-span-3">
            <Card className="border-border/40 bg-card/80">
              <CardContent className="p-6 sm:p-8">
                <h2 className="text-xl font-semibold mb-1">Send us a message</h2>
                <p className="text-sm text-muted-foreground mb-6">
                  Fill out the form below and we&apos;ll respond within 24 hours.
                </p>

                {sent && (
                  <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-400 mb-6">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    Message sent successfully! We&apos;ll get back to you soon.
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-5">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="c-name">Your Name *</Label>
                      <Input
                        id="c-name"
                        value={name}
                        onChange={handleInputChange(setName)}
                        placeholder="John Doe"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="c-email">Email Address *</Label>
                      <Input
                        id="c-email"
                        type="email"
                        value={email}
                        onChange={handleInputChange(setEmail)}
                        placeholder="you@company.com"
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="c-subject">Subject</Label>
                    <Input
                      id="c-subject"
                      value={subject}
                      onChange={handleInputChange(setSubject)}
                      placeholder="e.g. Feature Request, Bug Report, General Enquiry"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="c-message">Message *</Label>
                    <Textarea
                      id="c-message"
                      value={message}
                      onChange={handleMessageChange}
                      placeholder="Describe your query, suggestion, or request..."
                      className="min-h-[140px] resize-none"
                      required
                    />
                  </div>

                  <Button
                    type="submit"
                    disabled={sending}
                    className="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    {sending ? (
                      <><Loader2 className="h-4 w-4 animate-spin" /> Sending...</>
                    ) : (
                      <><Send className="h-4 w-4" /> Send Message</>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ContactPage
