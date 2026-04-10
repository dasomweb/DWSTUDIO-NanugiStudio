const { test, expect } = require('@playwright/test');
const { authenticateStore } = require('./helpers');

// 모바일 프로젝트에서만 실행
test.describe('모바일 반응형', () => {

  test.beforeEach(async ({ page }) => {
    await authenticateStore(page);
  });

  test('모바일에서 홈페이지 정상 로딩', async ({ page }) => {
    await page.goto('/');
    await expect(page).not.toHaveTitle(/404/i);
    await expect(page.locator('body')).toBeVisible();
  });

  test('모바일 메뉴 (햄버거) 토글 동작', async ({ page }) => {
    await page.goto('/');

    // 모바일 메뉴 버튼 찾기
    const menuButton = page.locator(
      'button[aria-label*="menu" i], button[aria-label*="메뉴"], [data-header-drawer-toggle], details[id*="menu"] summary, header button:has(svg)'
    ).first();

    if (await menuButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await menuButton.click();
      await page.waitForTimeout(500);
      // 메뉴가 열렸는지 확인 (드로어 또는 네비게이션)
      const menuDrawer = page.locator(
        '[class*="drawer"][class*="open"], [class*="menu"][class*="active"], nav[class*="mobile"], [id*="menu-drawer"]'
      ).first();
      // 메뉴 드로어가 보이거나 네비게이션 링크가 보이면 통과
      const navLinks = page.locator('nav a').first();
      const isOpen = await menuDrawer.isVisible({ timeout: 3000 }).catch(() => false)
        || await navLinks.isVisible({ timeout: 3000 }).catch(() => false);
      expect(isOpen).toBeTruthy();
    }
  });

  test('모바일에서 상품 페이지 정상 표시', async ({ page }) => {
    await page.goto('/collections/all');
    const productLink = page.locator('a[href*="/products/"]').first();

    if (await productLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      const href = await productLink.getAttribute('href');
      await page.goto(href);
      await page.waitForLoadState('domcontentloaded');
      await expect(page).not.toHaveTitle(/404/i);
      // 가로 스크롤이 없는지 확인 (오버플로우 체크)
      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(hasHorizontalScroll).toBeFalsy();
    }
  });

  test('모바일에서 카트 페이지 접근 가능', async ({ page }) => {
    await page.goto('/cart');
    await expect(page).not.toHaveTitle(/404/i);
    await expect(page.locator('body')).toBeVisible();
  });
});
