# 1. Frontend Overview
This frontend is organized as a layered React app where routing and global state live at the top, and page-level business flows live in route pages and orchestration components. The design goal is to keep UI rendering simple while moving cross-cutting logic (auth, permissions, projects, runs) into reusable contexts and a centralized API client.

Beginner-friendly explanation: Think of the app like a mall. The building structure (routing + layouts) stays the same, while shops (pages) change as you walk. Shared services like security (auth) and information desk (contexts) sit at the center so every shop can use them.

Core entry files:
- [Cognitest-Frontend/index.html](Cognitest-Frontend/index.html)
- [Cognitest-Frontend/src/main.tsx](Cognitest-Frontend/src/main.tsx)
- [Cognitest-Frontend/src/App.tsx](Cognitest-Frontend/src/App.tsx)

Why this architecture exists:
- A single entry path prevents split boot sequences and makes the app predictable.
- Contexts centralize shared state to avoid duplicated fetch logic across pages.
- Routing and layouts are separated so navigation and chrome stay stable while pages swap.

# 2. Project Folder Structure
Folder boundaries map to responsibility boundaries:

Beginner-friendly explanation: Each folder is like a labeled drawer. If you know the drawer name, you know what is inside. That makes it easier to find the right file.

- [Cognitest-Frontend/src/pages](Cognitest-Frontend/src/pages): owns business flows and page-specific state.
  - If removed, routing renders nothing or fails to match routes.
- [Cognitest-Frontend/src/components](Cognitest-Frontend/src/components): reusable view components and layout scaffolding.
  - If removed, pages lose their UI building blocks.
- [Cognitest-Frontend/src/context](Cognitest-Frontend/src/context): global state and domain ownership (auth, permissions, projects, members, runs, theme).
  - If removed, core flows lose state, auth, and data fetching.
- [Cognitest-Frontend/src/services](Cognitest-Frontend/src/services): API communication and request conventions.
  - If removed, all backend calls break.
- [Cognitest-Frontend/src/config](Cognitest-Frontend/src/config): runtime and constants for environment/runtime correctness.
  - If removed, API base URLs and constants become hardcoded and fragile.
- [Cognitest-Frontend/src/lib](Cognitest-Frontend/src/lib): shared utilities and pure helpers.
  - If removed, common formatting, tokens, and helpers break.
- [Cognitest-Frontend/src/data](Cognitest-Frontend/src/data): mock or seed data used to render UI.
  - If removed, demo and placeholder lists lose data.
- [Cognitest-Frontend/src/components/ui](Cognitest-Frontend/src/components/ui): UI primitive wrappers.
  - If removed, most UI components will not render.

# 3. Frontend Startup Flow
The app boot sequence is explicit and predictable.

Beginner-friendly explanation: When you open the website, it first opens the front door (index.html), then plugs in the power (main.tsx), and finally turns on the full app (App.tsx).

Real execution flow:
```
index.html
  -> main.tsx
      -> creates React root
      -> renders App.tsx
          -> AppProviders mounts Theme, Auth, Permissions, Projects, Members, RunHistory
          -> BrowserRouter initializes
          -> routes resolve to PublicLayout or DashboardLayout
```

Why this flow exists:
- Providers run before pages, so pages can read global state immediately.
- The router is defined once, so auth and layout logic is centralized.

# 4. Routing System
Routing is intentionally split to separate public marketing flows from authenticated product flows.

Beginner-friendly explanation: Public routes are like the store lobby anyone can enter. Dashboard routes are like the employee-only area that needs a badge.

- [Cognitest-Frontend/src/routes/PublicRoutes.tsx](Cognitest-Frontend/src/routes/PublicRoutes.tsx)
  - Public pages and entry funnels (landing, login, signup, docs, pricing, contact).
- [Cognitest-Frontend/src/routes/DashboardRoutes.tsx](Cognitest-Frontend/src/routes/DashboardRoutes.tsx)
  - Authenticated product surfaces and super-admin surfaces.
- [Cognitest-Frontend/src/components/layout/PublicLayout.tsx](Cognitest-Frontend/src/components/layout/PublicLayout.tsx)
  - Owns public header + content area.
- [Cognitest-Frontend/src/components/layout/DashboardLayout.tsx](Cognitest-Frontend/src/components/layout/DashboardLayout.tsx)
  - Owns sidebar, header, breadcrumb, and API tester tray.
- [Cognitest-Frontend/src/components/layout/AdminRoute.tsx](Cognitest-Frontend/src/components/layout/AdminRoute.tsx)
  - Enforces tenant admin paths.
- [Cognitest-Frontend/src/components/layout/SuperAdminRoute.tsx](Cognitest-Frontend/src/components/layout/SuperAdminRoute.tsx)
  - Enforces system-level access.

Why split routing:
- Public routes do not need auth guards or dashboard chrome.
- Dashboard routes need persistent navigation, auth checks, and global data.

# 5. State Management Flow
State is split into global contexts for shared domains and local state for page-only UI.

Beginner-friendly explanation: Global state is like the building rules everyone follows (auth, current project). Local state is like a notepad each page keeps for its own small tasks.

Provider order (from [Cognitest-Frontend/src/context/AppProviders.tsx](Cognitest-Frontend/src/context/AppProviders.tsx)):
Theme -> Auth -> Permissions -> Projects -> Members -> RunHistory

Why this order:
- Theme is needed by all UI early.
- Auth must be ready before permissions and project data.
- Permissions depend on user identity from Auth.
- Projects and Members depend on workspace and user context.
- RunHistory depends on projects to scope runs.

Why contexts are separated:
- Each context owns a single domain and its cache, so updates are isolated.
- It avoids a single global store that grows unbounded.

Global vs local state:
- Global: auth token, user identity, selected workspace/project, permissions, run history.
- Local: tabs, modals, filters, UI selection state in pages.

State flow:
```
Page -> useContext() -> context method -> backendClient -> setContextState -> re-render
```

# 6. API & Backend Communication Flow
All backend calls go through [Cognitest-Frontend/src/services/backendClient.ts](Cognitest-Frontend/src/services/backendClient.ts).

Beginner-friendly explanation: Instead of every page making its own phone call to the server, the app uses one call center (backendClient). This keeps calls consistent and secure.

Why the services layer exists:
- One place to attach auth headers and timeouts.
- One place to encode API URLs and payload shapes.
- Pages and contexts do not need to know raw fetch logic.

Centralized API flow:
```
Page/Context
  -> backendClient.someFunction()
      -> request() helper
          -> attaches Authorization header if token exists
          -> fetches from runtime API base URL
          -> returns typed data or throws error
```

# 7. Authentication Flow
Auth is owned by [Cognitest-Frontend/src/context/AuthContext.tsx](Cognitest-Frontend/src/context/AuthContext.tsx).

Beginner-friendly explanation: Login is like getting a wristband at an event. Once you have it, you can enter the VIP areas (dashboard routes).

Why auth is global:
- The token is needed by every API request.
- Role checks are needed by routing and navigation.

Auth execution chain:
```
Login/Signup page
  -> AuthContext.loginUser/signupUser
      -> backendClient.loginUser/signupUser
          -> token + user returned
          -> AuthContext stores token and user in memory + localStorage
              -> DashboardLayout allows entry
```

# 8. Component Architecture
There are clear layers with distinct purposes:

Beginner-friendly explanation: Components are like Lego blocks. Layouts are big base plates, pages are medium blocks, and UI primitives are small bricks you reuse everywhere.

- Core architecture files: entry, routing, providers, layouts.
- Business logic files: contexts, backend client, project pages, RunSuiteModal.
- UI files: reusable component views and ShadCN wrappers.
- Utility files: helpers and constants.
- Orchestration files: layout shells and modal flows that connect UI and business actions.

Why layouts exist:
- Dashboards need a persistent sidebar and header.
- Public pages need a different chrome.
- Layouts prevent duplicated navigation code across pages.

# 9. Important Files Explained Individually
This section uses the required 10 questions for each important file. After each file, there is a beginner note that explains the same thing in simple words.

## Entry and Core Architecture

### [Cognitest-Frontend/index.html](Cognitest-Frontend/index.html)
1) Why it exists: Provides the single root and script entry for the SPA.
2) Responsibility: Host the root div and bootstrap script load.
3) Who calls it: The browser.
4) What it calls: Loads main.tsx bundle.
5) Data in: None (static HTML).
6) Data out: DOM root for React.
7) Business logic: None.
8) Why not elsewhere: HTML bootstrapping must be here for Vite.
9) What breaks if removed: App never renders.
10) Type: core architecture file.

Beginner note: This is the empty stage where the app will be placed. Without it, nothing can appear on screen.

### [Cognitest-Frontend/src/main.tsx](Cognitest-Frontend/src/main.tsx)
1) Why it exists: The JS entry point for React.
2) Responsibility: Create React root, render App, load global CSS.
3) Who calls it: index.html bundle.
4) What it calls: App.tsx and index.css.
5) Data in: None.
6) Data out: React tree mounted to DOM.
7) Business logic: None.
8) Why not elsewhere: Boot logic must be at entry to avoid double mounts.
9) What breaks if removed: App never mounts.
10) Type: core architecture file.

Beginner note: This is the power switch that turns the app on.

### [Cognitest-Frontend/src/App.tsx](Cognitest-Frontend/src/App.tsx)
1) Why it exists: Central router and provider wiring.
2) Responsibility: Wrap providers and routes.
3) Who calls it: main.tsx.
4) What it calls: AppProviders, BrowserRouter, PublicRoutes, DashboardRoutes.
5) Data in: None.
6) Data out: The root React tree with routing.
7) Business logic: App-level orchestration only.
8) Why not elsewhere: Central routing prevents duplicated provider stacks.
9) What breaks if removed: Routing and providers vanish.
10) Type: core architecture file.

Beginner note: This is the main control room that decides which page you see.

### [Cognitest-Frontend/src/context/AppProviders.tsx](Cognitest-Frontend/src/context/AppProviders.tsx)
1) Why it exists: Centralizes provider order.
2) Responsibility: Compose Theme, Auth, Permissions, Projects, Members, RunHistory.
3) Who calls it: App.tsx.
4) What it calls: ThemeProvider, AuthProvider, PermissionsProvider, ProjectProvider, MembersProvider, RunHistoryProvider.
5) Data in: Children React tree.
6) Data out: Context-enabled tree.
7) Business logic: Provider orchestration and dependency ordering.
8) Why not elsewhere: Order matters; separating risks mismatch.
9) What breaks if removed: All contexts are unavailable.
10) Type: core architecture file.

Beginner note: This stacks all the global tools so every page can use them.

### [Cognitest-Frontend/src/routes/PublicRoutes.tsx](Cognitest-Frontend/src/routes/PublicRoutes.tsx)
1) Why it exists: Defines public route-to-page mapping.
2) Responsibility: Map paths to public pages and layouts.
3) Who calls it: App.tsx routing tree.
4) What it calls: PublicLayout and public pages.
5) Data in: URL path from router.
6) Data out: Rendered public page.
7) Business logic: Navigation mapping only.
8) Why not elsewhere: Routing must be centralized for clarity.
9) What breaks if removed: Public pages unreachable.
10) Type: core architecture file.

Beginner note: This is the map for pages anyone can visit.

### [Cognitest-Frontend/src/routes/DashboardRoutes.tsx](Cognitest-Frontend/src/routes/DashboardRoutes.tsx)
1) Why it exists: Defines authenticated and super-admin routes.
2) Responsibility: Map dashboard URLs to pages and guards.
3) Who calls it: App.tsx routing tree.
4) What it calls: DashboardLayout, AdminRoute, SuperAdminRoute, pages.
5) Data in: URL path.
6) Data out: Rendered dashboard page.
7) Business logic: Auth-aware routing and page selection.
8) Why not elsewhere: Guards must sit in routing to block access early.
9) What breaks if removed: Dashboard routes fail.
10) Type: core architecture file.

Beginner note: This is the map for pages that need a logged-in user.

### [Cognitest-Frontend/src/components/layout/PublicLayout.tsx](Cognitest-Frontend/src/components/layout/PublicLayout.tsx)
1) Why it exists: Defines public chrome.
2) Responsibility: Optional PublicNavbar, content container, animated outlet.
3) Who calls it: PublicRoutes.
4) What it calls: PublicNavbar, AnimatedOutlet.
5) Data in: Router location.
6) Data out: Rendered public page body.
7) Business logic: Hides navbar for auth pages.
8) Why not elsewhere: Avoids repeating navbar logic in every page.
9) What breaks if removed: Public pages lose layout consistency.
10) Type: orchestration file.

Beginner note: This is the public page frame so every public page looks consistent.

### [Cognitest-Frontend/src/components/layout/DashboardLayout.tsx](Cognitest-Frontend/src/components/layout/DashboardLayout.tsx)
1) Why it exists: Defines dashboard shell and access gate.
2) Responsibility: Auth check, sidebar provider, header, breadcrumb, API tester tray.
3) Who calls it: DashboardRoutes.
4) What it calls: AppSidebar, AppHeader, DashboardBreadcrumb, MiniPostman, SidebarProvider.
5) Data in: Auth context user and routing outlet.
6) Data out: Dashboard UI with nested page.
7) Business logic: Redirects to login when no user.
8) Why not elsewhere: Access control must happen at layout for all dashboard pages.
9) What breaks if removed: Dashboard chrome and auth gating vanish.
10) Type: core architecture file.

Beginner note: This is the dashboard frame with the sidebar, header, and main content area.

### [Cognitest-Frontend/src/components/layout/AdminRoute.tsx](Cognitest-Frontend/src/components/layout/AdminRoute.tsx)
1) Why it exists: Tenant admin guard.
2) Responsibility: Block non-admin access to admin pages.
3) Who calls it: DashboardRoutes.
4) What it calls: Navigate redirect.
5) Data in: AuthContext isAdmin.
6) Data out: Children or redirect.
7) Business logic: Role enforcement.
8) Why not elsewhere: Routing guard is the earliest safe check.
9) What breaks if removed: Unauthorized users can access admin screens.
10) Type: core architecture file.

Beginner note: This is a bouncer that blocks non-admins.

### [Cognitest-Frontend/src/components/layout/SuperAdminRoute.tsx](Cognitest-Frontend/src/components/layout/SuperAdminRoute.tsx)
1) Why it exists: System-level guard.
2) Responsibility: Block non-super-admin access.
3) Who calls it: DashboardRoutes.
4) What it calls: Navigate redirect.
5) Data in: AuthContext user.systemRole.
6) Data out: Children or redirect.
7) Business logic: System role enforcement.
8) Why not elsewhere: Must block early for secure routing.
9) What breaks if removed: Super-admin surfaces become accessible to normal users.
10) Type: core architecture file.

Beginner note: This is a stricter bouncer for system admins only.

## Global State and Business Logic

### [Cognitest-Frontend/src/context/AuthContext.tsx](Cognitest-Frontend/src/context/AuthContext.tsx)
1) Why it exists: Central auth state and identity.
2) Responsibility: Store user, token, workspace/project selection, login/signup/verify/logout.
3) Who calls it: Login/Signup pages, AppHeader, layouts, guards.
4) What it calls: backendClient.loginUser, backendClient.signupUser, backendClient.verifyOtp, localStorage helpers.
5) Data in: Credentials, OTP, stored token.
6) Data out: User object, token, isAdmin flag, selected workspace/project.
7) Business logic: Session persistence, token parsing, role detection.
8) Why not elsewhere: Many components need shared auth state; prop drilling would be fragile.
9) What breaks if removed: Auth, guards, and API auth headers break.
10) Type: state management file.

Beginner note: This keeps track of who you are and whether you are logged in.

### [Cognitest-Frontend/src/context/PermissionsContext.tsx](Cognitest-Frontend/src/context/PermissionsContext.tsx)
1) Why it exists: Central permission logic.
2) Responsibility: Permission checks and role-based gating helpers.
3) Who calls it: Admin UI components, members/roles pages, route guards.
4) What it calls: AuthContext and backendClient as needed.
5) Data in: User roles and permission sets.
6) Data out: Boolean permission decisions.
7) Business logic: Role/permission interpretation.
8) Why not elsewhere: Keeps permission logic consistent across pages.
9) What breaks if removed: Permission checks become inconsistent.
10) Type: state management file.

Beginner note: This checks what actions your role is allowed to do.

### [Cognitest-Frontend/src/context/ProjectContext.tsx](Cognitest-Frontend/src/context/ProjectContext.tsx)
1) Why it exists: Central project list and selection.
2) Responsibility: Load projects, track active project.
3) Who calls it: DashboardPage, ProjectDetailPageNew, breadcrumbs.
4) What it calls: backendClient.getWorkspaceProjects and getProjectMeta.
5) Data in: Workspace ID and user context.
6) Data out: Projects list, active project state.
7) Business logic: Project loading and selection.
8) Why not elsewhere: Multiple pages rely on the same project data.
9) What breaks if removed: Project lists and selection disappear.
10) Type: state management file.

Beginner note: This keeps the list of projects so many pages can reuse it.

### [Cognitest-Frontend/src/context/MembersContext.tsx](Cognitest-Frontend/src/context/MembersContext.tsx)
1) Why it exists: Team member list is shared across pages.
2) Responsibility: Fetch and store members list for workspace/project.
3) Who calls it: Members pages, admin dialogs.
4) What it calls: backendClient member endpoints.
5) Data in: Workspace/project IDs.
6) Data out: Members list, loading state.
7) Business logic: Member loading and caching.
8) Why not elsewhere: Prevent duplicated member fetch logic.
9) What breaks if removed: Members pages lose data.
10) Type: state management file.

Beginner note: This stores the team members list so it does not reload everywhere.

### [Cognitest-Frontend/src/context/RunHistoryContext.tsx](Cognitest-Frontend/src/context/RunHistoryContext.tsx)
1) Why it exists: Run history is shared across project pages and reports.
2) Responsibility: Store run entries and allow refresh.
3) Who calls it: ProjectDetailPageNew, RunSuiteModal, reports tables.
4) What it calls: backendClient.getTestExecutions, getRunResults.
5) Data in: Project ID, run payloads.
6) Data out: Run history list and status.
7) Business logic: Run tracking across sessions.
8) Why not elsewhere: Multiple pages need the same run list.
9) What breaks if removed: Run results vanish or become inconsistent.
10) Type: state management file.

Beginner note: This stores test run history so reports stay consistent.

### [Cognitest-Frontend/src/context/ThemeContext.tsx](Cognitest-Frontend/src/context/ThemeContext.tsx)
1) Why it exists: Central theme handling.
2) Responsibility: Persist theme mode and provide toggles.
3) Who calls it: Theme toggles and layout components.
4) What it calls: localStorage, document class toggles.
5) Data in: Theme preference.
6) Data out: Theme mode and setter.
7) Business logic: Theme persistence.
8) Why not elsewhere: Consistent theme across all pages.
9) What breaks if removed: Theme toggles and dark mode fail.
10) Type: state management file.

Beginner note: This stores dark/light mode so it stays the same on all pages.

## Services and Config

### [Cognitest-Frontend/src/services/backendClient.ts](Cognitest-Frontend/src/services/backendClient.ts)
1) Why it exists: Single source for API calls and request policy.
2) Responsibility: Build requests, attach auth, parse responses, expose typed endpoints.
3) Who calls it: Contexts and pages across the app.
4) What it calls: fetch and config runtime.
5) Data in: Payloads for auth, projects, tests, runs, admin actions.
6) Data out: Parsed API responses (projects, test cases, runs, stats).
7) Business logic: Request timeout, auth header injection, endpoint mapping.
8) Why not elsewhere: Avoid duplicated fetch logic and inconsistent headers.
9) What breaks if removed: All backend communication breaks.
10) Type: business logic file.

Beginner note: This is the single place that talks to the backend server.

Key exports used in flows:
- loginUser, signupUser, verifyOtp
- getWorkspaceProjects, getProjectMeta
- uploadProjectSpec
- generateAISuite, generateTestCasesFromSpec
- executeBatch
- getTestExecutions, getCategoryStats, getRunResults

### [Cognitest-Frontend/src/config/runtime.ts](Cognitest-Frontend/src/config/runtime.ts)
1) Why it exists: Central API base URL resolution.
2) Responsibility: Expose runtime environment settings.
3) Who calls it: backendClient.
4) What it calls: environment variables.
5) Data in: Vite env values.
6) Data out: API base URL.
7) Business logic: Runtime config selection.
8) Why not elsewhere: Keep configuration in one place.
9) What breaks if removed: API calls lose base URL.
10) Type: utility/helper file.

Beginner note: This decides which server address the app should use.

### [Cognitest-Frontend/src/config/constants.ts](Cognitest-Frontend/src/config/constants.ts)
1) Why it exists: Central constants used across UI.
2) Responsibility: Store static values for labels or defaults.
3) Who calls it: Pages and components.
4) What it calls: None.
5) Data in: None.
6) Data out: Constants.
7) Business logic: None.
8) Why not elsewhere: Avoid scattering hardcoded values.
9) What breaks if removed: UI defaults and labels break.
10) Type: utility/helper file.

Beginner note: This is a box of fixed values used across the UI.

### [Cognitest-Frontend/src/config/testCategories.ts](Cognitest-Frontend/src/config/testCategories.ts)
1) Why it exists: Central test category definitions.
2) Responsibility: Provide category labels and metadata.
3) Who calls it: Project and report pages.
4) What it calls: None.
5) Data in: None.
6) Data out: Category list.
7) Business logic: Category configuration.
8) Why not elsewhere: Shared category mapping must be consistent.
9) What breaks if removed: Category labels and filters break.
10) Type: utility/helper file.

Beginner note: This is the official list of test categories used in the UI.

### [Cognitest-Frontend/src/config/index.ts](Cognitest-Frontend/src/config/index.ts)
1) Why it exists: Re-export config for clean imports.
2) Responsibility: Provide a single import point for config.
3) Who calls it: Pages and services.
4) What it calls: runtime/constants/testCategories.
5) Data in: None.
6) Data out: Config exports.
7) Business logic: None.
8) Why not elsewhere: Cleaner imports.
9) What breaks if removed: Imports become noisy or broken.
10) Type: utility/helper file.

Beginner note: This file is a shortcut to import all config in one line.

## Layout and Navigation

### [Cognitest-Frontend/src/components/layout/AppSidebar.tsx](Cognitest-Frontend/src/components/layout/AppSidebar.tsx)
1) Why it exists: Central dashboard navigation UI.
2) Responsibility: Render nav groups and admin-only links.
3) Who calls it: DashboardLayout.
4) What it calls: Sidebar UI primitives, AuthContext.
5) Data in: Current location, isAdmin.
6) Data out: Navigation events.
7) Business logic: Hide admin links for non-admins.
8) Why not elsewhere: Navigation must be consistent across dashboard pages.
9) What breaks if removed: Dashboard navigation disappears.
10) Type: orchestration file.

Beginner note: This draws the left menu that lets you move between pages.

### [Cognitest-Frontend/src/components/layout/AppHeader.tsx](Cognitest-Frontend/src/components/layout/AppHeader.tsx)
1) Why it exists: Dashboard top bar with user menu.
2) Responsibility: Display current section title, org label, user menu, logout.
3) Who calls it: DashboardLayout.
4) What it calls: AuthContext, SidebarTrigger, DropdownMenu.
5) Data in: Location, user, workspace.
6) Data out: Navigation actions and logout.
7) Business logic: Title mapping from path.
8) Why not elsewhere: Prevents repeating header logic in each page.
9) What breaks if removed: Header and profile actions vanish.
10) Type: orchestration file.

Beginner note: This draws the top bar with your user menu and page title.

### [Cognitest-Frontend/src/components/layout/DashboardBreadcrumb.tsx](Cognitest-Frontend/src/components/layout/DashboardBreadcrumb.tsx)
1) Why it exists: Breadcrumb trail and project name resolution.
2) Responsibility: Render breadcrumbs and fetch project name by ID.
3) Who calls it: DashboardLayout.
4) What it calls: backendClient.getProjectMeta and Breadcrumb UI.
5) Data in: Location path and query params.
6) Data out: Breadcrumb UI and optional project name.
7) Business logic: Segment normalization and ID detection.
8) Why not elsewhere: Breadcrumbs are shared across dashboard pages.
9) What breaks if removed: Breadcrumb navigation and project labels vanish.
10) Type: orchestration file.

Beginner note: This shows where you are in the app, like a trail.

### [Cognitest-Frontend/src/components/layout/PublicNavbar.tsx](Cognitest-Frontend/src/components/layout/PublicNavbar.tsx)
1) Why it exists: Public navbar wiring to landing Navbar.
2) Responsibility: Provide nav links and current path to Navbar.
3) Who calls it: PublicLayout.
4) What it calls: Navbar component.
5) Data in: Location path.
6) Data out: Navbar UI.
7) Business logic: None.
8) Why not elsewhere: Keeps public layout clean.
9) What breaks if removed: Public navbar disappears.
10) Type: UI file.

Beginner note: This is the simple top menu for public pages.

### [Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminLayout.tsx](Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminLayout.tsx)
1) Why it exists: Super-admin shell and data preload.
2) Responsibility: Load stats and tenants, render admin sidebar/header, provide outlet context.
3) Who calls it: DashboardRoutes under SuperAdminRoute.
4) What it calls: backendClient.getSuperAdminStats, getSuperAdminTenants, Outlet.
5) Data in: Auth user and route path.
6) Data out: Outlet context with stats/tenants/loading.
7) Business logic: Fetch shared super-admin data and manage refresh.
8) Why not elsewhere: Super-admin pages share the same dataset.
9) What breaks if removed: Super-admin navigation and data flow break.
10) Type: orchestration file.

Beginner note: This is the special frame for system admins only.

## Orchestration Components

### [Cognitest-Frontend/src/components/RunSuiteModal.tsx](Cognitest-Frontend/src/components/RunSuiteModal.tsx)
1) Why it exists: Dedicated run execution flow UI and logic.
2) Responsibility: Configure runs, start execution, stream results, show progress.
3) Who calls it: ProjectDetailPageNew.
4) What it calls: backendClient.executeBatch, getRunResults, analyze failure helper.
5) Data in: Selected test cases, base URL, auth config.
6) Data out: Run progress, console logs, results state.
7) Business logic: Orchestrates execution lifecycle and result aggregation.
8) Why not elsewhere: Execution flow spans multiple UI states and needs isolation.
9) What breaks if removed: Run suite functionality disappears.
10) Type: orchestration file.

Beginner note: This is the control panel that runs tests and shows progress.

### [Cognitest-Frontend/src/components/api-tester/MiniPostman.tsx](Cognitest-Frontend/src/components/api-tester/MiniPostman.tsx)
1) Why it exists: In-app API testing utility.
2) Responsibility: Build ad-hoc requests, send, render response and history.
3) Who calls it: DashboardLayout.
4) What it calls: fetch directly.
5) Data in: URL, method, headers, params, body.
6) Data out: Response body, headers, status.
7) Business logic: Request building, response formatting, local history.
8) Why not elsewhere: Not tied to any single page; reusable tool.
9) What breaks if removed: API tester tray disappears.
10) Type: utility/helper file.

Beginner note: This is a small built-in tool to send test requests.

### [Cognitest-Frontend/src/components/motion/AnimatedOutlet.tsx](Cognitest-Frontend/src/components/motion/AnimatedOutlet.tsx)
1) Why it exists: Route transition animation without double renders.
2) Responsibility: Wraps router outlet in animated container and frozen router.
3) Who calls it: PublicLayout.
4) What it calls: React Router contexts, framer-motion.
5) Data in: Current location and outlet.
6) Data out: Animated page rendering.
7) Business logic: Prevents flicker during route transitions.
8) Why not elsewhere: Animation must wrap router outlet.
9) What breaks if removed: Public page transitions revert to default.
10) Type: UI file.

Beginner note: This makes page changes look smooth instead of sudden.

## Page-Level Business Logic Files

### [Cognitest-Frontend/src/pages/dashboard/DashboardPage.tsx](Cognitest-Frontend/src/pages/dashboard/DashboardPage.tsx)
1) Why it exists: Main dashboard summary and project list.
2) Responsibility: Render summary stats and active projects list.
3) Who calls it: DashboardRoutes.
4) What it calls: ProjectContext, backendClient for stats, DataTable UI.
5) Data in: Workspace and project data.
6) Data out: Dashboard UI and navigation actions.
7) Business logic: Aggregation for display and project navigation.
8) Why not elsewhere: This is the dashboard route surface.
9) What breaks if removed: The main dashboard page disappears.
10) Type: business logic file.

Beginner note: This is the home screen inside the dashboard.

### [Cognitest-Frontend/src/pages/dashboard/projects/ProjectDetailPageNew.tsx](Cognitest-Frontend/src/pages/dashboard/projects/ProjectDetailPageNew.tsx)
1) Why it exists: Central project workflow screen.
2) Responsibility: Show project metadata, specs, test categories, test cases, execution, and reports.
3) Who calls it: DashboardRoutes with project ID.
4) What it calls: backendClient project/test endpoints, RunSuiteModal, context hooks.
5) Data in: Project ID, category filters, run state.
6) Data out: UI state for tests, generation, execution results.
7) Business logic: Coordinates test generation, spec upload, and execution UI.
8) Why not elsewhere: It is the core product workflow page.
9) What breaks if removed: Core test workflow becomes unreachable.
10) Type: business logic file.

Beginner note: This is the main project screen where most work happens.

### [Cognitest-Frontend/src/pages/dashboard/projects/NewProjectPage.tsx](Cognitest-Frontend/src/pages/dashboard/projects/NewProjectPage.tsx)
1) Why it exists: Project creation flow.
2) Responsibility: Capture project details and call creation endpoint.
3) Who calls it: DashboardRoutes.
4) What it calls: backendClient project creation endpoints.
5) Data in: Form fields.
6) Data out: Created project and navigation to detail page.
7) Business logic: Form validation and creation action.
8) Why not elsewhere: Project creation is a separate workflow.
9) What breaks if removed: Users cannot create projects.
10) Type: business logic file.

Beginner note: This is the form that creates a new project.

### [Cognitest-Frontend/src/pages/dashboard/projects/ProjectTestExecutionPage.tsx](Cognitest-Frontend/src/pages/dashboard/projects/ProjectTestExecutionPage.tsx)
1) Why it exists: Dedicated execution view or deep link for runs.
2) Responsibility: Render run execution list and results.
3) Who calls it: DashboardRoutes.
4) What it calls: backendClient run endpoints and shared components.
5) Data in: Project ID.
6) Data out: Execution history UI.
7) Business logic: Run history display and filtering.
8) Why not elsewhere: Keeps execution UI separate from project detail tabs.
9) What breaks if removed: Direct execution page unavailable.
10) Type: business logic file.

Beginner note: This page focuses on showing test runs and results.

### [Cognitest-Frontend/src/pages/dashboard/members/MembersPage.tsx](Cognitest-Frontend/src/pages/dashboard/members/MembersPage.tsx)
1) Why it exists: Members list and management.
2) Responsibility: Display members list, filters, and actions.
3) Who calls it: DashboardRoutes.
4) What it calls: MembersContext and backendClient member actions.
5) Data in: Workspace or project member data.
6) Data out: Members table and action events.
7) Business logic: Admin management of member access.
8) Why not elsewhere: This is the members management surface.
9) What breaks if removed: Member management UI gone.
10) Type: business logic file.

Beginner note: This page lists team members and lets admins manage them.

### [Cognitest-Frontend/src/pages/dashboard/members/CreateMemberPage.tsx](Cognitest-Frontend/src/pages/dashboard/members/CreateMemberPage.tsx)
1) Why it exists: Member creation flow.
2) Responsibility: Capture user info and invite/create.
3) Who calls it: MembersPage navigation.
4) What it calls: backendClient create member endpoint.
5) Data in: Form fields.
6) Data out: New member and navigation.
7) Business logic: Form submission and error handling.
8) Why not elsewhere: Separate workflow from member list.
9) What breaks if removed: Cannot create members.
10) Type: business logic file.

Beginner note: This form adds a new person to the team.

### [Cognitest-Frontend/src/pages/dashboard/members/EditUserAccessPage.tsx](Cognitest-Frontend/src/pages/dashboard/members/EditUserAccessPage.tsx)
1) Why it exists: Edit access/roles for a user.
2) Responsibility: Update role and permissions for a member.
3) Who calls it: MembersPage actions.
4) What it calls: backendClient role update endpoints.
5) Data in: Member ID and role settings.
6) Data out: Updated member state.
7) Business logic: Permission updates and save flow.
8) Why not elsewhere: Role editing is a focused flow.
9) What breaks if removed: Admins cannot edit member access.
10) Type: business logic file.

Beginner note: This page changes what a member is allowed to do.

### [Cognitest-Frontend/src/pages/dashboard/roles/RolesPage.tsx](Cognitest-Frontend/src/pages/dashboard/roles/RolesPage.tsx)
1) Why it exists: Role and permission management UI.
2) Responsibility: Display roles, permissions, and assignment.
3) Who calls it: DashboardRoutes.
4) What it calls: backendClient role and permission endpoints.
5) Data in: Roles and permission sets.
6) Data out: Role table and updates.
7) Business logic: Role updates and permission mapping.
8) Why not elsewhere: Dedicated admin function.
9) What breaks if removed: Role management disappears.
10) Type: business logic file.

Beginner note: This page manages roles and permissions.

### [Cognitest-Frontend/src/pages/dashboard/account/ProfilePage.tsx](Cognitest-Frontend/src/pages/dashboard/account/ProfilePage.tsx)
1) Why it exists: User profile editing.
2) Responsibility: Display and update personal profile data.
3) Who calls it: DashboardRoutes and AppHeader menu.
4) What it calls: backendClient profile endpoints.
5) Data in: User profile form.
6) Data out: Updated profile state.
7) Business logic: Form validation and profile update.
8) Why not elsewhere: Account settings are isolated from project workflows.
9) What breaks if removed: Users cannot edit profile.
10) Type: business logic file.

Beginner note: This page edits your personal profile details.

### [Cognitest-Frontend/src/pages/dashboard/account/SettingsPage.tsx](Cognitest-Frontend/src/pages/dashboard/account/SettingsPage.tsx)
1) Why it exists: Workspace or account settings surface.
2) Responsibility: Show settings toggles and preferences.
3) Who calls it: DashboardRoutes.
4) What it calls: backendClient settings endpoints.
5) Data in: Settings values.
6) Data out: Updated settings.
7) Business logic: Settings persistence.
8) Why not elsewhere: Keeps admin settings isolated.
9) What breaks if removed: Settings page gone.
10) Type: business logic file.

Beginner note: This page changes workspace or account settings.

### [Cognitest-Frontend/src/pages/dashboard/account/PlansPage.tsx](Cognitest-Frontend/src/pages/dashboard/account/PlansPage.tsx)
1) Why it exists: Subscription management UI.
2) Responsibility: Show plan details and CTA.
3) Who calls it: DashboardRoutes.
4) What it calls: backendClient billing endpoints when applicable.
5) Data in: Plan data.
6) Data out: UI state and plan actions.
7) Business logic: Plan selection flow.
8) Why not elsewhere: Billing is isolated from project workflows.
9) What breaks if removed: Users cannot manage plans.
10) Type: business logic file.

Beginner note: This page shows subscription plans and actions.

### [Cognitest-Frontend/src/pages/dashboard/account/SupportPage.tsx](Cognitest-Frontend/src/pages/dashboard/account/SupportPage.tsx)
1) Why it exists: Support contact UI.
2) Responsibility: Display support form and help links.
3) Who calls it: DashboardRoutes.
4) What it calls: backendClient support endpoints if any.
5) Data in: Support form input.
6) Data out: Support request submission.
7) Business logic: Form submission flow.
8) Why not elsewhere: Support is a dedicated surface.
9) What breaks if removed: Support access is lost.
10) Type: business logic file.

Beginner note: This page lets users contact support.

### [Cognitest-Frontend/src/pages/public/LoginPage.tsx](Cognitest-Frontend/src/pages/public/LoginPage.tsx)
1) Why it exists: User login entry.
2) Responsibility: Collect credentials and trigger login.
3) Who calls it: PublicRoutes.
4) What it calls: AuthContext.loginUser.
5) Data in: Email and passcode.
6) Data out: Navigation to dashboard on success.
7) Business logic: Form handling and error feedback.
8) Why not elsewhere: Public access surface.
9) What breaks if removed: Users cannot log in.
10) Type: business logic file.

Beginner note: This is the sign-in page.

### [Cognitest-Frontend/src/pages/public/SignupPage.tsx](Cognitest-Frontend/src/pages/public/SignupPage.tsx)
1) Why it exists: User signup entry.
2) Responsibility: Collect user details and trigger signup.
3) Who calls it: PublicRoutes.
4) What it calls: AuthContext.signupUser.
5) Data in: User profile and company data.
6) Data out: Navigation to OTP verification.
7) Business logic: Form validation and submit.
8) Why not elsewhere: Public access surface.
9) What breaks if removed: New users cannot sign up.
10) Type: business logic file.

Beginner note: This is the sign-up page for new users.

### [Cognitest-Frontend/src/pages/public/VerifyOtpPage.tsx](Cognitest-Frontend/src/pages/public/VerifyOtpPage.tsx)
1) Why it exists: OTP verification step.
2) Responsibility: Verify OTP and finalize signup.
3) Who calls it: PublicRoutes after signup flow.
4) What it calls: AuthContext.verifyOtp.
5) Data in: OTP code.
6) Data out: Authenticated session and navigation.
7) Business logic: OTP verification flow.
8) Why not elsewhere: OTP is a dedicated step.
9) What breaks if removed: Signups cannot be verified.
10) Type: business logic file.

Beginner note: This page confirms your code so signup is complete.

### [Cognitest-Frontend/src/pages/public/LandingPage.tsx](Cognitest-Frontend/src/pages/public/LandingPage.tsx)
1) Why it exists: Marketing homepage.
2) Responsibility: Render hero, feature sections, CTA.
3) Who calls it: PublicRoutes.
4) What it calls: Landing components (HeroSection, TrustSection, etc.).
5) Data in: None.
6) Data out: Marketing UI.
7) Business logic: None.
8) Why not elsewhere: Keeps marketing separate from product app.
9) What breaks if removed: Home page is blank.
10) Type: UI file.

Beginner note: This is the public marketing home page.

### [Cognitest-Frontend/src/pages/public/DocsPage.tsx](Cognitest-Frontend/src/pages/public/DocsPage.tsx)
1) Why it exists: Documentation and onboarding UI.
2) Responsibility: Show docs and usage guidance.
3) Who calls it: PublicRoutes.
4) What it calls: UI components and code snippets.
5) Data in: None.
6) Data out: Docs UI.
7) Business logic: None.
8) Why not elsewhere: Public docs should not be tied to dashboard.
9) What breaks if removed: Docs route is empty.
10) Type: UI file.

Beginner note: This page shows docs and help info.

### [Cognitest-Frontend/src/pages/public/PricingPage.tsx](Cognitest-Frontend/src/pages/public/PricingPage.tsx)
1) Why it exists: Pricing and plan comparison.
2) Responsibility: Present pricing tiers and CTA.
3) Who calls it: PublicRoutes.
4) What it calls: UI components.
5) Data in: None.
6) Data out: Pricing UI.
7) Business logic: None.
8) Why not elsewhere: Marketing content only.
9) What breaks if removed: Pricing route is empty.
10) Type: UI file.

Beginner note: This page shows pricing options.

### [Cognitest-Frontend/src/pages/public/ContactPage.tsx](Cognitest-Frontend/src/pages/public/ContactPage.tsx)
1) Why it exists: Contact form for sales/support.
2) Responsibility: Provide a contact UI.
3) Who calls it: PublicRoutes.
4) What it calls: UI components.
5) Data in: Contact form entries.
6) Data out: Contact submission.
7) Business logic: Simple form handling.
8) Why not elsewhere: Public contact should not be gated.
9) What breaks if removed: Contact route is empty.
10) Type: UI file.

Beginner note: This page lets visitors contact the team.

## Super-Admin Business Files

### [Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminDashboard.tsx](Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminDashboard.tsx)
1) Why it exists: Super-admin overview analytics.
2) Responsibility: Render stats and charts for tenants and users.
3) Who calls it: SuperAdminLayout outlet.
4) What it calls: StatCard, charts, uses layout context data.
5) Data in: stats and tenants from outlet context.
6) Data out: Dashboard UI.
7) Business logic: Aggregation of tenant stats for charts.
8) Why not elsewhere: Super-admin overview is isolated.
9) What breaks if removed: Super-admin dashboard view gone.
10) Type: business logic file.

Beginner note: This is the admin overview page with summary charts.

### [Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminTenants.tsx](Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminTenants.tsx)
1) Why it exists: Tenant CRUD and management.
2) Responsibility: Filter, create, edit, suspend, delete tenants.
3) Who calls it: SuperAdminLayout outlet.
4) What it calls: backendClient create/update/delete tenant endpoints.
5) Data in: tenant list and form input.
6) Data out: Updated tenant list and UI state.
7) Business logic: Tenant lifecycle actions.
8) Why not elsewhere: Super-admin only workflow.
9) What breaks if removed: Tenant management gone.
10) Type: business logic file.

Beginner note: This page manages tenant companies.

### [Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminUsersRoles.tsx](Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminUsersRoles.tsx)
1) Why it exists: Cross-tenant user management.
2) Responsibility: Flatten tenant users and allow status changes.
3) Who calls it: SuperAdminLayout outlet.
4) What it calls: backendClient.updateSuperAdminUserStatus.
5) Data in: tenants list.
6) Data out: Filtered user list and status updates.
7) Business logic: User status control across tenants.
8) Why not elsewhere: Super-admin only view.
9) What breaks if removed: Super-admin user management gone.
10) Type: business logic file.

Beginner note: This page manages users across tenants.

### [Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminBilling.tsx](Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminBilling.tsx)
1) Why it exists: Billing analytics.
2) Responsibility: Compute revenue and render charts.
3) Who calls it: SuperAdminLayout outlet.
4) What it calls: Chart components.
5) Data in: tenants list.
6) Data out: Billing UI.
7) Business logic: Revenue estimation and churn calculations.
8) Why not elsewhere: Super-admin overview area.
9) What breaks if removed: Billing analytics disappear.
10) Type: business logic file.

Beginner note: This page shows billing and revenue insights.

### [Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminTestSystem.tsx](Cognitest-Frontend/src/pages/super-admin-dashboard/SuperAdminTestSystem.tsx)
1) Why it exists: System-level test analytics.
2) Responsibility: Compute coverage and render stats.
3) Who calls it: SuperAdminLayout outlet.
4) What it calls: Chart components.
5) Data in: stats and tenants.
6) Data out: Test system UI.
7) Business logic: Aggregated test metrics.
8) Why not elsewhere: Super-admin view only.
9) What breaks if removed: Test system view gone.
10) Type: business logic file.

Beginner note: This page shows overall test system metrics.

### [Cognitest-Frontend/src/pages/super-admin-dashboard/InfrastructurePage.tsx](Cognitest-Frontend/src/pages/super-admin-dashboard/InfrastructurePage.tsx)
1) Why it exists: Infra usage overview.
2) Responsibility: Render storage and infra metrics.
3) Who calls it: SuperAdminLayout outlet.
4) What it calls: Chart UI.
5) Data in: static or derived metrics.
6) Data out: Infrastructure UI.
7) Business logic: Metric formatting.
8) Why not elsewhere: Super-admin view only.
9) What breaks if removed: Infra view gone.
10) Type: business logic file.

Beginner note: This page shows infrastructure metrics.

## Shared and Utility Files

### [Cognitest-Frontend/src/lib/utils.ts](Cognitest-Frontend/src/lib/utils.ts)
1) Why it exists: Shared helpers (classnames and formatting).
2) Responsibility: Utility functions used across UI.
3) Who calls it: UI components and pages.
4) What it calls: None.
5) Data in: Various values.
6) Data out: Formatted output.
7) Business logic: None (pure utilities).
8) Why not elsewhere: Avoid repeating helper logic.
9) What breaks if removed: Many components fail to format correctly.
10) Type: utility/helper file.

Beginner note: This file is a toolbox of small helper functions.

### [Cognitest-Frontend/src/lib/runHistory.ts](Cognitest-Frontend/src/lib/runHistory.ts)
1) Why it exists: Run history helpers.
2) Responsibility: Format or derive run history details.
3) Who calls it: Run history views and contexts.
4) What it calls: None.
5) Data in: Run entries.
6) Data out: Derived run data.
7) Business logic: Run formatting utilities.
8) Why not elsewhere: Keep run helpers reusable.
9) What breaks if removed: Run display logic breaks.
10) Type: utility/helper file.

Beginner note: This file helps format run history so it looks clean.

### [Cognitest-Frontend/src/lib/design-tokens.ts](Cognitest-Frontend/src/lib/design-tokens.ts)
1) Why it exists: Shared design constants.
2) Responsibility: Central token definitions.
3) Who calls it: UI components.
4) What it calls: None.
5) Data in: None.
6) Data out: Tokens.
7) Business logic: None.
8) Why not elsewhere: Tokens must be centralized.
9) What breaks if removed: Visual consistency breaks.
10) Type: utility/helper file.

Beginner note: This file stores shared design values like spacing or colors.

### [Cognitest-Frontend/src/data/runHistorySeed.ts](Cognitest-Frontend/src/data/runHistorySeed.ts)
1) Why it exists: Seed data for UI.
2) Responsibility: Provide mock run history.
3) Who calls it: Run history UI.
4) What it calls: None.
5) Data in: None.
6) Data out: Seed list.
7) Business logic: None.
8) Why not elsewhere: Seed data should be isolated.
9) What breaks if removed: Demo lists empty.
10) Type: utility/helper file.

Beginner note: This is example data used for demos or placeholders.

### [Cognitest-Frontend/src/data/reports.ts](Cognitest-Frontend/src/data/reports.ts)
1) Why it exists: Seed report data.
2) Responsibility: Provide report items.
3) Who calls it: Reports UI.
4) What it calls: None.
5) Data in: None.
6) Data out: Report list.
7) Business logic: None.
8) Why not elsewhere: Keeps mock data separate.
9) What breaks if removed: Report samples empty.
10) Type: utility/helper file.

Beginner note: This is example data for report screens.

## UI Wrapper Files (Representative)

The UI primitives wrap Radix and apply consistent styles. They are UI-only files; removing them breaks UI composition but not business logic.

### [Cognitest-Frontend/src/components/ui/button.tsx](Cognitest-Frontend/src/components/ui/button.tsx)
1) Why it exists: Unified button styling and variants.
2) Responsibility: Render a styled button wrapper.
3) Who calls it: All pages/components with buttons.
4) What it calls: None.
5) Data in: props and variant.
6) Data out: Button element.
7) Business logic: None.
8) Why not elsewhere: Avoid repeated button styles.
9) What breaks if removed: Buttons break across the UI.
10) Type: UI file.

Beginner note: This is the basic button everyone uses.

### [Cognitest-Frontend/src/components/ui/card.tsx](Cognitest-Frontend/src/components/ui/card.tsx)
1) Why it exists: Shared card layout.
2) Responsibility: Card wrapper elements.
3) Who calls it: Most pages with cards.
4) What it calls: None.
5) Data in: children props.
6) Data out: Styled divs.
7) Business logic: None.
8) Why not elsewhere: Consistent card styling.
9) What breaks if removed: Card layout fails.
10) Type: UI file.

Beginner note: This draws a bordered box used across the UI.

### [Cognitest-Frontend/src/components/ui/table.tsx](Cognitest-Frontend/src/components/ui/table.tsx)
1) Why it exists: Shared table wrapper and styles.
2) Responsibility: Table primitives.
3) Who calls it: DataTable and list pages.
4) What it calls: None.
5) Data in: children props.
6) Data out: Table layout.
7) Business logic: None.
8) Why not elsewhere: Consistency across tables.
9) What breaks if removed: Table lists break.
10) Type: UI file.

Beginner note: This draws consistent tables everywhere.

### [Cognitest-Frontend/src/components/ui/dialog.tsx](Cognitest-Frontend/src/components/ui/dialog.tsx)
1) Why it exists: Shared dialog modal infrastructure.
2) Responsibility: Wrap Radix dialog with styles.
3) Who calls it: Modals like tenant create/edit, confirmation dialogs.
4) What it calls: Radix dialog primitives.
5) Data in: open state and content.
6) Data out: Dialog UI.
7) Business logic: None.
8) Why not elsewhere: Avoid duplicating modal styles.
9) What breaks if removed: Dialogs fail to render.
10) Type: UI file.

Beginner note: This is the pop-up modal system.

### [Cognitest-Frontend/src/components/ui/sidebar.tsx](Cognitest-Frontend/src/components/ui/sidebar.tsx)
1) Why it exists: Sidebar container and state handling.
2) Responsibility: Provide sidebar open/collapse and mobile behavior.
3) Who calls it: AppSidebar and DashboardLayout.
4) What it calls: Button primitives.
5) Data in: open state.
6) Data out: Sidebar UI state.
7) Business logic: Mobile and collapsed behavior.
8) Why not elsewhere: Centralizes sidebar behavior.
9) What breaks if removed: Sidebar and triggers break.
10) Type: UI file.

Beginner note: This controls the sidebar open/close behavior.

# 10. Full Business Logic Flow
This section traces the real internal chains for critical flows.

Beginner-friendly explanation: These are step-by-step stories of what the app does when you click a button, like a recipe.

## Login
```
User opens /login
  -> LoginPage renders form
  -> user clicks submit
      -> AuthContext.loginUser
          -> backendClient.loginUser
              -> request() adds auth header (skipAuth true here)
              -> response returns user + token
          -> AuthContext stores token and user in localStorage
          -> AppHeader and DashboardLayout re-render with user
          -> navigate to /dashboard
```

## Signup
```
User opens /signup
  -> SignupPage renders form
  -> submit
      -> AuthContext.signupUser
          -> backendClient.signupUser
              -> request() with extended timeout
              -> response returns signup state
          -> navigate to /verify-otp
```

## OTP Verification
```
User opens /verify-otp
  -> VerifyOtpPage collects code
  -> AuthContext.verifyOtp
      -> backendClient.verifyOtp
          -> session created
      -> AuthContext stores token + user
      -> navigate to /dashboard
```

## Project Loading (Dashboard)
```
DashboardLayout mounts
  -> ProjectContext loads workspace projects
      -> backendClient.getWorkspaceProjects
          -> request() with auth header
      -> ProjectContext sets projects list
  -> DashboardPage renders stats + table
```

## Spec Upload (Project Detail)
```
User opens ProjectDetailPageNew
  -> selects spec file
  -> upload action triggers
      -> backendClient.uploadProjectSpec
          -> request() with FormData
      -> ProjectDetailPageNew updates spec info
      -> UI refreshes category stats and test list
```

## Test Generation
```
User clicks Generate Tests
  -> ProjectDetailPageNew handler
      -> backendClient.generateAISuite (or generateTestCasesFromSpec)
      -> loading state set in page
      -> test cases list updated
      -> UI re-renders test cases table
```

## Run Execution
```
User clicks Run Suite
  -> RunSuiteModal opens
  -> user confirms run
      -> RunSuiteModal executes backendClient.executeBatch
      -> progress and console stream updates local modal state
      -> RunHistoryContext refreshes via getTestExecutions/getRunResults
      -> ProjectDetailPageNew re-renders results tab
```

## Report Loading
```
User opens Test Results tab
  -> ProjectDetailPageNew triggers report fetch
      -> backendClient.getTestExecutions and getCategoryStats
      -> local state updated
      -> results table re-renders
```

## Navigation
```
User clicks sidebar item
  -> AppSidebar NavLink updates route
  -> Router renders new page in DashboardLayout outlet
  -> DashboardBreadcrumb updates path and project name
```

## Protected Route Checks
```
Route match occurs
  -> AdminRoute or SuperAdminRoute renders
      -> checks AuthContext isAdmin or systemRole
      -> if unauthorized, Navigate to /dashboard
      -> if authorized, render page
```

# 11. Dependency & Import Flow
Dependency chain in practice:

Beginner-friendly explanation: Think of this as a tree. The trunk is the entry file, branches are routes/layouts, and leaves are pages and UI components.
```
index.html
  -> main.tsx
      -> App.tsx
          -> AppProviders
              -> Contexts (Auth -> Permissions -> Projects -> Members -> RunHistory)
          -> Routes
              -> Layouts
                  -> Pages
                      -> Shared UI + UI primitives
                          -> backendClient + config + lib utils
```

Why dependencies flow downward:
- Core files must not depend on pages to avoid cycles.
- Contexts depend on services, not on UI, so they are reusable.
- Pages depend on contexts and services for business logic.

# 12. Rendering Lifecycle
Rendering is driven by state and routing:

Beginner-friendly explanation: When data changes, React redraws only the parts of the screen that need to update.

```
Initial render
  -> Providers initialize state
  -> Router resolves route
  -> Layout renders
  -> Page renders
  -> Local state and context state trigger updates
```

Why this matters:
- Global state changes re-render dependent components only.
- Local UI changes avoid global re-renders.

# 13. Beginner Learning Path
Recommended path with rationale:

Beginner-friendly explanation: Follow the order so you learn the foundation first, then the features.
1) [Cognitest-Frontend/src/main.tsx](Cognitest-Frontend/src/main.tsx) and [Cognitest-Frontend/src/App.tsx](Cognitest-Frontend/src/App.tsx) for boot flow.
2) [Cognitest-Frontend/src/routes/PublicRoutes.tsx](Cognitest-Frontend/src/routes/PublicRoutes.tsx) and [Cognitest-Frontend/src/routes/DashboardRoutes.tsx](Cognitest-Frontend/src/routes/DashboardRoutes.tsx) for navigation.
3) [Cognitest-Frontend/src/context/AppProviders.tsx](Cognitest-Frontend/src/context/AppProviders.tsx) for provider order.
4) [Cognitest-Frontend/src/context/AuthContext.tsx](Cognitest-Frontend/src/context/AuthContext.tsx) for session model.
5) [Cognitest-Frontend/src/services/backendClient.ts](Cognitest-Frontend/src/services/backendClient.ts) for API contract.
6) [Cognitest-Frontend/src/components/layout/DashboardLayout.tsx](Cognitest-Frontend/src/components/layout/DashboardLayout.tsx) for app shell.
7) [Cognitest-Frontend/src/pages/dashboard/projects/ProjectDetailPageNew.tsx](Cognitest-Frontend/src/pages/dashboard/projects/ProjectDetailPageNew.tsx) for core business flow.
8) [Cognitest-Frontend/src/components/RunSuiteModal.tsx](Cognitest-Frontend/src/components/RunSuiteModal.tsx) for execution logic.
9) [Cognitest-Frontend/src/components/api-tester/MiniPostman.tsx](Cognitest-Frontend/src/components/api-tester/MiniPostman.tsx) for supporting tools.
10) [Cognitest-Frontend/src/components/ui](Cognitest-Frontend/src/components/ui) for UI primitives.

# 14. Frontend Architecture Summary
This frontend is intentionally layered: core startup and routing at the top, global state via contexts, business flows in pages and orchestration components, and UI primitives underneath. This allows each file to own one responsibility, keeps auth and API concerns centralized, and makes product flows like spec upload, test generation, and run execution traceable end to end.

Beginner-friendly explanation: The app is built like a clean stack. The top decides where you go, the middle stores shared data, and the bottom is the reusable UI pieces.
