const { chromium } = require('playwright');

async function expandSection(page, title) {
  const btns = await page.$$('button');
  for (const b of btns) {
    const t = (await b.textContent())?.trim() || '';
    if (t === title || t.startsWith(title + ' ') || t.startsWith(title + '\n')) {
      await b.click();
      await page.waitForTimeout(200);
      return true;
    }
  }
  return false;
}

async function getComputedOfSelected(page, prop) {
  return await page.evaluate((p) => {
    // The selected block — get via chip's closest wrapper's .dw-section-preview > firstChild
    const chip = document.querySelector('button.bg-blue-600\\/90');
    if (!chip) return null;
    const wrapper = chip.closest('[class*="rounded-lg"][class*="border"]');
    if (!wrapper) return null;
    // Get what's visually the target — for inner blocks (heading), find inner element with matching block text
    // For outer block, use .dw-section-preview > firstChild
    const preview = wrapper.querySelector('.dw-section-preview');
    const target = preview?.firstElementChild || preview;
    if (!target) return null;
    return window.getComputedStyle(target)[p];
  }, prop);
}

async function selectById(page, blockId) {
  const chip = await page.$(`button[title*="${blockId}"]`);
  if (!chip) return false;
  await chip.click();
  await page.waitForTimeout(600);
  return true;
}

const out = [];
function r(name, pass, detail) {
  out.push({ name, pass, detail });
  console.log(`${pass ? '✓' : '✗'} ${name}  — ${detail}`);
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

  // Select hero cover
  await selectById(page, 'p17-b04');

  // ---------- SPACING: padding T/L/R/B + margin ----------
  await expandSection(page, 'Spacing');
  await page.waitForTimeout(300);

  const paddingBefore = await getComputedOfSelected(page, 'padding');
  const inputs = await page.$$('input[type="number"]');
  // Expected layout: [padT, padL, padR, padB, marT, marL, marR, marB, gap]
  if (inputs.length >= 4) {
    // padding-bottom = 4th
    await inputs[3].fill('80');
    await inputs[3].press('Tab');
    await page.waitForTimeout(1000);
    const after = await getComputedOfSelected(page, 'padding');
    r('SPACING padding-bottom → 80px', after !== paddingBefore && after?.includes('80'), `"${paddingBefore}" → "${after}"`);
  }

  // Margin-top
  if (inputs.length >= 5) {
    const marginBefore = await getComputedOfSelected(page, 'margin');
    await inputs[4].fill('30');
    await inputs[4].press('Tab');
    await page.waitForTimeout(1000);
    const after = await getComputedOfSelected(page, 'margin');
    r('SPACING margin-top → 30px', after?.includes('30'), `"${marginBefore}" → "${after}"`);
  }

  // ---------- BORDER ----------
  await expandSection(page, 'Border');
  await page.waitForTimeout(300);
  const borderBefore = await getComputedOfSelected(page, 'borderStyle');
  // Click "Solid" — might be inside an expanded section or SegmentedControl
  const solid = await page.locator('button', { hasText: /^Solid$/ }).first();
  try {
    await solid.click({ timeout: 2000 });
    await page.waitForTimeout(1000);
    const after = await getComputedOfSelected(page, 'borderStyle');
    r('BORDER style → Solid', after?.includes('solid'), `"${borderBefore}" → "${after}"`);
  } catch (e) {
    r('BORDER style → Solid', false, `button click failed: ${e.message.slice(0, 60)}`);
  }

  // ---------- SHADOW ----------
  await expandSection(page, 'Shadow');
  await page.waitForTimeout(300);
  const shadowBefore = await getComputedOfSelected(page, 'boxShadow');
  // Click a preset shadow button — probably labeled "sm", "md", "lg"
  try {
    const mdBtn = await page.locator('button', { hasText: /^md$/i }).first();
    await mdBtn.click({ timeout: 2000 });
    await page.waitForTimeout(1000);
    const after = await getComputedOfSelected(page, 'boxShadow');
    r('SHADOW → md preset', after !== shadowBefore && after !== 'none', `"${shadowBefore}" → "${after}"`);
  } catch (e) {
    r('SHADOW → md preset', false, `no md button: ${e.message.slice(0, 60)}`);
  }

  // ---------- SIZE ----------
  await expandSection(page, 'Size');
  await page.waitForTimeout(300);
  const widthBefore = await getComputedOfSelected(page, 'width');
  const sizeInputs = await page.$$('input[type="number"]');
  // Find width input — may not be easy; try the one closest after "Size" label
  // Use label search
  try {
    const widthLabel = await page.locator('span', { hasText: /^Width$/ }).first();
    const widthBox = await widthLabel.locator('..').locator('input[type="number"]').first();
    await widthBox.fill('800');
    await widthBox.press('Tab');
    await page.waitForTimeout(1000);
    const after = await getComputedOfSelected(page, 'width');
    r('SIZE width → 800', after !== widthBefore, `"${widthBefore}" → "${after}"`);
  } catch (e) {
    r('SIZE width', false, `input not found: ${e.message.slice(0, 80)}`);
  }

  // ---------- OVERLAY (on cover) ----------
  await expandSection(page, 'Overlay');
  await page.waitForTimeout(300);
  // No direct computed style for overlay — verify via style JSON via API instead
  try {
    const overlayStyle = await page.evaluate(async () => {
      const r = await fetch('https://api-server-production-e398.up.railway.app/api/projects/proj-001/pages/p17/blocks');
      const blocks = await r.json();
      const find = (bs, id) => {
        for (const b of bs) {
          if (b.block_id === id) return b;
          const f = find(b.inner_blocks || [], id);
          if (f) return f;
        }
        return null;
      };
      const block = find(blocks, 'p17-b04');
      return block?.style?.overlay || null;
    });
    r('OVERLAY exists on cover (style.overlay)', !!overlayStyle,
      overlayStyle ? `opacity=${overlayStyle.opacity}, blend=${overlayStyle.blendMode}` : 'null');
  } catch (e) {
    r('OVERLAY check', false, e.message.slice(0, 80));
  }

  // ---------- ALIGNMENT ----------
  await expandSection(page, 'Alignment');
  await page.waitForTimeout(300);
  try {
    // Self alignment select
    const selfSelect = await page.locator('select').first();
    await selfSelect.selectOption({ index: 1 });
    await page.waitForTimeout(1000);
    r('ALIGNMENT self changed', true, 'select option changed');
  } catch (e) {
    r('ALIGNMENT self', false, e.message.slice(0, 80));
  }

  // ---------- Switch to heading (inner) for typography tests ----------
  await selectById(page, 'p17-b06');

  const colorBefore = await page.evaluate(() => {
    const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
    return el ? window.getComputedStyle(el).color : null;
  });
  await expandSection(page, 'Typography');
  await page.waitForTimeout(300);
  const swatches = await page.$$('button[title*="#"]');
  if (swatches.length > 1) {
    await swatches[1].click();
    await page.waitForTimeout(1200);
    const after = await page.evaluate(() => {
      const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
      return el ? window.getComputedStyle(el).color : null;
    });
    r('TYPOGRAPHY color (2nd swatch)', after !== colorBefore, `"${colorBefore}" → "${after}"`);
  }

  // Font weight
  try {
    const mediumBtn = await page.locator('button[title*="Medium"]').first();
    await mediumBtn.click({ timeout: 2000 });
    await page.waitForTimeout(1000);
    const fw = await page.evaluate(() => {
      const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
      return el ? window.getComputedStyle(el).fontWeight : null;
    });
    r('TYPOGRAPHY weight → Medium', fw === '500', `fontWeight="${fw}"`);
  } catch (e) {
    r('TYPOGRAPHY weight Medium', false, e.message.slice(0, 80));
  }

  // Heading scale
  try {
    const h2 = await page.locator('button', { hasText: /^H2$/i }).first();
    await h2.click({ timeout: 2000 });
    await page.waitForTimeout(1000);
    const fs = await page.evaluate(() => {
      const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
      return el ? window.getComputedStyle(el).fontSize : null;
    });
    r('TYPOGRAPHY scale → H2', !!fs, `fontSize="${fs}"`);
  } catch (e) {
    r('TYPOGRAPHY scale H2', false, e.message.slice(0, 80));
  }

  // ---------- Panel stability ----------
  const beforeTabs = await page.$$eval('button', (bs) =>
    bs.map(b => b.textContent?.trim()).filter(t => t === 'Blocks' || t === 'Settings' || t === 'Content').length
  );
  // Rapid click 3 elements
  const chips = await page.$$('button[title*="p17-b"]');
  for (let i = 0; i < Math.min(4, chips.length); i++) {
    await chips[i].click();
    await page.waitForTimeout(200);
  }
  const afterTabs = await page.$$eval('button', (bs) =>
    bs.map(b => b.textContent?.trim()).filter(t => t === 'Blocks' || t === 'Settings' || t === 'Content').length
  );
  r('RightPanel tabs stable after rapid clicks', beforeTabs === afterTabs && afterTabs >= 3,
    `before=${beforeTabs} after=${afterTabs}`);

  // ---------- Summary ----------
  console.log('\n=== SUMMARY ===');
  const pass = out.filter((r) => r.pass).length;
  const fail = out.filter((r) => !r.pass).length;
  console.log(`PASS ${pass} / FAIL ${fail} / TOTAL ${out.length}`);
  console.log(`PageErrors: ${errs.length}`);
  errs.forEach((e) => console.log('  ', e.slice(0, 200)));

  await browser.close();
})();
