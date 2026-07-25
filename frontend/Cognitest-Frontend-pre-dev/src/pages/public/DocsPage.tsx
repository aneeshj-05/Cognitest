import { useState, useEffect, type ChangeEvent, type ReactNode } from "react"
import { useSearchParams } from "react-router-dom"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  Book, Rocket, KeyRound, FlaskConical, GitBranch, FileBarChart2,
  AlertTriangle, ChevronRight, Lightbulb, Shield, Webhook, Layers, Globe,
} from "lucide-react"

import type { LucideIcon } from "lucide-react"

interface DocsSectionContent {
  title: string
  body: ReactNode
}

interface DocsSection {
  id: string
  label: string
  icon: LucideIcon
  content: DocsSectionContent
}

const sections: DocsSection[] = [
  {
    id: "introduction",
    label: "Introduction",
    icon: Book,
    content: {
      title: "Introduction to Cognitest",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed">
            Cognitest is an AI-powered autonomous API testing platform that transforms how engineering teams approach quality assurance. Instead of writing test cases manually, Cognitest analyzes your API structure and auto-generates a comprehensive test suite covering functionality, security, edge cases, and performance — all within minutes.
          </p>

          <h3 className="mt-8 mb-4 text-lg font-semibold text-foreground">How it works</h3>
          <ol className="space-y-4">
            {[
              { num: "1", text: <><strong>Ingest:</strong> Upload your API definition files. We support JSON and YAML formats for OpenAPI v2/v3 and Postman Collections.</> },
              { num: "2", text: <><strong>Analyze:</strong> Our AI understands your endpoints, request/response schemas, parameters, and relationships to build intelligent test scenarios.</> },
              { num: "3", text: <><strong>Generate:</strong> Cognitest auto-creates positive, negative, boundary, and security test cases tailored to each endpoint.</> },
              { num: "4", text: <><strong>Execute:</strong> Run tests on-demand against your live or staging environment, or schedule them automatically in CI/CD.</> },
              { num: "5", text: <><strong>Report:</strong> Get detailed reports with pass/fail breakdowns, response time distributions, security vulnerability findings, and coverage metrics.</> },
            ].map((item) => (
              <li key={item.num} className="flex gap-4">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-400">
                  {item.num}
                </span>
                <span className="text-muted-foreground leading-relaxed">{item.text}</span>
              </li>
            ))}
          </ol>

          <h3 className="mt-8 mb-4 text-lg font-semibold text-foreground">Why Cognitest?</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              { title: "Zero Manual Effort", desc: "Upload your spec and get tests instantly — no scripting." },
              { title: "AI-Driven Intelligence", desc: "Our models understand context, not just schema shapes." },
              { title: "Security-First", desc: "OWASP Top 10 coverage included out of the box." },
              { title: "CI/CD Native", desc: "Plug into GitHub Actions, GitLab CI, Jenkins, and more." },
            ].map((item) => (
              <div key={item.title} className="rounded-lg border border-border/60 bg-secondary/30 p-4">
                <h4 className="font-semibold text-foreground text-sm mb-1">{item.title}</h4>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-semibold text-emerald-400">Pro Tip</span>
            </div>
            <p className="text-sm text-muted-foreground">
              For best results, ensure your Swagger documentation includes example responses, schema definitions, and proper descriptions. This allows our AI to generate more precise validation checks and security scenarios.
            </p>
          </div>
        </>
      ),
    },
  },
  {
    id: "quickstart",
    label: "Quick Start",
    icon: Rocket,
    content: {
      title: "Quick Start Guide",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Get up and running with Cognitest in under 5 minutes. Follow these steps to run your first automated API test suite.
          </p>

          <div className="rounded-lg border border-border/60 bg-secondary/20 p-4 mb-6">
            <h4 className="font-semibold text-foreground text-sm mb-2">Prerequisites</h4>
            <ul className="space-y-1 text-sm text-muted-foreground">
              <li className="flex items-center gap-2"><ChevronRight className="h-3 w-3 text-emerald-400" /> A Cognitest account (free tier available)</li>
              <li className="flex items-center gap-2"><ChevronRight className="h-3 w-3 text-emerald-400" /> An OpenAPI (Swagger) spec or Postman Collection file</li>
              <li className="flex items-center gap-2"><ChevronRight className="h-3 w-3 text-emerald-400" /> Your API running (locally, staging, or production)</li>
            </ul>
          </div>

          <ol className="space-y-6">
            <li>
              <h4 className="font-semibold text-foreground mb-1">1. Create an Account</h4>
              <p className="text-muted-foreground text-sm">Sign up at Cognitest and verify your email address. You&apos;ll get 50 free test runs per month on the free tier.</p>
            </li>
            <li>
              <h4 className="font-semibold text-foreground mb-1">2. Create a New Project</h4>
              <p className="text-muted-foreground text-sm">Navigate to <strong>My Projects → New Project</strong>. Give it a name and optionally set your base URL and GitHub repository link.</p>
            </li>
            <li>
              <h4 className="font-semibold text-foreground mb-1">3. Upload Your API Spec</h4>
              <p className="text-muted-foreground text-sm">Drag and drop your Swagger (JSON/YAML) or Postman Collection file. Cognitest will parse all endpoints and display a summary.</p>
            </li>
            <li>
              <h4 className="font-semibold text-foreground mb-1">4. Configure Auth (if needed)</h4>
              <p className="text-muted-foreground text-sm">If your API requires authentication, navigate to <strong>Project → Settings → Auth</strong> and set up your token or API key.</p>
            </li>
            <li>
              <h4 className="font-semibold text-foreground mb-1">5. Generate & Run Tests</h4>
              <p className="text-muted-foreground text-sm">Click <strong>Generate Tests</strong>. Review the generated suite if you want, then hit <strong>Run All</strong>. Cognitest will execute tests against your API and display results in real time.</p>
            </li>
            <li>
              <h4 className="font-semibold text-foreground mb-1">6. Review Reports</h4>
              <p className="text-muted-foreground text-sm">Check the <strong>Reports</strong> section for detailed pass/fail breakdowns, response time charts, and security findings. Export as PDF for stakeholders.</p>
            </li>
          </ol>

          <div className="mt-8 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-semibold text-emerald-400">What&apos;s Next?</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Set up CI/CD integration to automatically test on every push, or explore advanced test configurations for custom headers, environment variables, and test parallelism.
            </p>
          </div>
        </>
      ),
    },
  },
  {
    id: "authentication",
    label: "Authentication",
    icon: KeyRound,
    content: {
      title: "Authentication",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Cognitest supports multiple authentication methods to securely interact with your APIs during testing. Configure these under <strong>Project → Settings → Auth</strong>.
          </p>

          <div className="space-y-4">
            {[
              { method: "Bearer Token (JWT)", desc: "Pass a JSON Web Token in the Authorization header. Supports auto-refresh if you provide a refresh endpoint.", badge: "Popular" },
              { method: "API Key", desc: "Send your key as a custom header (e.g. X-API-Key) or as a query parameter. Configure placement in settings." },
              { method: "Basic Auth", desc: "Standard username:password base64-encoded header. Useful for internal services and staging environments." },
              { method: "OAuth 2.0 (Client Credentials)", desc: "Cognitest handles the token exchange flow automatically. Provide client ID, secret, and token endpoint." },
              { method: "Custom Headers", desc: "Add any arbitrary headers (cookies, session tokens, CSRF tokens) that your API expects." },
            ].map((item) => (
              <div key={item.method} className="rounded-lg border border-border/60 bg-secondary/20 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="font-semibold text-foreground text-sm">{item.method}</h4>
                  {item.badge && <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/30">{item.badge}</Badge>}
                </div>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-lg border border-border bg-muted/30 p-4 font-mono text-sm text-muted-foreground">
            <p className="text-xs text-foreground font-sans font-semibold mb-2">Example: Bearer Token Configuration</p>
            <pre className="whitespace-pre-wrap">{`{
  "authType": "bearer",
  "token": "eyJhbGciOiJIUzI1NiIsInR...",
  "refreshUrl": "https://api.example.com/auth/refresh",
  "autoRefresh": true
}`}</pre>
          </div>

          <p className="mt-6 text-sm text-muted-foreground">
            <strong>Security:</strong> All credentials are encrypted at rest using AES-256 and never logged. Tokens are transmitted over TLS 1.3 only.
          </p>
        </>
      ),
    },
  },
  {
    id: "test-generation",
    label: "Test Generation",
    icon: FlaskConical,
    content: {
      title: "Test Generation",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Our AI agent analyzes your API schema to produce structured test cases. Here&apos;s what gets generated for each endpoint:
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { title: "Happy Path", desc: "Valid requests with correct parameters and payloads. Verifies 2xx responses and correct response schemas.", color: "text-emerald-400" },
              { title: "Negative Testing", desc: "Missing required fields, invalid types, boundary values (0, -1, MAX_INT), malformed JSON, wrong content types.", color: "text-red-400" },
              { title: "Security Checks", desc: "SQL injection, XSS, BOLA/IDOR, broken auth, mass assignment, SSRF detection, and rate limit testing.", color: "text-yellow-400" },
              { title: "Edge Cases", desc: "Empty arrays, null values, max-length strings, unicode/emoji, concurrent requests, idempotency checks.", color: "text-blue-400" },
              { title: "Performance", desc: "Response time thresholds, payload size limits, pagination stress tests, and connection timeout handling.", color: "text-purple-400" },
              { title: "Schema Validation", desc: "Response body matches documented schema, correct HTTP status codes, proper error response formats.", color: "text-orange-400" },
            ].map((item) => (
              <div key={item.title} className="rounded-lg border border-border/60 bg-secondary/20 p-4">
                <h4 className={`font-semibold text-sm mb-1 ${item.color}`}>{item.title}</h4>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
            ))}
          </div>

          <h3 className="mt-8 mb-4 text-lg font-semibold text-foreground">AI Capabilities</h3>
          <ul className="space-y-3">
            {[
              "Understands field relationships (e.g. startDate must be before endDate)",
              "Auto-detects required vs optional fields from schema",
              "Generates realistic test data using field names and types as context",
              "Chains dependent endpoints (e.g. create → get → update → delete)",
              "Adapts test strategies based on HTTP method semantics",
            ].map((text) => (
              <li key={text} className="flex items-start gap-3">
                <ChevronRight className="h-4 w-4 mt-0.5 text-emerald-400 shrink-0" />
                <span className="text-sm text-muted-foreground">{text}</span>
              </li>
            ))}
          </ul>
        </>
      ),
    },
  },
  {
    id: "api-specs",
    label: "API Specs",
    icon: Layers,
    content: {
      title: "Supported API Specifications",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Cognitest supports a wide range of API definition formats. Upload any of the following:
          </p>

          <div className="space-y-4">
            {[
              { name: "OpenAPI 3.0 / 3.1", ext: ".json, .yaml", desc: "The industry standard. Full support for components, schemas, security schemes, and server definitions." },
              { name: "Swagger 2.0", ext: ".json, .yaml", desc: "Legacy format still widely used. Automatically converted to OpenAPI 3.x internally for processing." },
              { name: "Postman Collection v2.1", ext: ".json", desc: "Export your Postman collection and upload directly. Supports folders, variables, and pre-request scripts." },
            ].map((spec) => (
              <div key={spec.name} className="rounded-lg border border-border/60 bg-secondary/20 p-4">
                <div className="flex items-center gap-3 mb-1">
                  <h4 className="font-semibold text-foreground text-sm">{spec.name}</h4>
                  <Badge variant="outline" className="text-[10px]">{spec.ext}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{spec.desc}</p>
              </div>
            ))}
          </div>

          <h3 className="mt-8 mb-4 text-lg font-semibold text-foreground">Schema Best Practices</h3>
          <ul className="space-y-3">
            {[
              "Include example values for request/response bodies — they produce better test data",
              "Define proper data types and formats (e.g. date-time, email, uuid)",
              "Use $ref for shared schemas to avoid duplication",
              "Document error response schemas (4xx / 5xx) for negative test validation",
              "Include parameter descriptions and enum values where applicable",
            ].map((text) => (
              <li key={text} className="flex items-start gap-3">
                <ChevronRight className="h-4 w-4 mt-0.5 text-emerald-400 shrink-0" />
                <span className="text-sm text-muted-foreground">{text}</span>
              </li>
            ))}
          </ul>
        </>
      ),
    },
  },
  {
    id: "cicd",
    label: "CI/CD Setup",
    icon: GitBranch,
    content: {
      title: "CI/CD Integration",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Integrate Cognitest into your CI/CD pipeline to automatically run API tests on every push, pull request, or scheduled interval.
          </p>

          <h3 className="mb-3 text-base font-semibold text-foreground">GitHub Actions</h3>
          <div className="rounded-lg border border-border bg-muted/30 p-4 font-mono text-sm text-muted-foreground mb-6">
            <pre className="whitespace-pre-wrap">{`name: API Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Cognitest
        uses: cognitest/action@v1
        with:
          api-key: \${{ secrets.COGNITEST_API_KEY }}
          project-id: your-project-id
          base-url: https://staging.yourapi.com
          fail-on-security: true`}</pre>
          </div>

          <h3 className="mb-3 text-base font-semibold text-foreground">GitLab CI</h3>
          <div className="rounded-lg border border-border bg-muted/30 p-4 font-mono text-sm text-muted-foreground mb-6">
            <pre className="whitespace-pre-wrap">{`cognitest:
  stage: test
  image: cognitest/runner:latest
  script:
    - cognitest run --project-id $PROJECT_ID
  variables:
    COGNITEST_API_KEY: $COGNITEST_API_KEY`}</pre>
          </div>

          <h3 className="mb-3 text-base font-semibold text-foreground">CLI Usage</h3>
          <div className="rounded-lg border border-border bg-muted/30 p-4 font-mono text-sm text-muted-foreground mb-6">
            <pre className="whitespace-pre-wrap">{`# Install CLI
npm install -g @cognitest/cli

# Login
cognitest login

# Run tests
cognitest run --project my-api --env staging

# Export results
cognitest export --format json --output results.json`}</pre>
          </div>

          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-semibold text-emerald-400">Pipeline Tip</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Use <code className="text-foreground bg-secondary px-1 rounded text-xs">fail-on-security: true</code> to block deployments if any security vulnerabilities are found.
            </p>
          </div>
        </>
      ),
    },
  },
  {
    id: "environments",
    label: "Environments",
    icon: Globe,
    content: {
      title: "Environment Management",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Test against different environments (development, staging, production) using environment configuration. Override base URLs, auth tokens, and custom variables per environment.
          </p>

          <div className="rounded-lg border border-border bg-muted/30 p-4 font-mono text-sm text-muted-foreground mb-6">
            <p className="text-xs text-foreground font-sans font-semibold mb-2">Example: Environment Config</p>
            <pre className="whitespace-pre-wrap">{`{
  "environments": {
    "development": {
      "baseUrl": "http://localhost:3000/api",
      "variables": { "timeout": 10000 }
    },
    "staging": {
      "baseUrl": "https://staging.api.example.com",
      "auth": { "type": "bearer", "token": "stg_token..." }
    },
    "production": {
      "baseUrl": "https://api.example.com",
      "auth": { "type": "bearer", "token": "prod_token..." }
    }
  }
}`}</pre>
          </div>

          <h3 className="mt-6 mb-4 text-lg font-semibold text-foreground">Variable Substitution</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Use double curly braces <code className="text-foreground bg-secondary px-1 rounded text-xs">{"{{variableName}}"}</code> in your tests. Cognitest will replace them with environment-specific values at runtime.
          </p>

          <ul className="space-y-3">
            {[
              "Base URLs auto-swap when switching environments",
              "Auth credentials rotate per environment securely",
              "Custom variables available for dynamic test data",
              "Environment-specific timeout and retry configurations",
            ].map((text) => (
              <li key={text} className="flex items-start gap-3">
                <ChevronRight className="h-4 w-4 mt-0.5 text-emerald-400 shrink-0" />
                <span className="text-sm text-muted-foreground">{text}</span>
              </li>
            ))}
          </ul>
        </>
      ),
    },
  },
  {
    id: "security",
    label: "Security Testing",
    icon: Shield,
    content: {
      title: "Security Testing",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Cognitest automatically runs security scans aligned with OWASP API Security Top 10. No extra configuration needed — security tests are included in every test generation.
          </p>

          <div className="space-y-3">
            {[
              { id: "API1", name: "Broken Object Level Authorization", desc: "Tests IDOR vulnerabilities by manipulating resource IDs across authenticated users." },
              { id: "API2", name: "Broken Authentication", desc: "Checks for weak passwords, missing auth on sensitive endpoints, token leaks, and session fixation." },
              { id: "API3", name: "Excessive Data Exposure", desc: "Validates that responses don't return more fields than documented or expected." },
              { id: "API4", name: "Lack of Resources & Rate Limiting", desc: "Tests pagination abuse, large payload handling, and missing rate limits." },
              { id: "API5", name: "Broken Function Level Authorization", desc: "Attempts admin-level operations with regular user tokens." },
              { id: "API6", name: "Mass Assignment", desc: "Sends extra fields (role, isAdmin) to detect unprotected property binding." },
              { id: "API7", name: "Security Misconfiguration", desc: "Checks CORS headers, verbose error messages, stack traces, and missing security headers." },
              { id: "API8", name: "Injection", desc: "SQL injection, NoSQL injection, command injection, and XSS via API parameters." },
            ].map((item) => (
              <div key={item.id} className="rounded-lg border border-border/60 bg-secondary/20 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="text-[10px] text-red-400 border-red-500/30 font-mono">{item.id}</Badge>
                  <h4 className="font-semibold text-foreground text-sm">{item.name}</h4>
                </div>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
            ))}
          </div>
        </>
      ),
    },
  },
  {
    id: "reporting",
    label: "Reporting",
    icon: FileBarChart2,
    content: {
      title: "Reports & Analytics",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Every test run generates comprehensive reports with everything you need for QA review and compliance audits.
          </p>

          <h3 className="mb-4 text-base font-semibold text-foreground">Report Contents</h3>
          <div className="grid gap-3 sm:grid-cols-2 mb-6">
            {[
              { title: "Pass/Fail Summary", desc: "Overall test counts, pass rate %, and trend over time." },
              { title: "Response Times", desc: "Per-endpoint latency distributions (p50, p95, p99)." },
              { title: "Coverage Metrics", desc: "Percentage of endpoints, methods, and response codes tested." },
              { title: "Security Findings", desc: "Vulnerabilities categorized by severity (Critical/High/Medium/Low)." },
              { title: "Test Details", desc: "Each test case with request, expected vs actual response, and assertion results." },
              { title: "Error Analysis", desc: "Grouped failures with root cause suggestions and remediation guidance." },
            ].map((item) => (
              <div key={item.title} className="rounded-lg border border-border/60 bg-secondary/20 p-4">
                <h4 className="font-semibold text-foreground text-sm mb-1">{item.title}</h4>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </div>
            ))}
          </div>

          <h3 className="mb-3 text-base font-semibold text-foreground">Export Formats</h3>
          <div className="flex flex-wrap gap-2 mb-6">
            {["PDF", "JSON", "CSV", "HTML", "JUnit XML"].map((f) => (
              <Badge key={f} variant="outline" className="text-xs">{f}</Badge>
            ))}
          </div>

          <p className="text-sm text-muted-foreground">
            Reports are retained for 90 days on the free tier and indefinitely on Pro/Enterprise plans. Set up webhook notifications to get alerted when a test run completes.
          </p>
        </>
      ),
    },
  },
  {
    id: "webhooks",
    label: "Webhooks",
    icon: Webhook,
    content: {
      title: "Webhook Notifications",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">
            Configure webhooks to receive real-time notifications when test runs complete, security vulnerabilities are found, or report thresholds are breached.
          </p>

          <div className="rounded-lg border border-border bg-muted/30 p-4 font-mono text-sm text-muted-foreground mb-6">
            <p className="text-xs text-foreground font-sans font-semibold mb-2">Webhook Payload Example</p>
            <pre className="whitespace-pre-wrap">{`{
  "event": "test_run.completed",
  "project": "my-api",
  "summary": {
    "total": 48,
    "passed": 45,
    "failed": 3,
    "passRate": 93.75,
    "securityIssues": 1
  },
  "reportUrl": "https://app.cognitest.io/reports/abc123",
  "timestamp": "2026-02-07T10:30:00Z"
}`}</pre>
          </div>

          <h3 className="mb-3 text-base font-semibold text-foreground">Supported Integrations</h3>
          <ul className="space-y-2">
            {["Slack (incoming webhook)", "Microsoft Teams", "Discord", "PagerDuty", "Custom HTTP endpoint"].map((text) => (
              <li key={text} className="flex items-center gap-3">
                <ChevronRight className="h-4 w-4 text-emerald-400 shrink-0" />
                <span className="text-sm text-muted-foreground">{text}</span>
              </li>
            ))}
          </ul>
        </>
      ),
    },
  },
  {
    id: "troubleshooting",
    label: "Troubleshooting",
    icon: AlertTriangle,
    content: {
      title: "Troubleshooting",
      body: (
        <>
          <p className="text-muted-foreground leading-relaxed mb-6">Common issues and their resolutions:</p>
          <div className="space-y-3">
            {[
              { q: "Tests fail with 401 Unauthorized", a: "Ensure your auth token is valid and not expired. For OAuth, check that the token endpoint and client credentials are correct. Try refreshing the token manually." },
              { q: "Slow test execution", a: "Reduce concurrent virtual users, increase your API server capacity, or exclude heavy endpoints from parallel execution. Consider testing against a staging environment." },
              { q: "Missing endpoints in test suite", a: "Verify your Swagger/OpenAPI spec includes all endpoints with proper schemas. Endpoints without defined responses may be skipped during generation." },
              { q: "Schema validation failures", a: "Your API response doesn't match the documented schema. Check for extra or missing fields, type mismatches, or nullable fields not marked as nullable." },
              { q: "Timeout errors", a: "Default timeout is 30 seconds. Increase it in Project → Settings → Advanced. Some endpoints (file uploads, heavy queries) may need longer timeouts." },
              { q: "CORS errors in browser preview", a: "CORS only affects browser requests. Cognitest runs tests server-side, so CORS shouldn't affect test execution. If running locally, ensure your API allows the Cognitest user-agent." },
            ].map((item) => (
              <div key={item.q} className="rounded-lg border border-border/60 bg-secondary/20 p-4">
                <h4 className="font-semibold text-foreground text-sm mb-1">{item.q}</h4>
                <p className="text-xs text-muted-foreground">{item.a}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-semibold text-emerald-400">Still stuck?</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Reach out to us via the <strong>Contact Us</strong> page or email <strong>support@cognitest.io</strong>. We typically respond within 4 hours during business hours.
            </p>
          </div>
        </>
      ),
    },
  },
]

const DocsPage = () => {
  const [searchParams] = useSearchParams()
  const [activeSection, setActiveSection] = useState<string>(() => {
    const param = searchParams.get("section")
    return param && sections.some((section) => section.id === param)
      ? param
      : "introduction"
  })

  useEffect(() => {
    const param = searchParams.get("section")
    if (param && sections.some((section) => section.id === param)) {
      setActiveSection(param)
    }
  }, [searchParams])

  const active = sections.find((section) => section.id === activeSection)
  const ActiveIcon = active?.icon

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      {/* Sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-border/50 bg-card/40 md:block">
        <div className="sticky top-16 p-5">
          <h3 className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            <Book className="h-3.5 w-3.5" /> Documentation
          </h3>
          <nav className="space-y-0.5">
            {sections.map((s) => {
              const Icon = s.icon
              return (
                <button
                  key={s.id}
                  onClick={() => setActiveSection(s.id)}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors cursor-pointer",
                    activeSection === s.id
                      ? "bg-emerald-500/10 text-emerald-400 font-medium"
                      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                  )}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  {s.label}
                </button>
              )
            })}
          </nav>
        </div>
      </aside>

      {/* Mobile nav */}
      <div className="block border-b border-border p-3 md:hidden fixed top-16 left-0 right-0 bg-background z-30">
        <select
          value={activeSection}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => setActiveSection(event.target.value)}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
        >
          {sections.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
      </div>

      {/* Content */}
      <div className="flex-1 px-6 py-10 md:px-12 lg:px-20 max-w-4xl">
        <div className="flex items-center gap-3 mb-8">
          {ActiveIcon && <ActiveIcon className="h-6 w-6 text-emerald-400" />}
          <h1 className="text-3xl font-bold tracking-tight text-foreground">{active?.content.title}</h1>
        </div>
        {active?.content.body}
      </div>
    </div>
  )
}

export default DocsPage
