import { expect, test } from "@playwright/test"

test("public login route renders", async ({ page }) => {
  await page.goto("/login")
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible()
})

test("dashboard route redirects unauthenticated users", async ({ page }) => {
  await page.goto("/dashboard")
  await expect(page).toHaveURL(/\/login$/)
})
