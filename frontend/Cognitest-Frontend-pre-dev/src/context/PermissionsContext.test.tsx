import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { PermissionsProvider, usePermissions } from "./PermissionsContext"

vi.mock("./AuthContext", () => ({
  useAuth: vi.fn(() => ({
    user: { id: "u-1", systemRole: "MEMBER" },
    workspacePermissions: {
      "ws-1": ["TEST_CASE.CREATE", "TEST_RUN.EXECUTE", "PROJECT.UPDATE"],
    },
    workspace: { id: "ws-1" },
    isAdmin: false,
  })),
}))

const Probe = () => {
  const perms = usePermissions()
  return (
    <div>
      <span data-testid="create-tests">{String(perms.canCreateTests)}</span>
      <span data-testid="run-tests">{String(perms.canRunTests)}</span>
      <span data-testid="modify-project">{String(perms.canModifyProject)}</span>
      <span data-testid="manage-members">{String(perms.canManageMembers)}</span>
    </div>
  )
}

describe("PermissionsContext", () => {
  it("maps workspace permissions into capability flags", () => {
    render(
      <PermissionsProvider>
        <Probe />
      </PermissionsProvider>,
    )

    expect(screen.getByTestId("create-tests")).toHaveTextContent("true")
    expect(screen.getByTestId("run-tests")).toHaveTextContent("true")
    expect(screen.getByTestId("modify-project")).toHaveTextContent("true")
    expect(screen.getByTestId("manage-members")).toHaveTextContent("false")
  })
})
