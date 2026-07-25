export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "HEAD" | "OPTIONS"

export type TestCaseStatus = "pending" | "running" | "passed" | "failed"

export interface TestCase {
  id: string
  method: HttpMethod | string
  endpoint: string
  expected: number | string
  description?: string
  name?: string
  payloadData?: Record<string, unknown>
  type?: string
}

export type RawTestCase = Partial<TestCase> & {
  url?: string
  expectedStatus?: number | string
  body?: Record<string, unknown>
}

export interface ExecutionResult extends TestCase {
  status: TestCaseStatus
  time: string | null
  error?: string
}

export type LogType = "run" | "pass" | "fail" | "info"

export interface ExecutionLogEntryMeta {
  method?: HttpMethod | string
  endpoint?: string
}

export interface ExecutionLogEntry {
  ts: string
  type: LogType
  msg: string
  meta?: ExecutionLogEntryMeta
}

export interface ExecutedBySummary {
  id: string | null
  username: string | null
  displayName: string
}
