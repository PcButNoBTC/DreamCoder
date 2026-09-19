const { test, expect } = require('../electron/node_modules/@playwright/test');
test('DreamCoder frontend loads', async ({ page }) => {
  await page.goto('file://' + process.cwd() + '/../frontend/index.html');
  await expect(page.locator('body')).toBeVisible();
  await expect(page.locator('#editor')).toBeVisible();
});
