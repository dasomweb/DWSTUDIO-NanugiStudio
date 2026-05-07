const STORE_PASSWORD = process.env.STORE_PASSWORD || 'dwstudio';

/**
 * 패스워드 보호 페이지를 통과합니다.
 * 이미 인증된 경우 스킵합니다.
 */
async function authenticateStore(page) {
  await page.goto('/');

  // 봇 보호 (verification) 페이지 통과 대기 — JS 챌린지가 자동 통과될 때까지 최대 30초
  const verificationHeading = page.locator('h1', { hasText: /verified/i });
  if (await verificationHeading.isVisible({ timeout: 2000 }).catch(() => false)) {
    await verificationHeading.waitFor({ state: 'detached', timeout: 30_000 }).catch(() => {});
    // 통과 후 안정화 대기
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  }

  // 패스워드 페이지인지 확인
  const passwordInput = page.locator('input[type="password"]');
  if (await passwordInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await passwordInput.fill(STORE_PASSWORD);
    const submitButton = page.locator('button[type="submit"], input[type="submit"]');
    if (await submitButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await submitButton.click();
    } else {
      await passwordInput.press('Enter');
    }
    await page.waitForURL(url => !url.pathname.includes('password'), { timeout: 10_000 });
  }
}

/**
 * 페이지가 정상 로딩되었는지 확인합니다 (404/500 아님).
 */
async function assertPageLoaded(page) {
  const title = await page.title();
  const is404 = title.toLowerCase().includes('404') || title.toLowerCase().includes('not found');
  const content = await page.content();
  const hasError = content.includes('500') && content.includes('error');
  return { is404, hasError, title };
}

module.exports = { authenticateStore, assertPageLoaded, STORE_PASSWORD };
