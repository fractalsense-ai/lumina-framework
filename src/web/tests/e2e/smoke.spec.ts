import { test, expect } from '@playwright/test'

test('app shell loads unauthenticated login screen', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: /Project Lumina/i })).toBeVisible()
  await expect(page.getByPlaceholder('Username')).toBeVisible()
  await expect(page.getByPlaceholder('Password')).toBeVisible()
  await expect(page.getByRole('button', { name: /Sign In/i })).toBeVisible()
})
