/**
 * API Service for communicating with the backend
 */

import { API_BASE_URL } from "@/config/runtime"
console.log('API_BASE_URL from runtime:', API_BASE_URL);
console.log('VITE_API_URL env:', import.meta.env.VITE_API_URL);


type JsonRecord = Record<string, unknown>

interface RequestOptions<TBody = JsonRecord> {
  method?: string
  body?: TBody
  timeout?: number
  fallbackMsg?: string
  skipAuth?: boolean
  isFormData?: boolean
}

export interface BackendEndpointSummary {
  endpoint: string
  status?: number
  message?: string
}

export interface BackendRunSummary {
  total?: number
  passed?: number
  failed?: number
  coverage?: number
  successEndpoints?: BackendEndpointSummary[]
  failedEndpoints?: BackendEndpointSummary[]
}

export interface ProjectMetaResponse {
  hasSpec?: boolean
  spec?: { originalName?: string; baseUrl?: string }
  lastRun?: {
    executedAt?: string
    summary?: BackendRunSummary
    categorySummary?: Record<string, { total: number; passed: number; failed: number }>
  }
  // Dynamic stats from DB
  name?: string
  description?: string | null
  baseUrl?: string | null
  createdAt?: string
  updatedAt?: string
  testsRun?: number
  testsPassed?: number
  testsFailed?: number
  categorySummary?: Record<string, { total: number; passed: number; failed: number }>
  endpointsCount?: number
  testSuitesCount?: number
  testRunsCount?: number
  lastRunAt?: string | null
}

export interface GeneratedRunResponse {
  runId: string
  testCases?: unknown
  testcases?: unknown
  collection?: unknown
}

export interface SpecInfo {
  id: string
  file_type: string
  version: string
  file_url: string
  uploadedBy?: string | null
  createdAt: string
}

export interface SpecTestResult {
  endpointId?: string | null
  testCaseId: string
  method: string
  endpoint: string
  name: string
  expected: number | number[] | string
  actual: number | string
  message?: string | null
}

export interface SpecTestResultsResponse {
  passed: SpecTestResult[]
  failed: SpecTestResult[]
}

export interface RunProjectResponse {
  runId: string
  summary?: BackendRunSummary
}

export interface RunSummaryPayload {
  project: string
  baseUrl: string
  summary?: BackendRunSummary
  [key: string]: unknown
}

export interface TenantData {
  id: string
  name: string
  status: string
}

export interface SubscriptionData {
  id: string
  planId: string
  status: string
  expiryDate: string
}

export interface LoginResponse {
  token: string
  user: {
    id: string
    tenantId: string
    email: string
    name: string | null
    systemRole: string
    company?: string | null
    contactNumber?: string | null
  }
  tenant?: TenantData | null
  workspace?: WorkspaceData | null
  subscription?: SubscriptionData | null
}


export interface UserData {
  id: string
  tenantId: string
  email: string
  name: string | null
  systemRole: string
  company?: string | null
  contactNumber?: string | null
  projectMembers?: {
    projectId: string
    roleId?: string
    project?: {
      id: string
      name: string
    }
    role?: {
      id: string
      name: string
    }
  }[]

}

export interface WorkspaceData {
  id: string
  tenantId: string
  name: string
  createdBy: string | null
}

export interface ProjectData {
  id: string
  tenantId: string
  workspaceId: string
  name: string
  description?: string | null
  // UI / extended fields (optional — filled from local state or mock data)
  baseUrl?: string
  repoUrl?: string
  status?: string
  statusVariant?: string
  coverage?: number
  testsRun?: number
  testsPassed?: number
  testsFailed?: number
  passRate?: number | null
  endpoints?: number
  createdAt?: string
  lastModified?: string
  lastRun?: string
  specData?: unknown
  fileName?: string
  tested?: boolean
}

export interface SignupInitialResponse {
  message: string
  email: string
}

export interface SignupResponse {
  token: string
  user: UserData
  tenant: TenantData
  workspace: WorkspaceData
  project: ProjectData
  subscription: SubscriptionData
}

// ── Auth token and state helpers ───────────────────────────────────────
const AUTH_TOKEN_KEY = "cognitest-token"
const TENANT_ID_KEY = "cognitest-tenant-id"
const CURRENT_WORKSPACE_KEY = "cognitest-workspace-id"

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(AUTH_TOKEN_KEY)
}

export function setAuthToken(token: string): void {
  if (typeof window === "undefined") return
  window.localStorage.setItem(AUTH_TOKEN_KEY, token)
}

export function getTenantId(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(TENANT_ID_KEY)
}

export function setTenantId(id: string): void {
  if (typeof window === "undefined") return
  window.localStorage.setItem(TENANT_ID_KEY, id)
}

export function getWorkspaceId(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(CURRENT_WORKSPACE_KEY)
}

export function setWorkspaceId(id: string): void {
  if (typeof window === "undefined") return
  window.localStorage.setItem(CURRENT_WORKSPACE_KEY, id)
}

export function clearAuthState(): void {
  if (typeof window === "undefined") return
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
  window.localStorage.removeItem(TENANT_ID_KEY)
  window.localStorage.removeItem(CURRENT_WORKSPACE_KEY)
}

export function parseJwt(token: string) {
  try {
    const base64Url = token.split(".")[1]
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/")
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join(""),
    )
    return JSON.parse(jsonPayload)
  } catch (e) {
    return null
  }
}

// ── Shared fetch helper ──────────────────────────────────────────────
async function request<TResponse = unknown, TBody = JsonRecord>(
  path: string,
  { method = "GET", body, timeout, fallbackMsg, skipAuth = false }: RequestOptions<TBody> = {},
): Promise<TResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  }

  // Attach JWT auth header if available
  if (!skipAuth) {
    const token = getAuthToken()
    if (token) {
      headers["Authorization"] = `Bearer ${token}`
    }
  }

  const init: RequestInit = {
    method,
    headers,
  }

  if (body !== undefined) {
    init.body = JSON.stringify(body)
  }

  // Default timeout prevents infinite loading spinners when backend is unreachable.
  // Set `timeout: 0` explicitly to disable.
  const effectiveTimeout = typeof timeout === "number" ? timeout : 15000

  let controller: AbortController | null = null
  let timeoutId: ReturnType<typeof setTimeout> | undefined

  if (effectiveTimeout > 0) {
    controller = new AbortController()
    init.signal = controller.signal
    timeoutId = setTimeout(() => controller?.abort(), effectiveTimeout)
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, init)

    if (!response.ok) {
      // ── 401 Unauthorized — session expired or token invalid ──────────────
      // Clear all stored auth state and redirect to login so the user doesn't
      // remain in a broken authenticated-looking state. skipAuth calls (login,
      // signup) are exempt — a 401 from those is a real credential error, not
      // a session expiry, and should fall through to the normal error path.
      if (response.status === 401 && !skipAuth) {
        clearAuthState()
        // Clear every other piece of user state stored by AuthContext
        if (typeof window !== "undefined") {
          window.localStorage.removeItem("cognitest-user")
          window.localStorage.removeItem("cognitest-workspace")
          window.localStorage.removeItem("cognitest-project")
          // Redirect with a query param so the login page can show a message
          window.location.href = "/login?reason=session_expired"
        }
        // Throw so any awaiting caller knows the call failed, but the page
        // redirect means the user will never see this message.
        throw new Error("Session expired. Please log in again.")
      }

      const errorPayload = await response.json().catch(() => undefined)
      const message = extractErrorMessage(errorPayload) || fallbackMsg || "Request failed"
      throw new Error(message)
    }

    if (response.status === 204) {
      return undefined as TResponse
    }

    const contentType = response.headers.get("content-type") || ""
    if (contentType.includes("application/json")) {
      return (await response.json()) as TResponse
    }

    // Some endpoints may legitimately return an empty body (or non-JSON) on success.
    const text = await response.text().catch(() => "")
    if (!text) return undefined as TResponse
    return text as unknown as TResponse
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(fallbackMsg || "Request timed out")
    }

    if (err instanceof Error) {
      throw err
    }

    throw new Error(fallbackMsg || "Unknown request error")
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
  }
}

function extractErrorMessage(payload: unknown): string | null {
  if (payload && typeof payload === "object") {
    const maybeError = payload as Record<string, unknown>
    if (typeof maybeError.detail === "string") return maybeError.detail
    if (typeof maybeError.error === "string") return maybeError.error
    if (typeof maybeError.message === "string") return maybeError.message
  }
  return null
}

// ── Auth API ─────────────────────────────────────────────────────────

/** Login user via backend */
export function loginUser(email: string, passcode: string, inviteToken?: string) {
  return request<LoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: { email, passcode, inviteToken },
    skipAuth: true,
    fallbackMsg: "Login failed",
  })
}

/** Signup user via backend (Initial phase) */
export function signupUser(data: {
  email: string
  name: string
  passcode: string
  company?: string
  contactNumber?: string
  inviteToken?: string
}) {
  return request<SignupInitialResponse>("/api/v1/auth/signup", {
    method: "POST",
    body: data,
    // Signup can be slow on first run (tenant + role/permission seeding + OTP email).
    timeout: 60000,
    skipAuth: true,
    fallbackMsg: "Signup failed",
  })
}

/** Verify user OTP and finalize login */
export function verifyOtp(email: string, otp: string, inviteToken?: string) {
  return request<SignupResponse>("/api/v1/auth/verify", {
    method: "POST",
    body: { email, otp, inviteToken },
    skipAuth: true,
    fallbackMsg: "OTP verification failed",
  })
}

/** Change password via backend (requires auth) */
export function changePassword(currentPassword: string, newPassword: string) {
  return request<{ message: string }>("/api/v1/auth/change-password", {
    method: "POST",
    body: { currentPassword, newPassword },
    fallbackMsg: "Failed to change password",
  })
}

// ── Public API (Projects & Runs) ─────────────────────────────────────

/** Generate test cases from a Swagger JSON spec (file upload) */
export function generateTestCasesFromSpec(spec: Record<string, unknown>) {
  return request<GeneratedRunResponse>("/api/v1/runs/generate-from-spec", {
    method: "POST",
    body: { spec },
    fallbackMsg: "Failed to generate test cases",
  })
}

/** Update test cases for a specific run */
export function updateTestCases(runId: string, collection: unknown) {
  return request("/api/v1/runs/update", {
    method: "POST",
    body: { runId, collection },
    fallbackMsg: "Failed to update test cases",
  })
}

/** Get the collection for a specific run */
export function getCollection(runId: string) {
  return request(`/api/v1/runs/${runId}`, {
    fallbackMsg: "Failed to get collection",
  })
}

/** Get the total number of tests in a collection */
export function getTestCount(runId: string) {
  return request(`/api/v1/runs/${runId}/count`, {
    fallbackMsg: "Failed to get test count",
  })
}

/** Execute a single batch of tests (2 min timeout) */
export function executeBatch(runId: string, batchIndex: number, batchSize = 10, baseUrl?: string, testCases?: unknown[]) {
  return request(`/api/v1/runs/${runId}/execute-batch`, {
    method: "POST",
    body: { batchIndex, batchSize, baseUrl, testCases },
    timeout: 120000,
    fallbackMsg: `Batch ${batchIndex + 1} timed out. Please try again.`,
  })
}

export interface CreateProjectRequest {
  name: string
  description?: string
  workspaceId: string
}

/** Get backend project metadata (spec status, last run). */
export function getProjectMeta(projectId: string) {
  return request<ProjectMetaResponse>(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
    fallbackMsg: "Failed to load project metadata",
  })
}

/** Check if user can create more projects based on subscription plan */
export function checkProjectLimit() {
  return request<{
    canCreate: boolean
    currentCount: number
    maxProjects: number
    planName: string
    message: string
  }>("/api/v1/projects/check-limit", {
    fallbackMsg: "Failed to check project limit",
  })
}

/** Create a new project */
export function createProject(data: CreateProjectRequest) {
  return request<ProjectData>("/api/v1/projects/", {
    method: "POST",
    body: data as unknown as JsonRecord,
    fallbackMsg: "Failed to create project",
  })
}

/** Update a project's name and/or description */
export function updateProject(projectId: string, data: { name?: string; description?: string }) {
  return request<ProjectData>(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
    method: "PATCH",
    body: data as unknown as JsonRecord,
    fallbackMsg: "Failed to update project",
  })
}

/** Delete a project */
export function deleteProject(projectId: string) {
  return request<void>(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
    fallbackMsg: "Failed to delete project",
  })
}

/** Get all projects for a workspace */
export function getWorkspaceProjects(workspaceId: string) {
  return request<ProjectData[]>(`/api/v1/projects/workspace/${encodeURIComponent(workspaceId)}`, {
    fallbackMsg: "Failed to load projects",
  })
}

export interface ProjectMember {
  userId: string
  name: string | null
  email: string
  role: string
}

/** Get all members assigned to a specific project */
export function getProjectMembers(projectId: string) {
  return request<ProjectMember[]>(`/api/v1/projects/${encodeURIComponent(projectId)}/members`, {
    fallbackMsg: "Failed to load project members",
  })
}

/** Get all uploaded specifications for a project */
export function getProjectSpecs(projectId: string) {
  return request<SpecInfo[]>(`/api/v1/projects/${encodeURIComponent(projectId)}/specs`, {
    fallbackMsg: "Failed to load project specifications",
  })
}
/** Get parsed spec content by specId */
export function getProjectSpecContent(projectId: string, specId: string) {
  return request<any>(`/api/v1/projects/${encodeURIComponent(projectId)}/specs/${encodeURIComponent(specId)}/content`, {
    fallbackMsg: "Failed to load specification content",
  })
}


/** Get test results (passed/failed) corresponding to a specific uploaded spec */
export function getSpecTestResults(projectId: string, specId: string) {
  return request<SpecTestResultsResponse>(`/api/v1/projects/${encodeURIComponent(projectId)}/specs/${encodeURIComponent(specId)}/results`, {
    fallbackMsg: "Failed to load spec test results",
  })
}

// ── AI Generator ─────────────────────────────────────────────────────────

export interface TestTypesResponse {
  types: string[]
}

/** Get the list of supported AI test generation types */
export function getGeneratorTypes() {
  return request<TestTypesResponse>("/api/v1/generator/types", {
    fallbackMsg: "Failed to load test types",
  })
}

export interface DraftTestCase {
  id: string
  name: string
  test_type: string
  endpoint_path: string
  method: string
  description?: string | null
  category?: string | null          // "crud" | "schema" | "params" | "workflow" | "pagination"
  ai_explanation?: string | null    // AI-generated explanation of what this test validates
  owasp_category?: string | null
  owasp_id?: string | null
  owasp_name?: string | null
  security_intent?: string | null
  ai_coverage_rationale?: string | null
  generation_source?: string | null
  metadata?: Record<string, unknown> | null

  // Request data (what the execution engine sends)
  headers?: Record<string, string> | null
  query_params?: Record<string, unknown> | null
  request_body?: Record<string, unknown> | null
  path_params?: Record<string, string> | null

  // Assertions (what to check)
  expected_status: number
  expected_response?: Record<string, unknown> | null
  assertions?: string[] | null
}

export interface GenerateTestsResponse {
  project_id: string
  test_type: string
  cases: DraftTestCase[]
  count: number
  generation_method: "rule_based" | "ai_enhanced" | "hybrid"
  base_url?: string | null
}

export interface AIAnalysisResponse {
  analysis: {
    root_cause: string
    explanation: string
    suggested_fix: string
    severity: "critical" | "high" | "medium" | "low"
  }
  ai_powered: boolean
  tokens_used?: { input_tokens: number; output_tokens: number }
}

export interface RunResultsResponse {
  results: Array<{
    id: string
    name: string
    endpoint_path: string
    method: string
    expected_status: number
    actual_status: number
    passed: boolean
    response_time_ms: number
    response_body: string
    response_headers: Record<string, string>
    error_message: string
    request_headers?: Record<string, string> | null
    request_body?: Record<string, unknown> | null
    query_params?: Record<string, unknown> | null
    log: string
  }>
  summary: { total: number; passed: number; failed: number }
  base_url: string
  executed_at: string
}

export interface GenerationMeta {
  generation_method: "rule_based" | "ai_enhanced" | "hybrid"
  ai_tokens_used: number
  test_type: string
  generated_at: string
}

/** Generate test cases for a project from its spec.
 *  - use_ai=false → synchronous, returns GenerateTestsResponse directly (200)
 *  - use_ai=true  → async job, returns GenerationJobAccepted (202) — poll getGenerationJob()
 */
export function generateAISuite(projectId: string, specId: string, testType: string, maxTests?: number, useAI = false, useBatch = true) {
  if (!useAI) {
    // Rule-based: always synchronous
    return request<GenerateTestsResponse>(
      `/api/v1/projects/${encodeURIComponent(projectId)}/generate-tests`,
      {
        method: "POST",
        body: { spec_id: specId, test_type: testType, max_tests: maxTests, use_ai: false, use_batch: useBatch } as unknown as Record<string, unknown>,
        timeout: 60000,
        fallbackMsg: "Failed to generate test suite",
      },
    )
  }
  // AI-enhanced: returns 202 + job_id immediately
  return request<GenerationJobAccepted>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/generate-tests`,
    {
      method: "POST",
      body: { spec_id: specId, test_type: testType, max_tests: maxTests, use_ai: true, use_batch: useBatch } as unknown as Record<string, unknown>,
      timeout: 30000,
      fallbackMsg: "Failed to start AI generation",
    },
  )
}

export interface GenerationJobAccepted {
  job_id: string
  status: "pending"
  message: string
}

export interface GenerationJobStatus {
  job_id: string
  project_id: string
  test_type: string
  status: "pending" | "running" | "completed" | "failed" | "partial"
  progress: number
  total: number
  suite_id: string | null
  result: {
    project_id: string
    test_type: string
    count: number
    suite_id: string
    generation_method: string
    base_url: string | null
  } | null
  error: string | null
  created_at: string
  updated_at: string
}

/** Poll the status of an async AI generation job */
export function getGenerationJob(projectId: string, jobId: string) {
  return request<GenerationJobStatus>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/generation-jobs/${encodeURIComponent(jobId)}`,
    { fallbackMsg: "Failed to get job status" },
  )
}

/** List recent generation jobs for a project */
export function listGenerationJobs(projectId: string) {
  return request<Array<{
    job_id: string
    test_type: string
    status: string
    progress: number
    total: number
    suite_id: string | null
    created_at: string
  }>>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/generation-jobs`,
    { fallbackMsg: "Failed to list generation jobs" },
  )
}

/** Get remaining AI token budget for the project's tenant */
export function getTokenBudget(projectId: string) {
  return request<{
    tenant_id: string
    remaining_tokens: number  // -1 = unlimited
    monthly_limit: number     // -1 = unlimited
    unlimited: boolean
  }>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/token-budget`,
    { fallbackMsg: "Failed to get token budget" },
  )
}

/** Fetch existing draft test cases for a project */
export function getProjectTestCases(projectId: string) {
  return request<DraftTestCase[]>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/test-cases`,
    { fallbackMsg: "Failed to load test cases" },
  )
}

/** Fetch test cases from database for a project */
export function getProjectTestCasesFromDb(
  projectId: string,
  opts?: {
    version?: string
    specId?: string
    testTypes?: string[]
    methods?: string[]
  },
) {
  const params = new URLSearchParams()
  if (opts?.version) params.set("version", opts.version)
  if (opts?.specId) params.set("spec_id", opts.specId)
  if (opts?.testTypes && opts.testTypes.length > 0) params.set("test_types", opts.testTypes.join(","))
  if (opts?.methods && opts.methods.length > 0) params.set("methods", opts.methods.join(","))

  const qs = params.toString()
  return request<DraftTestCase[]>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/test-cases-db${qs ? `?${qs}` : ""}`,
    { fallbackMsg: "Failed to load test cases from database" },
  )
}

// ==========================================
// Super Admin Data Types & Requests
// ==========================================

export interface SuperAdminStats {
  totalTenants: number
  activeTenants: number
  totalUsers: number
  subscribedTenants: number
  freeTenants: number
  enterpriseTenants: number
  totalProjects: number
  totalTestRuns: number
  totalTests: number
  totalPassed: number
  totalFailed: number
  totalSkipped: number
  adminCount: number
  memberCount: number
}

export interface TenantStatSummary {
  totalProjects: number
  totalTestRuns: number
  totalPassed: number
  totalFailed: number
  activeEndpoints: number
  riskScore: string
  tokenQuota: string
  activeIncidents: number
  health: string
}

export interface TenantTeamMember {
  id: string
  name: string
  email: string
  role: string
  avatar: string | null
  status: string
}

export interface TenantProjectSummary {
  id: string
  title: string
  status: string
  testRuns: number
  tasks: string
  prog: number
  color: string
}

export interface SuperAdminTenant {
  id: string
  name: string
  avatar: string | null
  email: string
  phone: string
  role: string
  location: string
  plan: string
  status: string
  company: string
  createdAt: string | null
  stats: TenantStatSummary
  team: TenantTeamMember[]
  projects: TenantProjectSummary[]
}

export function getSuperAdminStats() {
  return request<SuperAdminStats>(`/api/v1/super-admin/stats`, {
    fallbackMsg: "Failed to load super admin stats"
  })
}

export function getSuperAdminTenants() {
  return request<SuperAdminTenant[]>(`/api/v1/super-admin/tenants`, {
    fallbackMsg: "Failed to load super admin tenants"
  })
}

export interface SuperAdminTestStats {
  totalTests: number
  totalPassed: number
  totalFailed: number
  totalSkipped: number
  categoryStats: Record<string, { total: number; passed: number; failed: number }>
  recentExecutions: Array<{
    tenant: string
    testType: string
    category: string
    priority: string
    status: string
    coverage: string
    duration: string
    timestamp: string
  }>
}

export function getSuperAdminTestStats() {
  return request<SuperAdminTestStats>(`/api/v1/super-admin/test-stats`, {
    fallbackMsg: "Failed to load test system stats"
  })
}

export interface SuperAdminBillingStats {
  planCounts: Record<string, number>
  planTenants: Record<string, Array<{
    tenantId: string
    tenantName: string
    status: string
    startDate: string | null
    expiryDate: string | null
  }>>
  totalSubscriptions: number
}

export function getSuperAdminBillingStats() {
  return request<SuperAdminBillingStats>(`/api/v1/super-admin/billing-stats`, {
    fallbackMsg: "Failed to load billing stats"
  })
}

export function createSuperAdminTenant(data: { name?: string; email: string; password?: string; plan?: string }) {
  return request<{ status: string; tenantId: string }>(`/api/v1/super-admin/tenants`, {
    method: "POST",
    body: data as unknown as JsonRecord,
    fallbackMsg: "Failed to create tenant",
  })
}

export function updateSuperAdminTenant(id: string, data: { name?: string; email?: string; password?: string; plan?: string }) {
  return request<{ status: string }>(`/api/v1/super-admin/tenants/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: data as unknown as JsonRecord,
    fallbackMsg: "Failed to update tenant",
  })
}

export function updateSuperAdminTenantStatus(id: string, status: string) {
  return request<{ status: string }>(`/api/v1/super-admin/tenants/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    body: { status } as unknown as JsonRecord,
    fallbackMsg: "Failed to update tenant status",
  })
}

export function deleteSuperAdminTenant(id: string) {
  return request<{ status: string }>(`/api/v1/super-admin/tenants/${encodeURIComponent(id)}`, {
    method: "DELETE",
    fallbackMsg: "Failed to delete tenant",
  })
}

export function updateSuperAdminUserStatus(id: string, status: string) {
  return request<{ status: string }>(`/api/v1/super-admin/users/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    body: { status } as unknown as JsonRecord,
    fallbackMsg: "Failed to update user status",
  })
}

export function deleteSuperAdminProject(id: string) {
  return request<{ status: string }>(`/api/v1/super-admin/projects/${encodeURIComponent(id)}`, {
    method: "DELETE",
    fallbackMsg: "Failed to delete project",
  })
}

// ─── Token Usage Analytics ───────────────────────────────────────────────────

export interface TokenUsageEntry {
  timestamp: string
  project_id: string
  project_name: string
  test_type: string
  suite_id: string
  generation_method: string
  test_case_name: string
  endpoint_path: string
  method: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
  cache_creation_tokens?: number
  cache_read_tokens?: number
  savings_usd?: number
  is_batch?: boolean
}

export interface TokenUsageResponse {
  entries: TokenUsageEntry[]
  total: number
}

export function getSuperAdminTokenUsage() {
  return request<TokenUsageResponse>("/api/v1/super-admin/token-usage", {
    fallbackMsg: "Failed to load token usage data",
  })
}

export interface TestRunHistory {
  id: string
  runDate: string
  runTime: string
  status: "PASS" | "FAIL" | string
  statusCode: number
  responseTime: string
  duration: string
  errorMessage?: string
  payload?: Record<string, unknown> | null
}

export interface TestExecutionCase {
  id: string
  name: string
  endpoint: string
  method: string
  totalRuns: number
  passed: number
  failed: number
  lastStatus: "PASS" | "FAIL" | string
  history: TestRunHistory[]
  test_type?: string
}

/** Fetch test cases with execution history for a project */
export function getTestExecutions(projectId: string, category?: string, version?: string, specId?: string) {
  const params = new URLSearchParams()
  if (category && category !== "All Categories" && category !== "All") params.append("category", category)
  if (version) params.append("version", version)

  // Optional: filter executions to a specific uploaded spec
  if (specId) params.append("spec_id", specId)

  const query = params.toString()

  return request<TestExecutionCase[]>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/test-executions${query ? "?" + query : ""}`,
    { fallbackMsg: "Failed to load test executions" }
  )
}

/** Category stats from TestRun records (authoritative historical data) */
export interface CategoryStatsItem {
  category: string
  passed: number
  failed: number
  totalRuns: number
}

/** Fetch aggregated pass/fail stats per category from TestRun records */
export function getCategoryStats(projectId: string, opts?: { version?: string; specId?: string }) {
  const params = new URLSearchParams()
  if (opts?.version) params.append("version", opts.version)
  if (opts?.specId) params.append("spec_id", opts.specId)
  const query = params.toString()

  return request<CategoryStatsItem[]>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/category-stats${query ? "?" + query : ""}`,
    { fallbackMsg: "Failed to load category stats" }
  )
}

/** Inline-edit a single draft test case */
export function updateTestCase(
  projectId: string,
  caseId: string,
  data: Partial<Omit<DraftTestCase, "id">>,
) {
  return request<DraftTestCase>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/test-cases/${encodeURIComponent(caseId)}`,
    {
      method: "PATCH",
      body: data as unknown as Record<string, unknown>,
      fallbackMsg: "Failed to update test case",
    },
  )
}

/** Delete a draft test case from the project */
export function deleteTestCase(projectId: string, caseId: string) {
  return request<void>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/test-cases/${encodeURIComponent(caseId)}`,
    {
      method: "DELETE",
      fallbackMsg: "Failed to delete test case",
    },
  )
}

/** Analyze a failed test case using AI */
export function analyzeFailure(
  projectId: string,
  data: {
    test_name: string
    test_type: string
    method: string
    endpoint_path: string
    expected_status: number
    actual_status: number
    response_body?: string
    error_message?: string
    request_body?: string
    description?: string
  },
) {
  return request<AIAnalysisResponse>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/analyze-failure`,
    {
      method: "POST",
      body: data as unknown as Record<string, unknown>,
      fallbackMsg: "Failed to analyze failure",
    },
  )
}

/** Retrieve cached run results */
export function getRunResults(projectId: string) {
  return request<RunResultsResponse>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/run-results`,
    { fallbackMsg: "Failed to load run results" },
  )
}

/** Retrieve generation metadata (method, tokens used, etc.) */
export function getGenerationMeta(projectId: string) {
  return request<GenerationMeta>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/generation-meta`,
    { fallbackMsg: "Failed to load generation metadata" },
  )
}

/** Export current draft test cases as a Postman Collection */
export function exportPostmanCollection(projectId: string) {
  return request<any>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/export-postman`,
    {
      method: "GET",
      fallbackMsg: "Failed to export Postman collection",
    },
  )
}

/** Upload a Swagger/OpenAPI spec file for a project (multipart/form-data). */
export async function uploadProjectSpec(projectId: string, file: File) {
  const form = new FormData()
  form.append("spec", file)

  const headers: Record<string, string> = {}
  const token = getAuthToken()
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const response = await fetch(
    `${API_BASE_URL}/api/v1/projects/${encodeURIComponent(projectId)}/spec`,
    {
      method: "POST",
      body: form,
      headers,
    },
  )

  if (!response.ok) {
    const err = await response.json().catch(() => undefined)
    const message = extractErrorMessage(err) || "Failed to upload spec"
    throw new Error(message)
  }
  return (await response.json()) as JsonRecord
}

/** Generate+execute tests for a project using its stored spec. */
export function runProject(projectId: string, { baseUrl = "" }: { baseUrl?: string } = {}) {
  return request<RunProjectResponse>(`/api/v1/projects/${encodeURIComponent(projectId)}/run`, {
    method: "POST",
    body: { baseUrl },
    timeout: 300000,
    fallbackMsg: "Project run timed out. Please try again.",
  })
}

// ── Frontend-only storage helpers (no backend required) ─────────────

const RUN_SUMMARIES_KEY = "cognitest-run-summaries:v1"

function safeParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json) as T
  } catch {
    return fallback
  }
}

export interface CreateWorkspaceRequest {
  name: string
}

/** List all workspaces for the tenant */
export function listWorkspaces() {
  return request<WorkspaceData[]>("/api/v1/workspaces/", {
    fallbackMsg: "Failed to load workspaces",
  })
}

/** Create a new workspace */
export function createWorkspace(data: CreateWorkspaceRequest) {
  return request<WorkspaceData>("/api/v1/workspaces/", {
    method: "POST",
    body: data as unknown as JsonRecord,
    fallbackMsg: "Failed to create workspace",
  })
}

/** Update an existing workspace */
export function updateWorkspace(workspaceId: string, data: CreateWorkspaceRequest) {
  return request<WorkspaceData>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: "PATCH",
    body: data as unknown as JsonRecord,
    fallbackMsg: "Failed to update workspace",
  })
}

export interface MemberData {
  id: string
  workspaceId: string
  userId: string
  roleId: string
  user?: UserData
  role?: { id: string; name: string }
}

/** List all members of a workspace */
export function listMembers(workspaceId: string) {
  return request<MemberData[]>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`, {
    fallbackMsg: "Failed to load members",
  })
}

/** Add a member to a workspace */
export function addMemberToWorkspace(workspaceId: string, email: string, roleName: string) {
  return request<MemberData>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`, {
    method: "POST",
    body: { email, roleName },
    fallbackMsg: "Failed to add member",
  })
}

/** Update member role */
export function updateMemberRole(workspaceId: string, userId: string, roleName: string) {
  return request<MemberData>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: { roleName },
    fallbackMsg: "Failed to update member role",
  })
}

export interface ProjectAssignment {
  projectId: string
  roleId: string
}

export interface CreateUserByAdminPayload {
  name: string
  email: string
  password: string
  company?: string
  contactNumber?: string
  systemRole?: string
  workspaceRoleName: string
  projectAssignments: ProjectAssignment[]
  inviteMessage?: string
  sendInAppNotification?: boolean
}

export interface CreateUserByAdminResponse {
  userId: string
  name: string | null
  email: string
  company?: string | null
  contactNumber?: string | null
  systemRole: string
  workspaceMemberId: string
  projectAssignments: ProjectAssignment[]
}

/** Admin creates a brand-new user account with role + project assignments */
export function createUserByAdmin(workspaceId: string, data: CreateUserByAdminPayload) {
  return request<CreateUserByAdminResponse>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/create-user`,
    {
      method: "POST",
      body: data as unknown as JsonRecord,
      fallbackMsg: "Failed to create user",
    }
  )
}

export interface CreateInvitationPayload {
  email: string
  roleId: string
  workspaceId?: string
  projectId?: string
  message?: string
}

export interface InvitationResponse {
  id: string
  email: string
  roleId: string
  status: string
  token: string
}

/** Admin creates a new invitation */
export function createInvitation(data: CreateInvitationPayload) {
  return request<InvitationResponse>(
    `/api/v1/invitations`,
    {
      method: "POST",
      body: data as unknown as JsonRecord,
      fallbackMsg: "Failed to create invitation",
    }
  )
}

export interface ValidationResponse {
  valid: boolean
  message: string
  invitation?: {
    email: string
    role: { id: string; name: string }
    project?: { id: string; name: string } | null
    workspace?: { id: string; name: string } | null
    inviter?: { id: string; name: string; email: string } | null
    expiresAt: string
  }
}

export function validateInvitation(token: string) {
  return request<ValidationResponse>(`/api/v1/invitations/${token}/validate`, {
    fallbackMsg: "Failed to validate invitation",
    skipAuth: true,
  })
}

export function acceptInvitation(token: string) {
  return request<{ message: string; invitationId: string }>(`/api/v1/invitations/${token}/accept`, {
    method: "POST",
    fallbackMsg: "Failed to accept invitation",
  })
}

export interface FullInvitationResponse extends InvitationResponse {
  createdAt: string
  expiresAt: string
  inviterId: string
  projectId?: string
  workspaceId?: string
}

export function getInvitations(workspaceId?: string, projectId?: string) {
  const params = new URLSearchParams()
  if (workspaceId) params.append("workspace_id", workspaceId)
  if (projectId) params.append("project_id", projectId)
  const qs = params.toString() ? `?${params.toString()}` : ""

  return request<FullInvitationResponse[]>(`/api/v1/invitations${qs}`, {
    fallbackMsg: "Failed to load invitations",
  })
}

export function revokeInvitation(invitationId: string) {
  return request<InvitationResponse>(`/api/v1/invitations/${invitationId}/revoke`, {
    method: "POST",
    fallbackMsg: "Failed to revoke invitation",
  })
}

export function resendInvitation(invitationId: string) {
  return request<InvitationResponse>(`/api/v1/invitations/${invitationId}/resend`, {
    method: "POST",
    fallbackMsg: "Failed to resend invitation",
  })
}

/** Replace all project assignments for a member */
export function updateProjectAssignments(
  workspaceId: string,
  userId: string,
  assignments: Array<{ projectId: string; roleId: string }>
) {
  return request<{ userId: string; projectAssignments: ProjectAssignment[] }>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}/project-assignments`,
    {
      method: "PUT",
      body: { assignments } as unknown as JsonRecord,
      fallbackMsg: "Failed to update project assignments",
    }
  )
}

/** Store a run summary locally so UI can show it later (dummy-friendly). */
export function storeRunSummary(runId: string, payload: RunSummaryPayload) {
  if (typeof window === "undefined") return Promise.resolve(false)
  const raw = window.localStorage.getItem(RUN_SUMMARIES_KEY)
  const prev = raw ? safeParse<Record<string, unknown>>(raw, {}) : {}
  const next = {
    ...prev,
    [runId]: {
      ...payload,
      runId,
      storedAt: new Date().toISOString(),
    },
  }
  window.localStorage.setItem(RUN_SUMMARIES_KEY, JSON.stringify(next))
  return Promise.resolve(true)
}

// ── Roles & Permissions API ──────────────────────────────────────────

export interface PermissionData {
  id: string
  name: string
  resource: string
  action: string
  description?: string | null
}

export interface RoleData {
  id: string
  name: string
  description?: string | null
  tenantId?: string | null
  workspaceId?: string | null
  createdAt: string
  permissions: PermissionData[]
}

/** List all roles for the current tenant */
export function getRoles() {
  return request<RoleData[]>("/api/v1/roles/", {
    fallbackMsg: "Failed to load roles",
  })
}

/** Create a new role */
export function createRole(name: string, description?: string) {
  return request<RoleData>("/api/v1/roles/", {
    method: "POST",
    body: { name, description } as unknown as JsonRecord,
    fallbackMsg: "Failed to create role",
  })
}

/** Delete a role by ID */
export function deleteRole(roleId: string) {
  return request<void>(`/api/v1/roles/${encodeURIComponent(roleId)}`, {
    method: "DELETE",
    fallbackMsg: "Failed to delete role",
  })
}

/** Replace a role's permissions */
export function updateRolePermissions(roleId: string, permissionIds: string[]) {
  return request<RoleData>(`/api/v1/roles/${encodeURIComponent(roleId)}/permissions`, {
    method: "PATCH",
    body: { permissionIds } as unknown as JsonRecord,
    fallbackMsg: "Failed to update role permissions",
  })
}

/** List all available system permissions */
export function getAllPermissions() {
  return request<PermissionData[]>("/api/v1/roles/permissions", {
    fallbackMsg: "Failed to load permissions",
  })
}

// ── Dashboard & Reports API ──────────────────────────────────────────

export interface DashboardRecentRun {
  id: string
  projectName: string
  projectId: string
  status: string
  totalTests: number
  passed: number
  failed: number
  duration: string
  date: string | null
}

export interface DashboardActiveProject {
  id: string
  name: string
  description: string | null
  swaggerName?: string
  swaggerVersion?: string
  lastRunDate: string | null
  lastRunStatus: string | null
  passed: number
  failed: number
  passRate: number | null
  totalRuns?: number
  totalApisTested?: number
  apiVersion?: string | null
}

export interface DashboardStats {
  totalApisTested: number
  totalProjects: number
  totalTestRuns: number
  passRate: number
  totalTestsRun: number
  totalPassed: number
  totalFailed: number
  testDistribution?: Record<string, number>
  recentRuns: DashboardRecentRun[]
  activeProjects: DashboardActiveProject[]
}

export interface ReportTestSummary {
  name: string
  method: string
  endpoint: string
  expected: number
  actual: number
  message?: string
  responseTimeMs?: number | null
  category?: string | null
  subCategory?: string | null
}

export interface ReportData {
  id: string
  project: string
  projectId: string
  date: string
  duration: string
  passed: number
  failed: number
  coverage: number
  vulns: number
  categorySummary?: Record<string, number>
  passedTests: ReportTestSummary[]
  failedTests: ReportTestSummary[]
}

/** Get aggregated dashboard statistics */
export function getDashboardStats() {
  return request<DashboardStats>("/api/v1/dashboard/stats", {
    fallbackMsg: "Failed to load dashboard stats",
  })
}

/** Get list of reports (test runs) */
export function getReports() {
  return request<ReportData[]>("/api/v1/dashboard/reports", {
    fallbackMsg: "Failed to load reports",
  })
}

/** Get detailed report for a single test run */
export function getReportDetail(runId: string) {
  return request<ReportData>(`/api/v1/dashboard/reports/${encodeURIComponent(runId)}`, {
    fallbackMsg: "Failed to load report detail",
  })
}

export interface SupportTicketPayload {
  subject: string
  category: "bug" | "billing" | "feature" | "account"
  description: string
  workspaceId?: string | null
}

export interface SupportTicketResponse {
  id: string
  subject: string
  category: string
  description: string
  status: string
  userId?: string | null
  workspaceId?: string | null
  createdAt: string
  updatedAt: string
}

/** Submit a support ticket to the backend */
export function submitSupportTicket(data: SupportTicketPayload) {
  return request<SupportTicketResponse, SupportTicketPayload>("/api/v1/support/tickets", {
    method: "POST",
    body: data,
    fallbackMsg: "Failed to submit support ticket",
  })
}
