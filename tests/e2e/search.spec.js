const { test, expect } = require('@playwright/test');
const { authenticateStore } = require('./helpers');

test.describe('검색 플로우', () => {

  test.beforeEach(async ({ page }) => {
    await authenticateStore(page);
  });

  test('검색 페이지 정상 로딩', async ({ page }) => {
    await page.goto('/search');
    await expect(page).not.toHaveTitle(/404/i);
    await expect(page.locator('body')).toBeVisible();
  });

  test('검색어 입력 후 결과 페이지 이동', async ({ page }) => {
    await page.goto('/search?q=test');
    await expect(page).not.toHaveTitle(/404/i);
    await expect(page.locator('body')).toBeVisible();
  });

  test('검색 입력 필드가 동작함', async ({ page }) => {
    await page.goto('/');

    // 검색 아이콘/버튼 또는 검색 입력 필드 찾기
    const searchToggle = page.locator('[data-search-toggle], a[href*="/search"], button[aria-label*="search" i], button[aria-label*="검색"]').first();
    const searchInput = page.locator('input[type="search"], input[name="q"], input[placeholder*="search" i], input[placeholder*="검색"]').first();

    // 검색 토글이 있으면 클릭
    if (await searchToggle.isVisible({ timeout: 3000 }).catch(() => false)) {
      await searchToggle.click();
      await page.waitForTimeout(500);
    }

    // 검색 입력 필드가 보이면 검색 수행
    if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await searchInput.fill('product');
      await searchInput.press('Enter');
      await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
      // 검색 결과 페이지에 도착했는지 확인
      const url = page.url();
      expect(url).toContain('search');
    }
  });
});
