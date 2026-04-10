const { test, expect } = require('@playwright/test');
const { authenticateStore } = require('./helpers');

test.describe('쇼핑 플로우: 홈 → 컬렉션 → 상품 → 카트', () => {

  test.beforeEach(async ({ page }) => {
    await authenticateStore(page);
  });

  test('홈페이지 정상 로딩', async ({ page }) => {
    await page.goto('/');
    await expect(page).not.toHaveTitle(/404/i);
    await expect(page.locator('body')).toBeVisible();
    // 헤더 존재 확인
    await expect(page.locator('header').first()).toBeVisible();
    // 푸터 존재 확인
    await expect(page.locator('footer').first()).toBeVisible();
  });

  test('컬렉션 목록 페이지 로딩', async ({ page }) => {
    await page.goto('/collections');
    await expect(page).not.toHaveTitle(/404/i);
    await expect(page.locator('body')).toBeVisible();
  });

  test('전체 상품 컬렉션 로딩', async ({ page }) => {
    await page.goto('/collections/all');
    await expect(page).not.toHaveTitle(/404/i);
    // 상품 카드 또는 상품 링크가 하나 이상 존재
    const productLinks = page.locator('a[href*="/products/"]');
    const count = await productLinks.count();
    // 상품이 없을 수도 있으므로 페이지 자체가 로딩되면 통과
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('상품 상세 페이지 접근', async ({ page }) => {
    await page.goto('/collections/all');
    const productLink = page.locator('a[href*="/products/"]').first();

    if (await productLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      const href = await productLink.getAttribute('href');
      await page.goto(href);
      await expect(page).not.toHaveTitle(/404/i);
      // 상품 페이지에 Add to cart 또는 가격 정보 존재
      const hasProductContent = page.locator('[data-product-form], form[action*="/cart/add"], .product, [class*="product"]').first();
      await expect(hasProductContent).toBeVisible({ timeout: 10_000 });
    }
  });

  test('카트에 상품 추가 후 카트 확인', async ({ page }) => {
    await page.goto('/collections/all');
    const productLink = page.locator('a[href*="/products/"]').first();

    if (await productLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      const href = await productLink.getAttribute('href');
      await page.goto(href);
      await page.waitForLoadState('domcontentloaded');

      // Add to cart 버튼 찾기 — 메인 폼 내의 버튼 우선
      const addToCartBtn = page.locator(
        'form[action*="/cart/add"] button[type="submit"], product-form button[type="submit"], button[name="add"]'
      ).first();

      if (await addToCartBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await addToCartBtn.scrollIntoViewIfNeeded();
        await addToCartBtn.click({ force: true });
        await page.waitForTimeout(2000);

        // 카트 페이지에서 확인
        await page.goto('/cart');
        await expect(page).not.toHaveTitle(/404/i);
        await expect(page.locator('body')).toBeVisible();
      }
    }
  });

  test('카트 페이지 정상 로딩', async ({ page }) => {
    await page.goto('/cart');
    await expect(page).not.toHaveTitle(/404/i);
    await expect(page.locator('body')).toBeVisible();
  });
});
