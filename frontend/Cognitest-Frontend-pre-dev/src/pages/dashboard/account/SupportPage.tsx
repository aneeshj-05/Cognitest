import { z } from "zod"
import { useForm } from "react-hook-form"
import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { Link } from "react-router-dom"
import { BookOpen, Mail, MessageSquare, Send } from "lucide-react"

import PageHeader from "@/components/shared/PageHeader"
import SectionCard from "@/components/shared/SectionCard"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { submitSupportTicket, getWorkspaceId } from "@/services/backendClient"

const ticketSchema = z.object({
  subject: z.string().min(2, "Subject is required"),
  category: z.enum(["bug", "billing", "feature", "account"], {
    required_error: "Select a category",
  }),
  description: z.string().min(10, "Please provide more details"),
})

type TicketFormValues = z.infer<typeof ticketSchema>

export default function SupportPage() {
  const [showSuccess, setShowSuccess] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const form = useForm<TicketFormValues>({
    resolver: zodResolver(ticketSchema),
    defaultValues: {
      subject: "",
      category: "bug",
      description: "",
    },
    mode: "onSubmit",
  })

  const onSubmit = async (values: TicketFormValues) => {
    setShowSuccess(false)
    setErrorMsg(null)
    try {
      const workspaceId = getWorkspaceId()
      await submitSupportTicket({
        subject: values.subject,
        category: values.category,
        description: values.description,
        workspaceId,
      })
      setShowSuccess(true)
      form.reset({ subject: "", category: "bug", description: "" })
    } catch (err: any) {
      setErrorMsg(err?.message || "An unexpected error occurred. Please try again.")
    }
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Support"
        description="Get help and submit a support request."
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Link to="/dashboard/docs">
          <Card>
            <CardContent className="p-4 space-y-2">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Documentation</p>
              </div>
              <p className="text-sm text-muted-foreground">
                Guides and references for using Cognitest.
              </p>
            </CardContent>
          </Card>
        </Link>

        <Card>
          <CardContent className="p-4 space-y-2">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm font-medium">Chat</p>
            </div>
            <p className="text-sm text-muted-foreground">
              Prefer chat? Submit a ticket and we’ll follow up.
            </p>
          </CardContent>
        </Card>

        <a
          href="https://mail.google.com/mail/?view=cm&fs=1&to=support@cognitest.io&su=Cognitest%20Support%20Request&body=Describe%20your%20issue%20here..."
          target="_blank"
          rel="noopener noreferrer"
        >
          <Card>
            <CardContent className="p-4 space-y-2">
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Email</p>
              </div>
              <p className="text-sm text-muted-foreground">support@cognitest.io</p>
            </CardContent>
          </Card>
        </a>
      </div>

      <SectionCard
        title="Submit a Ticket"
        description="Describe your issue and we’ll get back to you."
      >
        {showSuccess ? (
          <Alert className="mb-4">
            <Send className="h-4 w-4" />
            <AlertTitle>Ticket submitted</AlertTitle>
            <AlertDescription>We’ll respond as soon as possible.</AlertDescription>
          </Alert>
        ) : null}

        {errorMsg ? (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>Error submitting ticket</AlertTitle>
            <AlertDescription>{errorMsg}</AlertDescription>
          </Alert>
        ) : null}


        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="subject"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Subject</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. Timeout on large spec" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Category</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="bug">Bug</SelectItem>
                        <SelectItem value="billing">Billing</SelectItem>
                        <SelectItem value="feature">Feature</SelectItem>
                        <SelectItem value="account">Account</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea rows={6} placeholder="What happened? What did you expect?" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex items-center justify-end">
              <Button type="submit" disabled={form.formState.isSubmitting}>
                Submit
              </Button>
            </div>
          </form>
        </Form>
      </SectionCard>
    </div>
  )
}
