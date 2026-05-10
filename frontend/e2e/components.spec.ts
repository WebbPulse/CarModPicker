import { test, expect } from '@playwright/test';

test('kitchen-sink visual regression', async ({ page }) => {
  page.on('pageerror', (err) => {
    throw err;
  });

  await page.goto('/_kitchen-sink');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);

  await expect(page).toHaveScreenshot({ fullPage: true });
});
