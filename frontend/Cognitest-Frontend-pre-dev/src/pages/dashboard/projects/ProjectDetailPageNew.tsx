import { useState, useEffect, useRef, useCallback, useMemo } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/components/ui/toast"
import { AnimatePresence, motion } from "framer-motion"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import { InfoIcon } from "@/components/shared/InfoIcon"
import { FileCode, Clock, CheckCircle2, XCircle, Play, Globe, Pencil, Eye, Trash2, Save, X, RefreshCw, History, Zap, CircleMinus, Shield, FileText, Shuffle, Layers, Loader2, CheckCheck, AlertCircle } from "lucide-react"
import { useProjects } from "@/context/ProjectContext"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { RunSuiteModal } from "@/components/RunSuiteModal"
import { getProjectTestCasesFromDb, getProjectSpecs, uploadProjectSpec, generateAISuite, getGenerationJob, getProjectMeta, getTestExecutions, getCategoryStats, TestExecutionCase, CategoryStatsItem, SpecInfo, updateTestCase, deleteTestCase, DraftTestCase, GenerationJobStatus } from "@/services/backendClient"
import { useAuth } from "@/context/AuthContext"
import {
  TEST_CATEGORIES,
  DEFAULT_TEST_CATEGORY,
  getCategoryConfig,
  getMethodColors,
  getFilterableMethods,
  API_CONFIG,
  formatDate,
  formatDateTime,
  getUserInitials,
} from "@/config"



const ProjectDetailPage = () => {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const toast = useToast()

  // State for inline Test Results tab
  const [loadingExecutions, setLoadingExecutions] = useState(false)
  const [filteredExecutions, setFilteredExecutions] = useState<TestExecutionCase[]>([])
  const [viewingHistory, setViewingHistory] = useState<TestExecutionCase | null>(null)
  const [viewingRunPayload, setViewingRunPayload] = useState<Record<string, unknown> | null>(null)

  const CATEGORY_CARD_STYLES: Record<
    string,
    {
      tileBg: string
      iconBg: string
      iconText: string
      active: string
    }
  > = {
    blue: {
      tileBg: "bg-muted/40",
      iconBg: "bg-muted/60",
      iconText: "text-foreground",
      active: "border-primary ring-2 ring-primary/10 bg-muted/40",
    },
    orange: {
      tileBg: "bg-muted/40",
      iconBg: "bg-muted/60",
      iconText: "text-foreground",
      active: "border-primary ring-2 ring-primary/10 bg-muted/40",
    },
    red: {
      tileBg: "bg-muted/40",
      iconBg: "bg-destructive/10",
      iconText: "text-destructive",
      active: "border-primary ring-2 ring-primary/10 bg-muted/40",
    },
    emerald: {
      tileBg: "bg-muted/40",
      iconBg: "bg-muted/60",
      iconText: "text-foreground",
      active: "border-primary ring-2 ring-primary/10 bg-muted/40",
    },
    purple: {
      tileBg: "bg-muted/40",
      iconBg: "bg-muted/60",
      iconText: "text-foreground",
      active: "border-primary ring-2 ring-primary/10 bg-muted/40",
    },
    slate: {
      tileBg: "bg-muted/40",
      iconBg: "bg-muted/60",
      iconText: "text-foreground",
      active: "border-border ring-2 ring-border/30 bg-muted/40",
    },
  }

  const getCategoryCardIcon = (name: string) => {
    const key = String(name || "").trim().toLowerCase()
    if (key.includes("functional")) return Zap
    if (key.includes("negative")) return CircleMinus
    if (key.includes("security")) return Shield
    if (key.includes("contract")) return FileText
    if (key.includes("fuzz")) return Shuffle
    return FileCode
  }

  const userInitials = getUserInitials(user?.displayName || user?.username || user?.name || user?.email)
  const [runSuiteOpen, setRunSuiteOpen] = useState(false)
  const [testCases, setTestCases] = useState<any[]>([])
  const [testExecutions, setTestExecutions] = useState<TestExecutionCase[]>([])
  const [categoryStats, setCategoryStats] = useState<CategoryStatsItem[]>([])
  const [specs, setSpecs] = useState<SpecInfo[]>([])
  const [projectMeta, setProjectMeta] = useState<any>(null)
  const [tablesLoading, setTablesLoading] = useState<boolean>(true)
  const [selectedTestTypes, setSelectedTestTypes] = useState<string[]>([DEFAULT_TEST_CATEGORY])
  const [selectedSpecId, setSelectedSpecId] = useState<string>("")
  const [selectedSpecVersion, setSelectedSpecVersion] = useState<string>("")
  const [selectedCaseIds, setSelectedCaseIds] = useState<Set<string>>(new Set())
  const [activeCategory, setActiveCategory] = useState<string | null>(null)


  // ─── Filter Panel State ────────────────────────────────────────────────────
  const [tableSearchText, setTableSearchText] = useState("")
  const [activeFilters, setActiveFilters] = useState<{ id: string; key: string; values: string[] }[]>([])

  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [useAI, setUseAI] = useState(false)
  const [useBatchAI, setUseBatchAI] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const runSuiteWasOpenRef = useRef(false)
  const testGenSectionRef = useRef<HTMLDivElement>(null)
  const initialSpecSetRef = useRef(false)
  const { projects } = useProjects()


  // Stores pass/fail results per test category from current session (before DB refresh)
  const [categoryResults, setCategoryResults] = useState<Record<string, { passed: number; failed: number }>>({})

  const [baseUrl, setBaseUrl] = useState<string>("")
  const [testCasePage, setTestCasePage] = useState<number>(1)
  const [runTestsPage, setRunTestsPage] = useState<number>(1)
  const TEST_CASES_PER_PAGE = 10
  const [activeMethodTab, setActiveMethodTab] = useState<string>("ALL")
  const [activeTab, setActiveTab] = useState<string>("testcases")

  const [editingCase, setEditingCase] = useState<DraftTestCase | null>(null)
  const [viewingCase, setViewingCase] = useState<DraftTestCase | null>(null)
  const [deletingCase, setDeletingCase] = useState<DraftTestCase | null>(null)
  const [editForm, setEditForm] = useState<Partial<DraftTestCase>>({})

  const securityMetaFor = useCallback((test: DraftTestCase | null) => {
    const meta = ((test as any)?.metadata && typeof (test as any).metadata === "object")
      ? (test as any).metadata as Record<string, unknown>
      : {}
    const owaspId = String((test as any)?.owasp_id || meta.owasp_id || (test as any)?.owasp_category || meta.owasp_category || "").trim()
    const owaspName = String((test as any)?.owasp_name || meta.owasp_name || "").trim()
    const source = String((test as any)?.generation_source || meta.generation_source || "").trim()
    const intent = String((test as any)?.security_intent || meta.security_intent || "").trim()
    const rationale = String((test as any)?.ai_coverage_rationale || meta.ai_coverage_rationale || "").trim()
    return { owaspId, owaspName, source, intent, rationale }
  }, [])

  const isAiGenerated = useCallback((test: DraftTestCase) => {
    const meta = securityMetaFor(test)
    return Boolean(test.ai_explanation || meta.source.toUpperCase() === "AI" || meta.owaspId || meta.intent || meta.rationale)
  }, [securityMetaFor])

  const visibleAssertionsFor = useCallback((test: DraftTestCase | null) => {
    return ((test as any)?.assertions || []).filter(
      (assertion: unknown) => !(typeof assertion === "string" && assertion.startsWith("__security_meta__="))
    )
  }, [])

  const handleSaveCaseEdit = async () => {
    if (!editingCase || !projectId) return
    try {
      const { id, ...rest } = editingCase
      let finalForm: Partial<DraftTestCase> = { ...editForm }
      if (finalForm.expected_status) {
        finalForm.expected_status = Number(finalForm.expected_status)
      }
      const updated = await updateTestCase(projectId, editingCase.id, finalForm)
      setTestCases(prev => prev.map(tc => tc.id === updated.id ? updated : tc))
      setEditingCase(null)
      setEditForm({})
    } catch (err) {
      console.error("Failed to update test case:", err)
    }
  }

  const handleDeleteDraftCase = async (caseId: string) => {
    if (!projectId) return
    try {
      await deleteTestCase(projectId, caseId)
      setTestCases(prev => prev.filter(tc => tc.id !== caseId))
      setSelectedCaseIds(prev => {
        const next = new Set(prev)
        next.delete(caseId)
        return next
      })
    } catch (err) {
      console.error("Failed to delete test case:", err)
    }
  }

  const dedupeCases = useCallback((cases: DraftTestCase[]) => {
    const stableStringify = (value: any): string => {
      try {
        if (value === null || value === undefined) return ""
        if (typeof value !== "object") return String(value)
        if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")} ]`
        const keys = Object.keys(value).sort()
        return `{${keys.map((k) => `${k}:${stableStringify((value as any)[k])}`).join(",")}}`
      } catch {
        return ""
      }
    }

    const seen = new Set<string>()
    const out: DraftTestCase[] = []
    for (const c of cases || []) {
      const method = String((c as any)?.method || "").toUpperCase()
      const path = String((c as any)?.endpoint_path || (c as any)?.endpointPath || "")
      const name = String((c as any)?.name || "")
      const expected = String((c as any)?.expected_status ?? (c as any)?.expectedStatus ?? "")
      const sub = String((c as any)?.sub_category || (c as any)?.subCategory || "")
      const cat = String((c as any)?.category || "")
      const headers = (c as any)?.headers ?? (c as any)?.request_headers
      const query = (c as any)?.query_params ?? (c as any)?.queryParams
      const body = (c as any)?.request_body ?? (c as any)?.requestBody
      const pathParams = (c as any)?.path_params ?? (c as any)?.pathParams
      const assertions = (c as any)?.assertions
      const requiresAuth = (c as any)?.requires_auth

      const sig = `${method}|${path}|${name}|${expected}|${cat}|${sub}|h:${stableStringify(headers)}|q:${stableStringify(query)}|p:${stableStringify(pathParams)}|b:${stableStringify(body)}|a:${stableStringify(assertions)}|ra:${String(requiresAuth)}`
      if (seen.has(sig)) continue
      seen.add(sig)
      out.push(c)
    }
    return out
  }, [])

  const refreshData = useCallback(async () => {
    if (!projectId) return
    setTablesLoading(true)
    try {
      // Fetch each independently so one failure doesn't block the others
      const [casesResult, specsResult, metaResult, execsResult, statsResult] = await Promise.allSettled([
        getProjectTestCasesFromDb(projectId, {
          specId: selectedSpecId || undefined,
          version: selectedSpecVersion || undefined,
          testTypes: selectedTestTypes.includes("All") ? undefined : selectedTestTypes,
          methods: activeFilters.find(f => f.key === "method")?.values?.length ? activeFilters.find(f => f.key === "method")?.values : undefined,
        }),
        getProjectSpecs(projectId),
        getProjectMeta(projectId),
        getTestExecutions(projectId),
        getCategoryStats(projectId)
      ])
      if (casesResult.status === "fulfilled") setTestCases(dedupeCases(casesResult.value))
      if (specsResult.status === "fulfilled") {
        const sortedSpecs = [...specsResult.value].sort((a: any, b: any) => Date.parse(b.createdAt) - Date.parse(a.createdAt))
        setSpecs(sortedSpecs)
        // Only set the initial spec selection once — prevents refreshData from changing its
        // own deps (selectedSpecId/selectedSpecVersion) and triggering an infinite re-fetch loop.
        if (!initialSpecSetRef.current && sortedSpecs.length > 0) {
          initialSpecSetRef.current = true
          const latest = sortedSpecs[0]
          setSelectedSpecId(latest.id)
          setSelectedSpecVersion(latest.version)
        }
      }

      if (metaResult.status === "fulfilled") setProjectMeta(metaResult.value)
      if (execsResult.status === "fulfilled") setTestExecutions(execsResult.value)
      if (statsResult.status === "fulfilled") {
        setCategoryStats(statsResult.value)
        // Clear local session results — DB now has the authoritative data
        setCategoryResults({})
      }
      if (execsResult.status === "rejected") console.error("Failed to load test executions:", execsResult.reason)
    } finally {
      setTablesLoading(false)
    }
  }, [projectId, selectedSpecId, selectedSpecVersion, selectedTestTypes, activeFilters, dedupeCases])
  const handleRunSuiteOpenChange = useCallback((open: boolean) => {
    if (!open && runSuiteWasOpenRef.current) {
      refreshData()
    }
    runSuiteWasOpenRef.current = open
    setRunSuiteOpen(open)
  }, [refreshData])

  const handleRunComplete = useCallback((_summary: { passed: number; failed: number }) => {
    refreshData()
  }, [refreshData])

  useEffect(() => {
    refreshData()
  }, [refreshData])

  const versionToLatestSpec = useMemo(() => {
    const map = new Map<string, SpecInfo>()
    for (const s of specs || []) {
      const v = String(s.version || "").trim()
      if (!v) continue
      const existing = map.get(v)
      if (!existing) {
        map.set(v, s)
        continue
      }
      const existingTime = Date.parse(existing.createdAt)
      const nextTime = Date.parse(s.createdAt)
      if (!Number.isNaN(nextTime) && (Number.isNaN(existingTime) || nextTime > existingTime)) {
        map.set(v, s)
      }
    }
    return map
  }, [specs])

  const versionOptions = useMemo(() => {
    const versions = Array.from(versionToLatestSpec.keys())
    const parse = (v: string) => v.split(".").map((x) => Number.parseInt(x, 10))
    const cmpSemverDesc = (a: string, b: string) => {
      const ap = parse(a)
      const bp = parse(b)
      const len = Math.max(ap.length, bp.length)
      for (let i = 0; i < len; i++) {
        const ai = Number.isFinite(ap[i]) ? ap[i] : 0
        const bi = Number.isFinite(bp[i]) ? bp[i] : 0
        if (ai !== bi) return bi - ai
      }
      return b.localeCompare(a)
    }
    return versions.sort(cmpSemverDesc)
  }, [versionToLatestSpec])

  const activeSpec = useMemo(() => {
    if (selectedSpecId) {
      const found = (specs || []).find((s) => s.id === selectedSpecId)
      if (found) return found
    }
    return specs && specs.length > 0 ? specs[0] : undefined
  }, [specs, selectedSpecId])

  // Keep selection in sync with loaded cases (default: select all currently visible)
  useEffect(() => {
    setSelectedCaseIds(prev => {
      if (prev.size > 0) return prev
      return new Set((testCases || []).map((c) => c.id).filter(Boolean))
    })
  }, [testCases])

  const handleUploadSpec = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file || !projectId) return

    setUploading(true)
    try {
      await uploadProjectSpec(projectId, file)
      // Refresh specs
      const projectSpecs = await getProjectSpecs(projectId)
      setSpecs(projectSpecs)
    } catch (err) {
      console.error("Failed to upload spec:", err)
    } finally {
      setUploading(false)
    }
  }

  const handleGenerateTests = async () => {
    if (!projectId || specs.length === 0) return
    const activeSpecId = selectedSpecId || specs[0]?.id
    if (!activeSpecId) return

    const typesToGenerate = (() => {
      if (selectedTestTypes.length === 0) return [DEFAULT_TEST_CATEGORY]
      if (selectedTestTypes.includes("All")) return TEST_CATEGORIES.map((c) => c.value)
      return selectedTestTypes
    })()

    setGenerating(true)
    try {
      for (const t of typesToGenerate) {
        const isContract = String(t || "").trim().toLowerCase() === "contract"
        const resp = await generateAISuite(projectId, activeSpecId, t, isContract ? undefined : API_CONFIG.DEFAULT_MAX_TESTS, useAI, useBatchAI)

        // If AI mode → 202 response with job_id — poll until done
        if (useAI && resp && "job_id" in resp) {
          await pollGenerationJob(projectId, (resp as any).job_id)
        }
      }
      await refreshData()
    } catch (err: any) {
      console.error("Failed to generate tests:", err)
      const errorMsg = err?.message || "Failed to generate tests"
      toast.show({
        title: "Test generation failed",
        description: errorMsg,
        type: "error",
      })
    } finally {
      setGenerating(false)
    }
  }

  /** Poll a background generation job until terminal state, updating progress. */
  const pollGenerationJob = async (projId: string, jobId: string): Promise<void> => {
    const POLL_MS = 2000
    const MAX_POLLS = 300 // 10 min max
    for (let i = 0; i < MAX_POLLS; i++) {
      await new Promise((r) => setTimeout(r, POLL_MS))
      try {
        const job: GenerationJobStatus = await getGenerationJob(projId, jobId)
        if (job.status === "completed" || job.status === "partial") return
        if (job.status === "failed") throw new Error(job.error || "AI generation failed")
      } catch (e) {
        throw e
      }
    }
    throw new Error("Generation timed out after 10 minutes")
  }

  // Dynamic data using config formatters
  const projectData = {
    name: projectMeta?.name || projects?.find((p: any) => p.id === projectId)?.name || "Loading...",
    status: projectMeta?.status || "Active",
    apiVersion: selectedSpecVersion || (specs.length > 0 ? specs[0].version : API_CONFIG.DEFAULT_API_VERSION),
    totalSpecApis: projectMeta?.endpointsCount || 0,
    createdOn: formatDate(projectMeta?.createdAt),
    lastTestRun: formatDateTime(projectMeta?.lastRunAt),
    testResults: {
      passed: projectMeta?.testsPassed || 0,
      failed: projectMeta?.testsFailed || 0
    }
  }

  const generateCategoryStats = (categoryName: string) => {
    const config = getCategoryConfig(categoryName)
    const dbMetaStats = projectMeta?.categorySummary?.[categoryName.toUpperCase()]
    const totalTests = dbMetaStats ? dbMetaStats.total : 0;

    const dbPassed = dbMetaStats?.passed || 0
    const dbFailed = dbMetaStats?.failed || 0

    // Add any current-session results not yet persisted to DB
    const localResults = categoryResults[categoryName]
    const passed = dbPassed + (localResults?.passed || 0)
    const failed = dbFailed + (localResults?.failed || 0)

    const runs = passed + failed
    const passRate = runs > 0 ? Math.round((passed / runs) * 100) : 0

    return {
      name: categoryName.toUpperCase(),
      icon: config?.icon || "📋",
      totalTests,
      passRate,
      passed,
      failed,
      color: config?.color || "slate",
      badgeClass: config?.badgeClass || "bg-muted/50 text-muted-foreground",
      description: config?.description || ""
    }
  }

  // Generate stats for all configured categories
  const testCategories = TEST_CATEGORIES.map((cat) => generateCategoryStats(cat.name))

  const filteredCases = useMemo(() => {
    // 1. Types & Categories global block
    const typesAll = selectedTestTypes.length === 0 || selectedTestTypes.includes("All")
    const typeSet = new Set(selectedTestTypes.map((t) => t.toLowerCase()))

    return (testCases || []).filter((tc) => {
      // (A) Global Types Filter
      const tt = String(tc.test_type || tc.testType || "").toLowerCase()
      const cat = String(tc.category || "").toLowerCase()
      const typeOk = typesAll ? true : typeSet.has(tt) || typeSet.has(cat)
      if (!typeOk) return false

      // (B) HTTP Method Tab
      if (activeMethodTab && activeMethodTab !== "ALL") {
        const m = String(tc.method || "").toUpperCase()
        if (m !== activeMethodTab) return false
      }

      // (C) Table Search Text
      if (tableSearchText.trim()) {
        const query = tableSearchText.toLowerCase()
        const matchesName = (tc.name || "").toLowerCase().includes(query)
        const matchesPath = (tc.endpoint_path || "").toLowerCase().includes(query)
        if (!matchesName && !matchesPath) return false
      }

      return true
    })
  }, [testCases, selectedTestTypes, tableSearchText, activeMethodTab])

  const totalPages = Math.ceil(filteredCases.length / TEST_CASES_PER_PAGE)
  const safePage = Math.min(testCasePage, Math.max(1, totalPages))
  const pagedCases = filteredCases.slice((safePage - 1) * TEST_CASES_PER_PAGE, safePage * TEST_CASES_PER_PAGE)

  const runTotalPages = Math.ceil(filteredCases.length / TEST_CASES_PER_PAGE)
  const runSafePage = Math.min(runTestsPage, Math.max(1, runTotalPages))
  const runPagedCases = filteredCases.slice((runSafePage - 1) * TEST_CASES_PER_PAGE, runSafePage * TEST_CASES_PER_PAGE)

  const selectedCount = selectedCaseIds.size
  const viewingLabel = selectedTestTypes.includes("All")
    ? "All"
    : selectedTestTypes.length === 1
      ? selectedTestTypes[0]
      : `${selectedTestTypes.length} types`

  const allMethods = useMemo(() => getFilterableMethods(), [])
  const methodOptions: { label: string; value: string }[] = useMemo(
    () => allMethods.map((m) => ({ label: m, value: m })),
    [allMethods],
  )
  const testTypeOptions: { label: string; value: string }[] = useMemo(
    () => [{ label: "All", value: "All" }, ...TEST_CATEGORIES.map((c) => ({ label: c.name, value: c.value }))],
    [],
  )

  const handleToggleAllVisible = () => {
    const visibleIds = filteredCases.map((c) => c.id).filter(Boolean)
    const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedCaseIds.has(id))

    setSelectedCaseIds((prev) => {
      const next = new Set(prev)
      if (allVisibleSelected) {
        visibleIds.forEach((id) => next.delete(id))
      } else {
        visibleIds.forEach((id) => next.add(id))
      }
      return next
    })
  }

  const toggleCaseId = (id: string) => {
    setSelectedCaseIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const projectStatusBadge = (() => {
    const raw = String(projectData.status || "").trim()
    const normalized = raw.toLowerCase()
    if (!raw) return { label: "Unknown", variant: "outline" as const }
    if (["active", "enabled", "ready"].includes(normalized)) return { label: raw, variant: "default" as const }
    if (["running", "in_progress", "in progress", "queued", "pending"].includes(normalized)) return { label: raw, variant: "secondary" as const }
    if (["disabled", "inactive"].includes(normalized)) return { label: raw, variant: "outline" as const }
    return { label: raw, variant: "outline" as const }
  })()

  if (tablesLoading) {
    return (
      <div className="flex flex-col min-h-0 p-6 space-y-6 bg-background">
        {/* Header Skeleton */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="mt-2 flex flex-wrap items-end gap-x-3 gap-y-1">
              <Skeleton className="h-9 w-72 max-w-[70vw] rounded-md" />
              <Skeleton className="h-4 w-40 rounded-md" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
          </div>
        </div>

        {/* Stats Cards Row Skeleton */}
        <div className="grid grid-cols-1 min-[540px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="relative overflow-hidden rounded-xl border border-border shadow-sm bg-muted/30">
              <CardContent className="p-4 min-h-26">
                <div className="flex items-start justify-between gap-3">
                  <Skeleton className="h-3 w-20 rounded-md" />
                  <Skeleton className="h-8 w-8 rounded-lg" />
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <Skeleton className="h-7 w-16 rounded-md" />
                  <Skeleton className="h-3 w-12 rounded-md" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Category Breakdown Section Skeleton */}
        <div className="mt-2">
          <div className="mb-4 flex items-center gap-2">
            <Skeleton className="h-6 w-64 rounded-md" />
          </div>
          <div className="grid grid-cols-1 min-[540px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Card key={i} className="relative overflow-hidden rounded-xl border border-border shadow-sm bg-muted/30">
                <CardContent className="p-4 min-h-28">
                  <div className="flex items-start justify-between gap-3">
                    <Skeleton className="h-3 w-20 rounded-md" />
                    <Skeleton className="h-8 w-8 rounded-lg" />
                  </div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <Skeleton className="h-7 w-12 rounded-md" />
                    <Skeleton className="h-3 w-10 rounded-md" />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-3 w-14 rounded-md" />
                      <Skeleton className="h-3 w-14 rounded-md" />
                    </div>
                    <Skeleton className="h-3 w-8 rounded-md" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col min-h-0 p-6 space-y-6 bg-background">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {tablesLoading ? (
            <div className="mt-2 flex flex-wrap items-end gap-x-3 gap-y-1">
              <Skeleton className="h-9 w-72 max-w-[70vw]" />
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-5 w-16" />
            </div>
          ) : (
            <div className="mt-2 flex flex-wrap items-end gap-x-3 gap-y-1 animate-in fade-in duration-300">
              <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-foreground leading-none wrap-break-word">{projectData.name}</h1>
              {projectData.createdOn && projectData.createdOn !== "-" && (
                <span className="text-sm text-muted-foreground leading-none">
                  Created on {projectData.createdOn}
                </span>
              )}
              <Badge variant={projectStatusBadge.variant} className="px-2.5 py-0.5 text-xs font-semibold capitalize">
                {projectStatusBadge.label}
              </Badge>
            </div>
          )}
        </div>


      </div>

      {/* Stats Cards Row */}
      <div className="grid grid-cols-1 min-[540px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {/* Card 1: API Version */}
        <Card className="relative overflow-hidden rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow bg-muted/30">
          <CardContent className="p-4 min-h-26">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] sm:text-[11px] font-medium text-muted-foreground">API Version</p>
              </div>
              <div className="h-8 w-8 rounded-lg flex items-center justify-center bg-muted/60 shrink-0 border border-border/60">
                <FileCode className="h-4 w-4 text-foreground" />
              </div>
            </div>

            <div className="mt-3 flex items-baseline gap-2">
              <div className="min-w-0">
                <Select
                  value={projectData.apiVersion}
                  onValueChange={(v) => {
                    const spec = versionToLatestSpec.get(v)
                    if (spec?.id) setSelectedSpecId(spec.id)
                    setSelectedSpecVersion(v)
                  }}
                >
                  <SelectTrigger className="h-7 sm:h-8 px-0 border-0 shadow-none focus:ring-0 bg-transparent text-xl sm:text-2xl font-semibold text-foreground tracking-tight">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {versionOptions.length > 0 ? (
                      versionOptions.map((v) => (
                        <SelectItem key={v} value={v}>
                          {v}
                        </SelectItem>
                      ))
                    ) : (
                      <SelectItem value={API_CONFIG.DEFAULT_API_VERSION}>{API_CONFIG.DEFAULT_API_VERSION}</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>
              <span className="text-xs font-normal text-muted-foreground">spec</span>
            </div>

            <div className="pointer-events-none absolute -right-6 -bottom-6 opacity-[0.06]">
              <FileCode className="h-24 w-24" />
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Total Spec APIs */}
        <Card className="relative overflow-hidden rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow bg-muted/30">
          <CardContent className="p-4 min-h-26">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] sm:text-[11px] font-medium text-muted-foreground">Total Spec APIs</p>
              </div>
              <div className="h-8 w-8 rounded-lg flex items-center justify-center bg-muted/60 shrink-0 border border-border/60">
                <Globe className="h-4 w-4 text-foreground" />
              </div>
            </div>

            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-xl sm:text-2xl font-semibold text-foreground tracking-tight tabular-nums">
                {projectData.totalSpecApis}
              </span>
              <span className="text-xs font-normal text-muted-foreground">endpoints</span>
            </div>

            <div className="pointer-events-none absolute -right-6 -bottom-6 opacity-[0.06]">
              <Globe className="h-24 w-24" />
            </div>
          </CardContent>
        </Card>

        {/* Card 3: Last Test Run */}
        <Card className="relative overflow-hidden rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow bg-muted/30">
          <CardContent className="p-4 min-h-26">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] sm:text-[11px] font-medium text-muted-foreground">Last Test Run</p>
              </div>
              <div className="h-8 w-8 rounded-lg flex items-center justify-center bg-muted/60 shrink-0 border border-border/60">
                <Clock className="h-4 w-4 text-foreground" />
              </div>
            </div>

            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-xl sm:text-2xl font-semibold text-foreground tracking-tight tabular-nums">
                {projectData.lastTestRun === "-" ? "-" : projectData.lastTestRun.split(",")[0]}
              </span>
              <span className="text-xs font-normal text-muted-foreground">
                {projectData.lastTestRun === "-" ? "Never" : projectData.lastTestRun.split(",")[1]?.trim()}
              </span>
            </div>

            <div className="pointer-events-none absolute -right-6 -bottom-6 opacity-[0.06]">
              <Clock className="h-24 w-24" />
            </div>
          </CardContent>
        </Card>

        {/* Card 4: Tests Passed */}
        <Card className="relative overflow-hidden rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow bg-muted/30">
          <CardContent className="p-4 min-h-26">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] sm:text-[11px] font-medium text-muted-foreground">Tests Passed</p>
              </div>
              <div className="h-8 w-8 rounded-lg flex items-center justify-center bg-primary/10 shrink-0 border border-border/60">
                <CheckCircle2 className="h-4 w-4 text-primary" />
              </div>
            </div>

            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-xl sm:text-2xl font-semibold text-foreground tracking-tight tabular-nums">
                {projectData.testResults.passed}
              </span>
              <span className="text-xs font-normal text-muted-foreground">tests</span>
            </div>

            <div className="pointer-events-none absolute -right-6 -bottom-6 opacity-[0.06]">
              <CheckCircle2 className="h-24 w-24" />
            </div>
          </CardContent>
        </Card>

        {/* Card 5: Tests Failed */}
        <Card className="relative overflow-hidden rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow bg-muted/30">
          <CardContent className="p-4 min-h-26">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] sm:text-[11px] font-medium text-muted-foreground">Tests Failed</p>
              </div>
              <div className="h-8 w-8 rounded-lg flex items-center justify-center bg-destructive/10 shrink-0 border border-border/60">
                <XCircle className="h-4 w-4 text-destructive" />
              </div>
            </div>

            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-xl sm:text-2xl font-semibold text-foreground tracking-tight tabular-nums">
                {projectData.testResults.failed}
              </span>
              <span className="text-xs font-normal text-muted-foreground">tests</span>
            </div>

            <div className="pointer-events-none absolute -right-6 -bottom-6 opacity-[0.06]">
              <XCircle className="h-24 w-24" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Project Test Category Breakdown */}
      <div className="mt-2">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-foreground">
          Project Test Category Breakdown
        </h2>
        {testCategories.length > 0 ? (
          <div className="grid grid-cols-1 min-[540px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {testCategories.map((category) => {
              const style =
                CATEGORY_CARD_STYLES[String(category.color || "slate").toLowerCase()] ?? CATEGORY_CARD_STYLES.slate
              const isActive = activeCategory === category.name
              const CategoryIcon = getCategoryCardIcon(category.name)

              return (
                <motion.div
                  key={category.name}
                  whileTap={{ scale: 0.99 }}
                  transition={{ type: "spring", stiffness: 420, damping: 30 }}
                  className="h-full"
                >
                  <Card
                    className={`relative overflow-hidden rounded-xl border shadow-sm hover:shadow-md transition-all cursor-pointer ${isActive
                      ? style.active
                      : `border-border ${style.tileBg}`
                      }`}
                    onClick={() => {
                      const next = activeCategory === category.name ? null : category.name
                      setActiveCategory(next)
                      if (next) {
                        setSelectedTestTypes([next])
                        // Scroll to Test Generation section after content renders
                        setTimeout(() => {
                          const el = testGenSectionRef.current
                          if (el) {
                            // Find the scrollable parent (main element)
                            const scrollContainer = el.closest('main')
                            if (scrollContainer) {
                              const rect = el.getBoundingClientRect()
                              const containerRect = scrollContainer.getBoundingClientRect()
                              scrollContainer.scrollTo({
                                top: scrollContainer.scrollTop + rect.top - containerRect.top - 24,
                                behavior: 'smooth'
                              })
                            } else {
                              el.scrollIntoView({ behavior: "smooth", block: "start" })
                            }
                          }
                        }, 300)
                      } else {
                        setSelectedTestTypes([DEFAULT_TEST_CATEGORY])
                      }
                      setTestCasePage(1)
                    }}
                  >
                    <CardContent className="p-4 min-h-28">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex items-center gap-1.5">
                          <p className="text-[10px] sm:text-[11px] font-medium text-muted-foreground">{category.name}</p>
                          {category.description && (
                            <InfoIcon
                              description={category.description}
                              side="right"
                              align="start"
                            />
                          )}
                        </div>
                        <div className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 border border-border/60 ${style.iconBg}`}>
                          <CategoryIcon className={`h-4 w-4 ${style.iconText}`} />
                        </div>
                      </div>

                      <div className="mt-3 flex items-baseline gap-2">
                        <span className="text-xl sm:text-2xl font-semibold text-foreground tracking-tight tabular-nums">
                          {category.totalTests}
                        </span>
                        <span className="text-xs font-normal text-muted-foreground">tests</span>
                      </div>

                      <div className="mt-1.5 flex items-center justify-between gap-3 text-[11px]">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">Passed</span>
                          <span className="font-semibold text-primary tabular-nums">{category.passed}</span>
                          <span className="text-muted-foreground">· Failed</span>
                          <span className="font-semibold text-destructive tabular-nums">{category.failed}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-muted-foreground">{category.passRate}%</span>
                        </div>
                      </div>

                      <div className="pointer-events-none absolute -right-6 -bottom-6 opacity-[0.06] text-foreground">
                        <CategoryIcon className="h-24 w-24" />
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )
            })}
          </div>
        ) : (
          <Card className="border border-border bg-card rounded-xl shadow-sm">
            <CardContent className="p-10 flex flex-col items-center justify-center text-center">
              <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <FileCode className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-sm font-medium text-foreground">No test data yet</p>
              <p className="text-xs text-muted-foreground mt-1">Generate and run tests to view the category breakdown</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Test Generation & Management Section */}
      <div ref={testGenSectionRef}>
        <AnimatePresence initial={false} mode="wait">
          {activeCategory && (
            <motion.div
              key={activeCategory}
              initial={{ opacity: 0, y: 6, scale: 0.995 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 6, scale: 0.995 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="border border-border/50 bg-card rounded-xl shadow-sm">


                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
                      <span className="capitalize">{activeCategory.toLowerCase()}</span> Test Generation & Management
                    </h2>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-full"
                      onClick={() => setActiveCategory(null)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  <Tabs
                    value={activeTab}
                    className="w-full"
                    onValueChange={(tab) => {
                      setActiveTab(tab)
                      // Fetch executions when switching to test results tab
                      if (tab === "testresults" && projectId && activeCategory) {
                        setLoadingExecutions(true)
                        const version = selectedSpecVersion || (specs.length > 0 ? specs[0].version : "")
                        const specId = selectedSpecId || (specs.length > 0 ? specs[0].id : "")
                        getTestExecutions(projectId, activeCategory, version, specId)
                          .then((execs) => setFilteredExecutions(execs))
                          .catch((err) => console.error("Failed to load executions:", err))
                          .finally(() => setLoadingExecutions(false))
                      }
                    }}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6">
                      <TabsList className="grid w-full sm:w-96 grid-cols-3 bg-muted/60 p-1 rounded-lg border border-border/50">
                        <TabsTrigger value="testcases" className="rounded-md data-[state=active]:bg-background data-[state=active]:shadow-sm text-xs">Testcases</TabsTrigger>
                        <TabsTrigger value="runtests" className="rounded-md data-[state=active]:bg-background data-[state=active]:shadow-sm text-xs">Run Tests</TabsTrigger>
                        <TabsTrigger value="testresults" className="rounded-md data-[state=active]:bg-background data-[state=active]:shadow-sm text-xs">Test Results</TabsTrigger>
                      </TabsList>

                      {activeTab === "testcases" && (
                        <div className="flex flex-col items-end gap-2">
                          <div className="flex items-center gap-2">
                            {/* Mode toggle: Rule-based / AI */}
                            <div className="flex items-center gap-1 px-2 py-1.5 rounded-lg border border-border/50 bg-muted/30">
                              <button
                                onClick={() => setUseAI(false)}
                                className={`text-xs px-2 py-0.5 rounded transition-colors ${!useAI ? "bg-background shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                              >
                                Rule-based
                              </button>
                              <button
                                onClick={() => setUseAI(true)}
                                className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded transition-colors ${useAI ? "bg-background shadow-sm font-medium text-purple-600" : "text-muted-foreground hover:text-foreground"}`}
                              >
                                ✨ AI
                              </button>
                            </div>

                            {useAI && (
                              <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg border border-border/50 bg-muted/20 text-[11px] text-muted-foreground select-none">
                                <input
                                  type="checkbox"
                                  id="useBatchAI"
                                  checked={useBatchAI}
                                  onChange={(e) => setUseBatchAI(e.target.checked)}
                                  className="h-3.5 w-3.5 rounded border-gray-300 text-purple-600 focus:ring-purple-500 cursor-pointer"
                                />
                                <label htmlFor="useBatchAI" className="cursor-pointer font-medium hover:text-foreground">
                                  Use Anthropic Batch API
                                </label>
                              </div>
                            )}

                            <Button
                              size="sm"
                              className={`h-9 px-4 text-xs font-medium gap-1.5 ${useAI ? "bg-purple-600 hover:bg-purple-700 text-white" : ""}`}
                              onClick={handleGenerateTests}
                              disabled={generating || specs.length === 0}
                            >
                              {generating
                                ? (useAI ? "✨ Generating with AI..." : "Generating...")
                                : (useAI ? "✨ Generate with AI" : "Generate Tests")}
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>

                    <TabsContent value="testcases" className="space-y-4">
                      <div className="flex flex-col min-h-0 border border-border/50 rounded-lg overflow-hidden bg-card">

                        {/* Table Header Section */}
                        <div className="p-4 border-b border-border/50 flex items-center justify-between bg-card">
                          <div>
                            <h3 className="text-sm font-semibold text-foreground">Generated Tests Listing</h3>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              Viewing {filteredCases.length} {viewingLabel} tests
                            </p>
                          </div>
                        </div>

                        {/* HTTP Method Tabs */}
                        <div className="border-b border-border/50 bg-muted/30 px-4 flex items-center gap-1">
                          {["ALL", "GET", "POST", "PUT", "PATCH", "DELETE"].map((method) => (
                            <Button
                              key={method}
                              type="button"
                              onClick={() => { setActiveMethodTab(method); setTestCasePage(1) }}
                              variant="ghost"
                              size="sm"
                              className={`h-9 rounded-none px-3 text-xs font-semibold border-b-2 transition-colors ${activeMethodTab === method
                                ? "border-primary text-primary"
                                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border/60"
                                }`}
                            >
                              {method}
                            </Button>
                          ))}
                        </div>

                        {/* Table wrapper with scroll support */}
                        <div className="overflow-x-auto max-h-125 overflow-y-scroll relative">
                          <Table className="w-full text-sm">
                            <TableHeader className="sticky top-0 z-10 bg-muted/40 border-b border-border/50 shadow-sm">
                              <TableRow>
                                <TableHead>Test Name</TableHead>
                                <TableHead className="w-40">OWASP</TableHead>
                                <TableHead>Endpoint Path</TableHead>
                                <TableHead className="w-24">Method</TableHead>
                                <TableHead className="w-24 text-right">Actions</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody className="animate-in fade-in duration-300">
                              {pagedCases.map((test, idx) => (
                                <TableRow key={test.id || idx} className="hover:bg-muted/30 transition-colors">
                                  <TableCell className="font-medium text-foreground max-w-62.5" title={test.name}>
                                    <div className="flex items-center gap-1.5 truncate">
                                      <span className="truncate">{test.name}</span>
                                      {isAiGenerated(test) && (
                                        <span className="shrink-0 text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-600 border border-purple-200">AI</span>
                                      )}
                                    </div>
                                  </TableCell>
                                  <TableCell className="max-w-40">
                                    {securityMetaFor(test).owaspId ? (
                                      <Badge
                                        variant="outline"
                                        className="max-w-full justify-start truncate border-red-500/30 bg-red-500/10 text-red-600 text-[10px]"
                                        title={[securityMetaFor(test).owaspId, securityMetaFor(test).owaspName].filter(Boolean).join(" - ")}
                                      >
                                        <Shield className="h-3 w-3 mr-1 shrink-0" />
                                        <span className="truncate">{securityMetaFor(test).owaspId}</span>
                                      </Badge>
                                    ) : (
                                      <span className="text-xs text-muted-foreground">-</span>
                                    )}
                                  </TableCell>
                                  <TableCell className="font-mono text-xs text-muted-foreground max-w-50 truncate" title={test.endpoint_path}>{test.endpoint_path}</TableCell>
                                  <TableCell>
                                    <Badge variant="outline" className={`${getMethodColors(test.method)} font-medium text-[10px] w-14 justify-center`}>
                                      {test.method}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <div className="flex items-center justify-end gap-1">
                                      <Button
                                        variant="ghost" size="sm"
                                        className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                        onClick={(e) => { e.stopPropagation(); setViewingCase(test) }}
                                        title="View"
                                        type="button"
                                      >
                                        <Eye className="h-4 w-4" />
                                      </Button>
                                      <Button
                                        variant="ghost" size="sm"
                                        className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                        onClick={(e) => { e.stopPropagation(); setEditingCase(test); setEditForm(test) }}
                                        title="Edit"
                                        type="button"
                                      >
                                        <Pencil className="h-4 w-4" />
                                      </Button>
                                      <Button
                                        variant="ghost" size="sm"
                                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                        onClick={(e) => { e.stopPropagation(); setDeletingCase(test) }}
                                        title="Delete"
                                        type="button"
                                      >
                                        <Trash2 className="h-4 w-4" />
                                      </Button>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                              {filteredCases.length === 0 && (
                                <TableRow>
                                  <TableCell colSpan={5} className="py-12 text-center text-muted-foreground">
                                    <div className="flex flex-col items-center justify-center">
                                      <span className="text-sm">No test cases found.</span>
                                      <span className="text-xs mt-1 text-muted-foreground/70">Upload a spec and generate tests to get started.</span>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              )}
                            </TableBody>
                          </Table>
                        </div>

                        {/* Pagination UI */}
                        {totalPages > 1 && (
                          <div className="border-t border-border/50 bg-muted/30 p-2 px-4 flex items-center justify-between">
                            <div className="text-[11px] text-muted-foreground font-medium">
                              Page {safePage} of {totalPages} · {filteredCases.length} total
                            </div>
                            <div className="flex items-center gap-1">
                              <Button
                                variant="outline"
                                size="icon"
                                className="h-6 w-6 p-0"
                                onClick={() => setTestCasePage(1)}
                                disabled={safePage === 1}
                              >
                                <span className="text-[10px]">«</span>
                              </Button>
                              <Button
                                variant="outline"
                                size="icon"
                                className="h-6 w-6 p-0"
                                onClick={() => setTestCasePage(p => Math.max(1, p - 1))}
                                disabled={safePage === 1}
                              >
                                <span className="text-[10px]">‹</span>
                              </Button>

                              <div className="flex items-center gap-1 bg-background/60 border border-border/50 rounded-md overflow-hidden">
                                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                                  let start = Math.max(1, safePage - 2)
                                  const end = Math.min(totalPages, start + 4)
                                  if (end - start < 4) start = Math.max(1, end - 4)
                                  return start + i
                                }).filter(p => p >= 1 && p <= totalPages).map(p => (
                                  <Button
                                    key={p}
                                    variant={p === safePage ? "default" : "ghost"}
                                    size="sm"
                                    className={`h-6 min-w-6 rounded-none px-2 text-[11px] font-medium border-x border-border/50 first:border-l-0 last:border-r-0 ${p === safePage ? "bg-primary hover:bg-primary/90 text-primary-foreground" : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"}`}
                                    onClick={() => setTestCasePage(p)}
                                  >
                                    {p}
                                  </Button>
                                ))}
                              </div>

                              <Button
                                variant="outline"
                                size="icon"
                                className="h-6 w-6 p-0"
                                onClick={() => setTestCasePage(p => Math.min(totalPages, p + 1))}
                                disabled={safePage === totalPages}
                              >
                                <span className="text-[10px]">›</span>
                              </Button>
                              <Button
                                variant="outline"
                                size="icon"
                                className="h-6 w-6 p-0"
                                onClick={() => setTestCasePage(totalPages)}
                                disabled={safePage === totalPages}
                              >
                                <span className="text-[10px]">»</span>
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    </TabsContent>

                    <TabsContent value="runtests">
                      <div className="flex flex-col min-h-0 border border-border/50 rounded-lg overflow-hidden bg-card">
                        {/* Header with Run Suite button */}
                        <div className="p-4 border-b border-border/50 flex items-center justify-between bg-card">
                          <div>
                            <h3 className="text-sm font-semibold text-foreground">Test Cases</h3>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {filteredCases.length} tests · Selected {selectedCaseIds.size}
                            </p>
                          </div>
                          <Button
                            size="sm"
                            className="h-9 px-4 text-xs font-medium gap-1.5"
                            onClick={() => handleRunSuiteOpenChange(true)}
                            disabled={selectedCaseIds.size === 0}
                          >
                            <Play className="h-3.5 w-3.5" />
                            Run Suite
                          </Button>
                        </div>

                        {/* Table with checkboxes */}
                        <div className="overflow-x-auto max-h-125 overflow-y-scroll relative">
                          <Table className="w-full text-sm">
                            <TableHeader className="sticky top-0 z-10 bg-muted/40 border-b border-border/50 shadow-sm">
                              <TableRow>
                                <TableHead className="w-10">
                                  <Checkbox
                                    checked={filteredCases.length > 0 && filteredCases.every((c) => selectedCaseIds.has(c.id))}
                                    onCheckedChange={() => handleToggleAllVisible()}
                                    aria-label="Select all"
                                  />
                                </TableHead>
                                <TableHead>Test Name</TableHead>
                                <TableHead className="w-40">OWASP</TableHead>
                                <TableHead>Endpoint Path</TableHead>
                                <TableHead className="w-24">Method</TableHead>
                                <TableHead className="w-24 text-right">Actions</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody className="animate-in fade-in duration-300">
                              {runPagedCases.map((test, idx) => (
                                <TableRow key={test.id || idx} className="hover:bg-muted/30 transition-colors">
                                  <TableCell>
                                    <Checkbox
                                      checked={selectedCaseIds.has(test.id)}
                                      onCheckedChange={() => toggleCaseId(test.id)}
                                      aria-label="Select test case"
                                    />
                                  </TableCell>
                                  <TableCell className="font-medium text-foreground max-w-62.5" title={test.name}>
                                    <div className="flex items-center gap-1.5 truncate">
                                      <span className="truncate">{test.name}</span>
                                      {isAiGenerated(test) && (
                                        <span className="shrink-0 text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-600 border border-purple-200">AI</span>
                                      )}
                                    </div>
                                  </TableCell>
                                  <TableCell className="max-w-40">
                                    {securityMetaFor(test).owaspId ? (
                                      <Badge
                                        variant="outline"
                                        className="max-w-full justify-start truncate border-red-500/30 bg-red-500/10 text-red-600 text-[10px]"
                                        title={[securityMetaFor(test).owaspId, securityMetaFor(test).owaspName].filter(Boolean).join(" - ")}
                                      >
                                        <Shield className="h-3 w-3 mr-1 shrink-0" />
                                        <span className="truncate">{securityMetaFor(test).owaspId}</span>
                                      </Badge>
                                    ) : (
                                      <span className="text-xs text-muted-foreground">-</span>
                                    )}
                                  </TableCell>
                                  <TableCell className="font-mono text-xs text-muted-foreground max-w-50 truncate" title={test.endpoint_path}>{test.endpoint_path}</TableCell>
                                  <TableCell>
                                    <Badge variant="outline" className={`${getMethodColors(test.method)} font-medium text-[10px] w-14 justify-center`}>
                                      {test.method}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <div className="flex items-center justify-end gap-1">
                                      <Button
                                        variant="ghost" size="sm"
                                        className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                        onClick={(e) => { e.stopPropagation(); setViewingCase(test) }}
                                        title="View"
                                        type="button"
                                      >
                                        <Eye className="h-4 w-4" />
                                      </Button>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                              {filteredCases.length === 0 && (
                                <TableRow>
                                  <TableCell colSpan={6} className="py-12 text-center text-muted-foreground">
                                    <div className="flex flex-col items-center justify-center">
                                      <Play className="h-10 w-10 text-muted-foreground/30 mb-3" />
                                      <span className="text-sm">No test cases available.</span>
                                      <span className="text-xs mt-1 text-muted-foreground/70">Generate tests first in the Testcases tab.</span>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              )}
                            </TableBody>
                          </Table>
                        </div>

                        {/* Pagination */}
                        {runTotalPages > 1 && (
                          <div className="border-t border-border/50 bg-muted/30 p-2 px-4 flex items-center justify-between">
                            <div className="text-[11px] text-muted-foreground font-medium">
                              Page {runSafePage} of {runTotalPages} · {filteredCases.length} total
                            </div>
                            <div className="flex items-center gap-1">
                              <Button variant="outline" size="icon" className="h-6 w-6 p-0" onClick={() => setRunTestsPage(1)} disabled={runSafePage === 1}><span className="text-[10px]">«</span></Button>
                              <Button variant="outline" size="icon" className="h-6 w-6 p-0" onClick={() => setRunTestsPage(p => Math.max(1, p - 1))} disabled={runSafePage === 1}><span className="text-[10px]">‹</span></Button>
                              <div className="flex items-center gap-1 bg-background/60 border border-border/50 rounded-md overflow-hidden">
                                {Array.from({ length: Math.min(5, runTotalPages) }, (_, i) => {
                                  let start = Math.max(1, runSafePage - 2)
                                  const end = Math.min(runTotalPages, start + 4)
                                  if (end - start < 4) start = Math.max(1, end - 4)
                                  return start + i
                                }).filter(p => p >= 1 && p <= runTotalPages).map(p => (
                                  <Button key={p} variant={p === runSafePage ? "default" : "ghost"} size="sm" className={`h-6 min-w-6 rounded-none px-2 text-[11px] font-medium border-x border-border/50 first:border-l-0 last:border-r-0 ${p === runSafePage ? "bg-primary hover:bg-primary/90 text-primary-foreground" : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"}`} onClick={() => setRunTestsPage(p)}>{p}</Button>
                                ))}
                              </div>
                              <Button variant="outline" size="icon" className="h-6 w-6 p-0" onClick={() => setRunTestsPage(p => Math.min(runTotalPages, p + 1))} disabled={runSafePage === runTotalPages}><span className="text-[10px]">›</span></Button>
                              <Button variant="outline" size="icon" className="h-6 w-6 p-0" onClick={() => setRunTestsPage(runTotalPages)} disabled={runSafePage === runTotalPages}><span className="text-[10px]">»</span></Button>
                            </div>
                          </div>
                        )}
                      </div>
                    </TabsContent>

                    {/* ── Test Results Tab (inline) ──────────────────── */}
                    <TabsContent value="testresults">
                      <div className="flex flex-col min-h-0 border border-border/50 rounded-lg overflow-hidden bg-card">
                        <div className="p-4 border-b border-border/50 flex items-center justify-between bg-card">
                          <div>
                            <h3 className="text-sm font-semibold text-foreground">Test Execution Results</h3>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {loadingExecutions ? "Loading…" : `${filteredExecutions.length} test case(s) with execution history`}
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            className="gap-1.5 text-xs"
                            disabled={loadingExecutions}
                            onClick={() => {
                              if (!projectId || !activeCategory) return
                              setLoadingExecutions(true)
                              const version = selectedSpecVersion || (specs.length > 0 ? specs[0].version : "")
                              const specId = selectedSpecId || (specs.length > 0 ? specs[0].id : "")
                              getTestExecutions(projectId, activeCategory, version, specId)
                                .then((execs) => setFilteredExecutions(execs))
                                .catch((err) => console.error("Failed to load executions:", err))
                                .finally(() => setLoadingExecutions(false))
                            }}
                          >
                            <RefreshCw className={`h-3.5 w-3.5 ${loadingExecutions ? "animate-spin" : ""}`} /> Refresh
                          </Button>
                        </div>

                        <div className="overflow-x-auto max-h-125 overflow-y-scroll relative">
                          <Table className="w-full text-sm">
                            <TableHeader className="sticky top-0 z-10 bg-muted/40 border-b border-border/50 shadow-sm">
                              <TableRow>
                                <TableHead>Test Name</TableHead>
                                <TableHead>Endpoint</TableHead>
                                <TableHead className="w-20">Method</TableHead>
                                <TableHead className="w-16 text-center">Runs</TableHead>
                                <TableHead className="w-20 text-center">Passed</TableHead>
                                <TableHead className="w-20 text-center">Failed</TableHead>
                                <TableHead className="w-24 text-center">Last Status</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody className="animate-in fade-in duration-300">
                              {loadingExecutions ? (
                                // Skeleton rows matching the table structure
                                Array.from({ length: 5 }).map((_, idx) => (
                                  <TableRow key={idx} className="h-12">
                                    <TableCell><Skeleton className="h-4 w-32 rounded-md" /></TableCell>
                                    <TableCell><Skeleton className="h-4 w-40 rounded-md" /></TableCell>
                                    <TableCell><Skeleton className="h-5 w-14 rounded-md" /></TableCell>
                                    <TableCell><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
                                    <TableCell><Skeleton className="h-4 w-20 rounded-md" /></TableCell>
                                    <TableCell><Skeleton className="h-4 w-6 rounded-md" /></TableCell>
                                    <TableCell className="text-right"><Skeleton className="h-7 w-7 rounded-md ml-auto" /></TableCell>
                                  </TableRow>
                                ))
                              ) : filteredExecutions.length === 0 ? (
                                <TableRow>
                                  <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                                    <div className="flex flex-col items-center justify-center">
                                      <History className="h-10 w-10 text-muted-foreground/30 mb-3" />
                                      <span className="text-sm">No test executions found.</span>
                                      <span className="text-xs mt-1 text-muted-foreground/70">Run tests first in the Run Tests tab.</span>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ) : (
                                filteredExecutions.map((exec, idx) => (
                                  <TableRow
                                    key={exec.id || idx}
                                    className="hover:bg-muted/30 transition-colors cursor-pointer"
                                    onClick={() => setViewingHistory(exec)}
                                  >
                                    <TableCell className="font-medium text-foreground max-w-62.5 truncate" title={exec.name}>{exec.name}</TableCell>
                                    <TableCell className="font-mono text-xs text-muted-foreground max-w-50 truncate" title={exec.endpoint}>{exec.endpoint}</TableCell>
                                    <TableCell>
                                      <Badge variant="outline" className={`${getMethodColors(exec.method)} font-medium text-[10px] w-14 justify-center`}>
                                        {exec.method}
                                      </Badge>
                                    </TableCell>
                                    <TableCell className="text-center tabular-nums">{exec.totalRuns}</TableCell>
                                    <TableCell className="text-center tabular-nums text-emerald-600 font-medium">{exec.passed}</TableCell>
                                    <TableCell className="text-center tabular-nums text-red-500 font-medium">{exec.failed}</TableCell>
                                    <TableCell className="text-center">
                                      {exec.lastStatus === "PASS" ? (
                                        <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[10px]">
                                          <CheckCircle2 className="h-3 w-3 mr-1" /> Pass
                                        </Badge>
                                      ) : exec.lastStatus === "FAIL" ? (
                                        <Badge className="bg-red-500/15 text-red-500 border-red-500/30 text-[10px]">
                                          <XCircle className="h-3 w-3 mr-1" /> Fail
                                        </Badge>
                                      ) : (
                                        <Badge variant="outline" className="text-[10px]">{exec.lastStatus || "—"}</Badge>
                                      )}
                                    </TableCell>
                                  </TableRow>
                                ))
                              )}
                            </TableBody>
                          </Table>
                        </div>
                      </div>
                    </TabsContent>

                  </Tabs>

                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>


      <RunSuiteModal
        open={runSuiteOpen}
        onOpenChange={handleRunSuiteOpenChange}
        projectId={projectId ?? ""}
        testCount={selectedCaseIds.size}
        baseUrl={projectMeta?.baseUrl || API_CONFIG.DEFAULT_BASE_URL}
        testType={activeCategory ?? (selectedTestTypes.length === 1 && !selectedTestTypes.includes("All") ? selectedTestTypes[0] : "Security")}
        caseIds={Array.from(selectedCaseIds)}
        onComplete={handleRunComplete}
      />
      {/* ── Edit Draft Test Case Dialog ── */}
      <Dialog open={Boolean(editingCase)} onOpenChange={(v) => { if (!v) { setEditingCase(null); setEditForm({}) } }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Pencil className="h-4 w-4 text-muted-foreground" />
              Edit Test Case
            </DialogTitle>
            <DialogDescription>Adjust the generated values before running the suite.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <label htmlFor="ec-name" className="text-sm font-medium leading-none">Name</label>
              <Input id="ec-name" value={editForm.name ?? ""} onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label htmlFor="ec-method" className="text-sm font-medium leading-none">Method</label>
                <Input id="ec-method" value={editForm.method ?? ""} onChange={(e) => setEditForm((p) => ({ ...p, method: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label htmlFor="ec-status" className="text-sm font-medium leading-none">Expected Status</label>
                <Input
                  id="ec-status"
                  type="number"
                  value={editForm.expected_status ?? ""}
                  onChange={(e) => setEditForm((p) => ({ ...p, expected_status: Number(e.target.value) }))}
                />
              </div>
            </div>
            <div className="space-y-1">
              <label htmlFor="ec-path" className="text-sm font-medium leading-none">Endpoint Path</label>
              <Input id="ec-path" value={editForm.endpoint_path ?? ""} onChange={(e) => setEditForm((p) => ({ ...p, endpoint_path: e.target.value }))} />
            </div>
            <div className="space-y-1">
              <label htmlFor="ec-desc" className="text-sm font-medium leading-none">Description</label>
              <Input id="ec-desc" value={editForm.description ?? ""} onChange={(e) => setEditForm((p) => ({ ...p, description: e.target.value }))} />
            </div>
            {editingCase && (editingCase.method?.toUpperCase() === 'POST' || editingCase.method?.toUpperCase() === 'PUT' || editingCase.method?.toUpperCase() === 'PATCH') && (
              <div className="space-y-1">
                <label htmlFor="ec-body" className="text-sm font-medium leading-none">Request Body (JSON)</label>
                <textarea
                  id="ec-body"
                  className="w-full h-32 p-3 text-xs font-mono bg-muted/50 rounded-md border border-border/50 focus:outline-none focus:ring-2 focus:ring-primary/20"
                  value={typeof editForm.request_body === 'object' && editForm.request_body !== null ? JSON.stringify(editForm.request_body, null, 2) : (editForm.request_body as string | undefined) ?? ""}
                  onChange={(e) => setEditForm((p) => ({ ...p, request_body: e.target.value as any }))}
                  placeholder="{}"
                />
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => { setEditingCase(null); setEditForm({}) }}>Cancel</Button>
            <Button className="gap-2" onClick={handleSaveCaseEdit}>
              <Save className="h-4 w-4" /> Save Changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Delete Confirmation Dialog ── */}
      <Dialog open={Boolean(deletingCase)} onOpenChange={(v) => { if (!v) setDeletingCase(null) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="h-4 w-4 text-destructive" />
              Delete Test Case
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this test case? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {deletingCase && (
            <div className="rounded-lg border border-border/50 bg-muted/30 px-4 py-3 text-sm overflow-hidden w-full">
              <p className="font-medium truncate">{deletingCase.name}</p>
              <div className="flex items-center gap-2 mt-1.5 min-w-0">
                <Badge variant="outline" className="font-mono text-[10px] px-1.5 py-0 shrink-0">{deletingCase.method}</Badge>
                <span className="text-xs text-muted-foreground font-mono truncate min-w-0">{deletingCase.endpoint_path}</span>
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setDeletingCase(null)}>Cancel</Button>
            <Button
              variant="destructive"
              className="gap-2"
              onClick={() => {
                if (deletingCase) {
                  void handleDeleteDraftCase(deletingCase.id)
                  setDeletingCase(null)
                }
              }}
            >
              <Trash2 className="h-4 w-4" /> Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── View Test Case Details Dialog ── */}
      <Dialog open={Boolean(viewingCase)} onOpenChange={(v) => { if (!v) setViewingCase(null) }}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-primary" />
              Test Case Details
            </DialogTitle>
            <DialogDescription>Full payload and assertions for this generated test case.</DialogDescription>
          </DialogHeader>

          {viewingCase && (
            <div className="flex-1 overflow-y-auto space-y-4 py-4 pr-2">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">Method & Path</span>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-xs">{viewingCase.method}</Badge>
                    <span className="text-sm font-mono truncate">{viewingCase.endpoint_path}</span>
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">Expected Status</span>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">{viewingCase.expected_status}</Badge>
                    <span className="text-xs text-muted-foreground">{viewingCase.expected_status >= 200 && viewingCase.expected_status < 300 ? "Success" : "Error"} Expected</span>
                  </div>
                </div>
              </div>

              {(securityMetaFor(viewingCase).owaspId || securityMetaFor(viewingCase).intent || securityMetaFor(viewingCase).rationale || securityMetaFor(viewingCase).source) && (
                <div className="space-y-3 rounded-lg border border-red-500/20 bg-red-500/5 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-red-600">
                      <Shield className="h-3.5 w-3.5" />
                      Security Metadata
                    </div>
                    {securityMetaFor(viewingCase).owaspId && (
                      <Badge variant="outline" className="border-red-500/30 bg-red-500/10 text-red-600 text-[10px]">
                        {securityMetaFor(viewingCase).owaspId}
                      </Badge>
                    )}
                    {securityMetaFor(viewingCase).owaspName && (
                      <span className="text-xs text-muted-foreground">{securityMetaFor(viewingCase).owaspName}</span>
                    )}
                    {securityMetaFor(viewingCase).source && (
                      <Badge variant="outline" className="border-purple-500/30 bg-purple-500/10 text-purple-600 text-[10px]">
                        {securityMetaFor(viewingCase).source}
                      </Badge>
                    )}
                  </div>
                  {securityMetaFor(viewingCase).intent && (
                    <div className="space-y-1">
                      <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">Security Intent</span>
                      <p className="text-xs text-foreground leading-relaxed">{securityMetaFor(viewingCase).intent}</p>
                    </div>
                  )}
                  {securityMetaFor(viewingCase).rationale && (
                    <div className="space-y-1">
                      <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">AI Coverage Rationale</span>
                      <p className="text-xs text-muted-foreground leading-relaxed">{securityMetaFor(viewingCase).rationale}</p>
                    </div>
                  )}
                </div>
              )}

              {viewingCase.ai_explanation && (
                <div className="space-y-1.5 p-3 rounded-lg bg-primary/5 border border-primary/10">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-primary">
                    <span className="h-3 w-3 inline-block rounded-full bg-primary" /> AI Explanation
                  </div>
                  <p className="text-xs italic text-muted-foreground leading-relaxed">{viewingCase.ai_explanation}</p>
                </div>
              )}

              {/* JSON Sections */}
              {[
                { label: "Request Body", data: viewingCase.request_body, prominent: true },
                { label: "Query Parameters", data: viewingCase.query_params },
                { label: "Path Parameters", data: viewingCase.path_params },
                { label: "Headers", data: viewingCase.headers },
                { label: "Expected Response", data: viewingCase.expected_response },
              ].map((section) => (
                section.data && (typeof section.data === 'string' || Object.keys(section.data).length > 0) && (
                  <div key={section.label} className="space-y-2">
                    <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">{section.label}</span>
                    <div className={`rounded-lg p-3 overflow-x-auto border ${section.prominent ? 'bg-foreground border-border/50 ring-1 ring-border/30' : 'bg-muted/50 border-border/50'}`}>
                      <pre className={`text-[11px] font-mono ${section.prominent ? 'text-background' : 'text-foreground'}`}>
                        {typeof section.data === 'string' ? section.data : JSON.stringify(section.data, null, 2)}
                      </pre>
                    </div>
                  </div>
                )
              ))}

              {visibleAssertionsFor(viewingCase).length > 0 && (
                <div className="space-y-2">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">Assertions</span>
                  <div className="flex flex-wrap gap-2">
                    {visibleAssertionsFor(viewingCase).map((assertion: unknown, i: number) => (
                      <Badge key={i} variant="secondary" className="text-[10px] py-0.5 font-normal bg-muted/40 border-border/50">
                        {String(assertion)}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-border/50">
            <Button variant="outline" onClick={() => setViewingCase(null)}>Close</Button>
            <Button
              variant="default"
              className="gap-2"
              onClick={() => {
                if (!viewingCase) return
                const caseId = viewingCase.id
                setViewingCase(null)
                setSelectedCaseIds(new Set([caseId]))
                handleRunSuiteOpenChange(true)
              }}
            >
              <Play className="h-3.5 w-3.5" /> Run This Test
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Test Case Execution History Dialog ── */}
      <Dialog open={Boolean(viewingHistory)} onOpenChange={(v) => { if (!v) setViewingHistory(null) }}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History className="h-5 w-5 text-muted-foreground" />
              Execution History
            </DialogTitle>
            {viewingHistory && (
              <DialogDescription className="flex items-center gap-2 flex-wrap">
                <Badge variant="outline" className={`${getMethodColors(viewingHistory.method)} font-medium text-[10px]`}>
                  {viewingHistory.method}
                </Badge>
                <span className="font-mono text-xs">{viewingHistory.endpoint}</span>
                <span className="text-xs text-muted-foreground">· {viewingHistory.name}</span>
              </DialogDescription>
            )}
          </DialogHeader>

          <div className="flex-1 min-h-0 overflow-y-auto rounded-lg border border-border/50">
            {viewingHistory && viewingHistory.history && viewingHistory.history.length > 0 ? (
              <Table className="w-full text-sm">
                <TableHeader className="sticky top-0 z-10 bg-muted/40 border-b border-border/50">
                  <TableRow>
                    <TableHead className="w-36">Run Date</TableHead>
                    <TableHead className="w-20 text-center">Status</TableHead>
                    <TableHead className="w-20 text-center">Code</TableHead>
                    <TableHead className="w-24 text-center">Response Time</TableHead>
                    <TableHead className="w-16 text-center">View</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {viewingHistory.history.map((run, idx) => (
                    <TableRow
                      key={run.id || idx}
                      className="hover:bg-muted/30 transition-colors"
                    >
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {run.runDate ? formatDateTime(run.runDate) : "—"}
                      </TableCell>
                      <TableCell className="text-center">
                        {run.status === "PASS" ? (
                          <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[10px]">
                            <CheckCircle2 className="h-3 w-3 mr-1" /> Pass
                          </Badge>
                        ) : (
                          <Badge className="bg-red-500/15 text-red-500 border-red-500/30 text-[10px]">
                            <XCircle className="h-3 w-3 mr-1" /> Fail
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-center font-mono text-xs tabular-nums">
                        {run.statusCode ?? "—"}
                      </TableCell>
                      <TableCell className="text-center text-xs tabular-nums">
                        {run.responseTime || "—"}
                      </TableCell>
                      <TableCell className="text-center">
                        {run.payload && Object.keys(run.payload).length > 0 ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-muted/50"
                            onClick={(e) => { e.stopPropagation(); setViewingRunPayload(run.payload!) }}
                            title="View Payload"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <History className="h-10 w-10 text-muted-foreground/30 mb-3" />
                <span className="text-sm">No execution history for this test case.</span>
              </div>
            )}
          </div>

          {viewingHistory && (
            <div className="shrink-0 flex items-center justify-between pt-2 border-t border-border/50">
              <div className="text-xs text-muted-foreground">
                {viewingHistory.totalRuns} total run{viewingHistory.totalRuns !== 1 ? "s" : ""} ·{" "}
                <span className="text-emerald-600 font-medium">{viewingHistory.passed} passed</span> ·{" "}
                <span className="text-red-500 font-medium">{viewingHistory.failed} failed</span>
              </div>
              <Button variant="outline" size="sm" onClick={() => setViewingHistory(null)}>Close</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Request Payload Popup ── */}
      <Dialog open={Boolean(viewingRunPayload)} onOpenChange={(v) => { if (!v) setViewingRunPayload(null) }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-muted-foreground" />
              Request Payload
            </DialogTitle>
          </DialogHeader>
          <div className="rounded-lg border border-border/50 bg-muted/30 overflow-hidden">
            <pre className="p-4 text-sm font-mono text-foreground whitespace-pre-wrap leading-relaxed overflow-x-auto max-h-[50vh]">
              {viewingRunPayload ? JSON.stringify(viewingRunPayload, null, 2) : ""}
            </pre>
          </div>
          <div className="flex justify-end pt-1">
            <Button size="sm" onClick={() => setViewingRunPayload(null)}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>

    </div>
  )
}

export default ProjectDetailPage
