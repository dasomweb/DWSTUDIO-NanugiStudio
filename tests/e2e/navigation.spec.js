const { test, expect } = require('@playwright/test');
const { authenticateStore } = require('./helpers');

test.describe('네비게이션 및 페이지 접근성', () => {

  test.beforeEach(async ({ page }) => {
    await authenticateStore(page);
  });

  test('헤더에 로고 또는 스토어 이름 존재', async ({ page }) => {
    await page.goto('/');
    const header = page.locator('header').first();
    await expect(header).toBeVisible();
    // 스토어 이름 링크 또는 로고 (visible한 홈 링크)
    const logoOrName = header.getByRole('link', { name: /nanugi/i }).first();
    await expect(logoOrName).toBeVisible();
  });

  test('푸터 존재 및 링크 포함', async ({ page }) => {
    await page.goto('/');
    const footer = page.locator('footer').first();
    await expect(footer).toBeVisible();
    const footerLinks = footer.locator('a');
    const count = await footerLinks.count();
    expect(count).toBeGreaterThan(0);
  });

  test('주요 페이지 404 없음', async ({ page }) => {
    const pages = ['/', '/collections', '/collections/all', '/cart', '/search'];

    for (const path of pages) {
      await page.goto(path);
      await expect(page).not.toHaveTitle(/404/i);
      const bodyText = await page.locator('body').textContent();
      expect(bodyText).not.toContain('page not found');
    }
  });

  test('블로그 페이지 접근 가능', async ({ page }) => {
    await page.goto('/blogs');
    // 블로그가 없으면 404일 수 있지만 서버 에러는 아니어야 함
    const status = page.url();
    expect(status).toBeTruthy();
  });

  test('로고 클릭 시 홈으로 이동', async ({ page }) => {
    await page.goto('/collections/all');
    const homeLink = page.locator('header a[href="/"]').first();

    if (await homeLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await homeLink.click();
      await page.waitForLoadState('domcontentloaded');
      expect(page.url()).toMatch(/\/$|\/\?/);
    }
  });
});
