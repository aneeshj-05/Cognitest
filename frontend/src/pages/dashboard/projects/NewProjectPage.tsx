import { useState, useRef, useCallback, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Rocket,
  Loader2,
  Upload,
  FileCode2,
  X,
  CheckCircle2,
  FolderOpen,
  ArrowRight,
  AlertCircle,
} from "lucide-react"
import { useProjects } from "@/context/ProjectContext"
import { uploadProjectSpec, checkProjectLimit } from "@/services/backendClient"

const ACCEPTED_TYPES = [".yaml", ".yml", ".json"]

const NewProjectPage = () => {
  const navigate = useNavigate()
  const { createNewProject, selectedWorkspaceId } = useProjects()
  const targetWorkspaceId = selectedWorkspaceId || ""

  const [projectName, setProjectName] = useState("")
  const [projectDesc, setProjectDesc] = useState("")
  const [specFile, setSpecFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [limitInfo, setLimitInfo] = useState<{
    canCreate: boolean
    currentCount: number
    maxProjects: number
    planName: string
    message: string
  } | null>(null)
  const [isCheckingLimit, setIsCheckingLimit] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Check project limit on mount
  useEffect(() => {
    const checkLimit = async () => {
      try {
        const info = await checkProjectLimit()
        setLimitInfo(info)
        
        // If user cannot create more projects, show error immediately
        if (!info.canCreate) {
          setError(info.message)
        }
      } catch (err: any) {
        console.error("Failed to check project limit:", err)
        setError("Failed to check project limits. Please try again.")
      } finally {
        setIsCheckingLimit(false)
      }
    }
    checkLimit()
  }, [])

  // ─── File helpers ─────────────────────────────────────────────────────────
  const acceptFile = (file: File | undefined) => {
    if (!file) return
    const ext = "." + file.name.split(".").pop()?.toLowerCase()
    if (!ACCEPTED_TYPES.includes(ext)) {
      setError("Only .yaml, .yml or .json spec files are accepted.")
      return
    }
    setError("")
    setSpecFile(file)
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    acceptFile(e.dataTransfer.files?.[0])
  }, [])

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => setIsDragging(false)

  // ─── Submit ───────────────────────────────────────────────────────────────
  const handleCreate = async () => {
    if (!projectName.trim()) {
      setError("Please enter a project name.")
      return
    }
    if (!targetWorkspaceId) {
      setError("Please select a workspace.")
      return
    }
    if (!specFile) {
      setError("Please upload your Swagger/OpenAPI spec to create the project.")
      return
    }
    
    // Check if user can create more projects
    if (limitInfo && !limitInfo.canCreate) {
      setError(limitInfo.message)
      return
    }

    setIsSubmitting(true)
    setError("")

    try {
      const proj = await createNewProject(projectName.trim(), projectDesc.trim(), targetWorkspaceId)
      await uploadProjectSpec(proj.id, specFile)
      navigate(`/dashboard/projects/${proj.id}`)
    } catch (err: any) {
      const errorMsg = err?.message || "Failed to create project. Please try again."
      setError(errorMsg)
      
      // If error mentions limit/upgrade, it's a plan limit issue
      if (errorMsg.toLowerCase().includes("limit") || errorMsg.toLowerCase().includes("upgrade")) {
        // Show error for 3 seconds then redirect to plans page
        setTimeout(() => {
          navigate("/dashboard/account/plans")
        }, 3000)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const canSubmit = projectName.trim().length > 0 && !!targetWorkspaceId && !!specFile && !isSubmitting && !isCheckingLimit && limitInfo?.canCreate !== false

  // Show loading state while checking limits
  if (isCheckingLimit) {
    return (
      <div className="w-full min-h-full flex items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Checking project limits...</p>
        </div>
      </div>
    )
  }

  // Show upgrade prompt if limit reached
  if (limitInfo && !limitInfo.canCreate) {
    return (
      <div className="w-full min-h-full flex items-center justify-center p-6">
        <Card className="w-full max-w-2xl">
          <CardContent className="p-8">
            <div className="flex flex-col items-center gap-6 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 border border-destructive/20">
                <AlertCircle className="h-8 w-8 text-destructive" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-semibold text-foreground">Project Limit Reached</h2>
                <p className="text-muted-foreground">
                  You've reached the maximum number of projects ({limitInfo.maxProjects}) allowed on the {limitInfo.planName} plan.
                </p>
                <p className="text-sm text-muted-foreground">
                  Currently using: {limitInfo.currentCount} / {limitInfo.maxProjects} projects
                </p>
              </div>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => navigate("/dashboard")}
                  className="gap-2"
                >
                  <FolderOpen className="h-4 w-4" />
                  Back to Dashboard
                </Button>
                <Button
                  onClick={() => navigate("/dashboard/account/plans")}
                  className="gap-2"
                >
                  <Rocket className="h-4 w-4" />
                  Upgrade Plan
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="w-full min-h-full flex items-start justify-center p-6">
      <div className="w-full max-w-5xl space-y-8">

        {/* ── Page header ─────────────────────────────────────────────────── */}
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-4 mb-1">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted border border-border shrink-0">
                <Rocket className="h-5 w-5 text-muted-foreground" />
              </div>
              <h1 className="text-2xl font-semibold tracking-tight truncate text-foreground">Create New Project</h1>
            </div>

            <Button
              variant="ghost"
              className="gap-1.5 rounded-xl"
              onClick={() => navigate(-1)}
              disabled={isSubmitting}
            >
              <FolderOpen className="h-4 w-4" />
              Cancel
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            Set up your project and upload your API specification to get started.
          </p>
        </div>

        {/* ── Main card ───────────────────────────────────────────────────── */}
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div className="grid grid-cols-1 lg:grid-cols-2">

              {/* Left — Project details */}
              <div className="p-6 space-y-5 lg:border-r border-border">
                <div className="flex items-center gap-2 mb-1">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-semibold">1</span>
                  <p className="text-sm font-semibold text-foreground">Project Details</p>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="projectName" className="text-sm text-muted-foreground">
                      Project Name <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="projectName"
                      value={projectName}
                      onChange={(e) => { setProjectName(e.target.value); setError("") }}
                      placeholder="e.g. Payment Gateway API"
                      className="h-11"
                      disabled={isSubmitting}
                      autoFocus
                      onKeyDown={(e) => e.key === "Enter" && canSubmit && handleCreate()}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="projectDesc" className="text-sm text-muted-foreground">
                      Description <span className="text-muted-foreground">(optional)</span>
                    </Label>
                    <Input
                      id="projectDesc"
                      value={projectDesc}
                      onChange={(e) => setProjectDesc(e.target.value)}
                      placeholder="Briefly describe what this project covers…"
                      className="h-11"
                      disabled={isSubmitting}
                    />
                  </div>
                </div>
              </div>

              {/* Right — Spec upload */}
              <div className="p-6 space-y-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-semibold">2</span>
                  <p className="text-sm font-semibold text-foreground">API Specification <span className="text-destructive">*</span></p>
                </div>

              {specFile ? (
                /* ── File attached state ── */
                <div className="flex items-center gap-4 rounded-xl border border-border bg-muted/30 px-4 py-3.5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted border border-border">
                    <CheckCircle2 className="h-5 w-5 text-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-foreground truncate">{specFile.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {(specFile.size / 1024).toFixed(1)} KB · Will be uploaded after project creation
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => { setSpecFile(null); setError("") }}
                    className="h-7 w-7 shrink-0 rounded-full text-muted-foreground hover:bg-muted transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                /* ── Drop zone ── */
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => fileInputRef.current?.click()}
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
                  className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-8 cursor-pointer transition-colors select-none
                    ${isDragging
                      ? "border-ring bg-muted/40"
                      : "border-border bg-muted/20 hover:bg-muted/30"
                    }`}
                >
                  <div className={`flex h-12 w-12 items-center justify-center rounded-xl border ${isDragging ? "border-ring bg-background" : "border-border bg-background"}`}> 
                    <Upload className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-semibold text-foreground">
                      {isDragging ? "Drop your spec file here" : "Upload Swagger / OpenAPI spec"}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Drag & drop or{" "}
                      <span className="text-primary font-medium underline underline-offset-2">browse files</span>
                      {" "}· .yaml, .yml, .json supported
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {[".yaml", ".yml", ".json"].map((ext) => (
                      <span key={ext} className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-[10px] font-semibold text-muted-foreground border border-border">
                        <FileCode2 className="h-3 w-3" />
                        {ext}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".yaml,.yml,.json"
                className="hidden"
                onChange={(e) => acceptFile(e.target.files?.[0])}
              />
              </div>

            </div>
          </CardContent>
        </Card>

        {/* ── Error banner ────────────────────────────────────────────────── */}
        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-3">
            <X className="h-4 w-4 text-destructive shrink-0" />
            <p className="text-xs text-destructive font-semibold">{error}</p>
          </div>
        )}

        {/* ── Action bar ──────────────────────────────────────────────────── */}
        <div className="flex items-center justify-end">
          <Button
            className="h-11 px-7 rounded-xl font-semibold gap-2 min-w-40"
            onClick={handleCreate}
            disabled={!canSubmit}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating & uploading…
              </>
            ) : (
              <>
                Create Project
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>
        </div>

      </div>
    </div>
  )
}

export default NewProjectPage
