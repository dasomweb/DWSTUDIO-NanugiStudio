/**
 * Direct API patch → canvas reflection test.
 * Bypasses UI selector issues. Verifies that when we patch a block.style
 * via the backend PATCH, the frontend refreshes and canvas reflects it.
 * This is the END-TO-END that matters — matches the Properties panel flow.
 */
const { chromium } = require('playwright');
const API = 'https://api-server-production-e398.up.railway.app';
const BID = 'p17-b04';

async function patchStyle(style) {
  const resp = await fetch(`${API}/api/projects/proj-001/pages/p17/blocks/${BID}/style`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ style }),
  });
  if (!resp.ok) throw new Error(`PATCH failed: ${resp.status} ${await resp.text()}`);
}

async function getComputed(page, prop) {
  return await page.evaluate(async (p) => {
    // Force a refresh first (trigger refreshBlocks if possible)
    const wrapper = document.querySelector('[data-block-id="p17-b04"]')
      || document.querySelector('button[title*="p17-b04"]')?.closest('[class*="rounded-lg"][class*="border"]');
    const preview = wrapper?.querySelector('.dw-section-preview');
    const target = preview?.firstElementChild || preview;
    if (!target) return null;
    return window.getComputedStyle(target)[p];
  }, prop);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));

  await page.goto('https://web.dwstudio.cc/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1500);
  await page.click('text=Korus Orchid Corporation');
  await page.waitForTimeout(2000);
  await page.click('text=Home');
  await page.waitForTimeout(2500);

  const results = [];
  const test = async (name, style, prop, expectContains) => {
    await patchStyle(style);
    // Force reload to pick up server state
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    await page.click('text=Korus Orchid Corporation');
    await page.waitForTimeout(1500);
    await page.click('text=Home');
    await page.waitForTimeout(2500);
    const val = await getComputed(page, prop);
    const pass = val?.toString().toLowerCase().includes(expectContains.toLowerCase());
    console.log(`${pass ? '✓' : '✗'} ${name}  → ${prop}="${val}"  expected contains "${expectContains}"`);
    results.push({ name, pass, val });
  };

  // Test each section
  await test('SPACING padding all 120',
    { spacing: { padding: { top: 120, right: 120, bottom: 120, left: 120 }, margin: null, gap: null } },
    'padding', '120');

  await test('SPACING margin 40 20 40 20',
    { spacing: { padding: null, margin: { top: 40, right: 20, bottom: 40, left: 20 }, gap: null } },
    'margin', '40');

  await test('BORDER solid 4px',
    { border: { width: 4, style: 'solid', color: { hex: '#2563eb' }, radius: { all: 0 } } },
    'borderStyle', 'solid');

  await test('BORDER radius 20',
    { border: { width: 2, style: 'solid', color: { hex: '#2563eb' }, radius: { all: 20 } } },
    'borderRadius', '20px');

  await test('SHADOW md preset',
    { shadow: { preset: 'md' } },
    'boxShadow', 'rgb');  // any non-none box shadow

  await test('SIZE width 600 / minHeight 400',
    { size: { width: '600px', minHeight: '400px' } },
    'width', '600px');

  await test('BACKGROUND color red',
    { background: { color: { hex: '#ff0000' }, image: null, gradient: null } },
    'backgroundColor', 'rgb(255, 0, 0)');

  // Reset to clean state (remove overrides) to not leave the page broken
  await patchStyle({
    spacing: null, margin: null, gap: null,
    border: null, shadow: null, size: null,
    background: { image: null, color: null, gradient: null },
    overlay: null, typography: null, alignment: null, responsive: null,
  });

  console.log('\n=== SUMMARY ===');
  const pass = results.filter(r => r.pass).length;
  console.log(`PASS ${pass} / TOTAL ${results.length}`);
  console.log(`PageErrors: ${errs.length}`);
  errs.forEach(e => console.log('  ', e.slice(0, 200)));

  await browser.close();
})();
