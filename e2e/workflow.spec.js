const { test, expect } = require('../electron/node_modules/@playwright/test');
const path = require('path');

test('DreamCoder boots into the creation workflow', async ({ page }) => {
  const file = path.resolve(process.cwd(), 'frontend', 'index.html');
  await page.goto('file://' + file);
  await expect(page.locator('body')).toBeVisible();
  await expect(page.locator('#editor')).toBeVisible();
  await expect(page.locator('.dc-workflow')).toBeVisible({ timeout: 10000 });
  await expect(page.locator('[data-workflow="goal"]')).toBeVisible();
  await expect(page.locator('[data-workflow="git"]')).toBeVisible();
});
