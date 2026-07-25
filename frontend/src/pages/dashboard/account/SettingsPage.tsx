import { useEffect, useState } from "react"

import PageHeader from "@/components/shared/PageHeader"
import SectionCard from "@/components/shared/SectionCard"
import ThemeToggle from "@/components/shared/ThemeToggle"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"

import { useTheme } from "@/context/ThemeContext"
import { useAuth } from "@/context/AuthContext"
import { updateWorkspace } from "@/services/backendClient"

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { workspace, isAdmin } = useAuth()

  const [workspaceName, setWorkspaceName] = useState(workspace?.name || "")
  const [savingWorkspace, setSavingWorkspace] = useState(false)
  const [workspaceSaved, setWorkspaceSaved] = useState(false)

  const [emailNotifications, setEmailNotifications] = useState(true)
  const [browserNotifications, setBrowserNotifications] = useState(false)

  useEffect(() => {
    setWorkspaceName(workspace?.name || "")
  }, [workspace?.name])

  const canSaveWorkspace =
    Boolean(workspace?.id) &&
    Boolean(workspaceName.trim()) &&
    workspaceName.trim() !== (workspace?.name || "")

  const handleSaveWorkspace = async () => {
    if (!workspace?.id || !workspaceName.trim()) return
    setSavingWorkspace(true)
    setWorkspaceSaved(false)

    try {
      await updateWorkspace(workspace.id, { name: workspaceName.trim() })
      setWorkspaceSaved(true)
      setTimeout(() => setWorkspaceSaved(false), 2500)
    } finally {
      setSavingWorkspace(false)
    }
  }

  return (
    <div className="min-w-0 p-6 space-y-6">
      <PageHeader
        title="Settings"
        description="Manage your workspace and preferences."
      />

      {isAdmin ? (
        <SectionCard
          title="Organization"
          description="Update workspace details for your organization."
          actions={
            <Button onClick={handleSaveWorkspace} disabled={!canSaveWorkspace || savingWorkspace}>
              Save
            </Button>
          }
        >
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Organization Name</p>
              <Input
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="Workspace name"
              />
            </div>

            {workspaceSaved ? (
              <Alert>
                <AlertTitle>Saved</AlertTitle>
                <AlertDescription>Workspace name updated.</AlertDescription>
              </Alert>
            ) : null}
          </div>
        </SectionCard>
      ) : null}

      <SectionCard
        title="Appearance"
        description="Switch between light and dark mode."
        actions={<ThemeToggle theme={theme} setTheme={setTheme} />}
      >
        <div className="text-sm text-muted-foreground">
          Theme changes apply immediately.
        </div>
      </SectionCard>

      <SectionCard
        title="Notifications"
        description="Choose how you want to be notified."
      >
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">Email notifications</p>
              <p className="text-sm text-muted-foreground">Receive results and updates via email.</p>
            </div>
            <Switch checked={emailNotifications} onCheckedChange={setEmailNotifications} />
          </div>

          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">Browser notifications</p>
              <p className="text-sm text-muted-foreground">Show desktop notifications when supported.</p>
            </div>
            <Switch checked={browserNotifications} onCheckedChange={setBrowserNotifications} />
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="Danger Zone"
        description="Irreversible actions for your account."
      >
        <Alert variant="destructive">
          <AlertTitle>Delete account</AlertTitle>
          <AlertDescription>
            Deleting your account is permanent. This action cannot be undone.
          </AlertDescription>
        </Alert>
        <div className="mt-4">
          <Button variant="destructive">Delete Account</Button>
        </div>
      </SectionCard>
    </div>
  )
}
