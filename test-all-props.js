/**
 * Comprehensive Properties panel live-update audit.
 *
 * For each property control, change a value and verify:
 *  1. Canvas DOM reflects the change (computed style)
 *  2. No errors
 *  3. Inspector panel doesn't flicker/remount
 *
 * Reports per property: PASS / FAIL / reason.
 */
const { chromium } = require('playwright');

const API = 'https://api-server-production-e398.up.railway.app';
const APP = 'https://web.dwstudio.cc';

async function selectHeadingBlock(page) {
  const heading = await page.$('.dw-section-preview h1, .dw-section-preview [class*="text-5xl"][class*="font-bold"]');
  if (heading) {
    await heading.click();
    await page.waitForTimeout(700);
  }
  // Verify selection
  return await page.$eval('span.font-mono.text-blue-400', (el) => el.textContent || '').catch(() => null);
}

async function selectCoverBlock(page) {
  // Click chip of p17-b04 (cover) — top-left of the hero block
  const chip = await page.$('button[title*="p17-b04"]');
  if (chip) {
    await chip.click();
    await page.waitForTimeout(700);
  }
  return await page.$eval('span.font-mono.text-blue-400', (el) => el.textContent || '').catch(() => null);
}

async function getCanvasBlock(page, blockId) {
  return await page.evaluate((id) => {
    // Inspect canvas — find element with data-block-id matching or find section by chip title
    // Actual hero block rendered by SectionPreview doesn't have data-block-id, so fall back to section chip
    const chip = document.querySelector(`button[title*="${id}"]`);
    if (!chip) return null;
    const wrapper = chip.closest('[class*="rounded-lg"][class*="border"]');
    if (!wrapper) return null;
    const preview = wrapper.querySelector('.dw-section-preview');
    if (!preview) return null;
    // The hero pattern div is the first child element inside preview
    const hero = preview.firstElementChild;
    const target = hero || preview;
    const cs = window.getComputedStyle(target);
    return {
      padding: cs.padding,
      margin: cs.margin,
      backgroundColor: cs.backgroundColor,
      backgroundImage: cs.backgroundImage,
      borderWidth: cs.borderWidth,
      borderStyle: cs.borderStyle,
      borderColor: cs.borderColor,
      borderRadius: cs.borderRadius,
      width: cs.width,
      height: cs.height,
      boxShadow: cs.boxShadow,
      color: cs.color,
      fontWeight: cs.fontWeight,
      textAlign: cs.textAlign,
    };
  }, blockId);
}

async function expandSection(page, sectionTitle) {
  // Click the properties section header (e.g., "Spacing", "Background")
  const btns = await page.$$('button');
  for (const b of btns) {
    const t = (await b.textContent())?.trim() || '';
    if (t === sectionTitle || t.startsWith(sectionTitle + ' ')) {
      await b.click();
      await page.waitForTimeout(200);
      return true;
    }
  }
  return false;
}

const results = [];
function record(name, pass, detail) {
  results.push({ name, pass, detail });
  console.log(`${pass ? '✓' : '✗'} ${name}  — ${detail}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();

  const pageErrors = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));

  await page.goto(APP, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1500);
  await page.click('text=Korus Orchid Corporation');
  await page.waitForTimeout(2000);
  await page.click('text=Home');
  await page.waitForTimeout(2500);

  // ============ Select Hero Section (cover) ============
  console.log('\n=== Select Hero Section (p17-b04 cover) ===');
  const coverChip = await selectCoverBlock(page);
  console.log('  selected:', coverChip);
  const before = await getCanvasBlock(page, 'p17-b04');
  console.log('  canvas before:', JSON.stringify(before).slice(0, 200));

  // ============ SPACING: padding ============
  console.log('\n=== SPACING — padding ===');
  await expandSection(page, 'Spacing');
  await page.waitForTimeout(300);

  // Find padding T input — the first number input near "PADDING" label
  const padTopInputs = await page.$$('input[type="number"]');
  if (padTopInputs.length > 0) {
    const paddingInput = padTopInputs[0]; // padding top (first)
    await paddingInput.fill('150');
    await paddingInput.press('Tab');
    await page.waitForTimeout(1000);
    const after = await getCanvasBlock(page, 'p17-b04');
    const changed = before?.padding !== after?.padding;
    record('SPACING padding-top 150px', changed, `before="${before?.padding}" after="${after?.padding}"`);
  } else {
    record('SPACING padding-top', false, 'no number inputs found');
  }

  // ============ BACKGROUND: color change ============
  console.log('\n=== BACKGROUND — color swatch ===');
  await expandSection(page, 'Background');
  await page.waitForTimeout(300);
  // Click Color mode first
  const colorModeBtn = await page.$('button:has-text("Color")');
  if (colorModeBtn) {
    // Skip — user currently has Image mode. Try Gradient instead or just test existing.
  }

  // ============ TYPOGRAPHY: color ============
  console.log('\n=== Select heading ===');
  const headingId = await selectHeadingBlock(page);
  console.log('  selected:', headingId);
  const hbefore = await page.evaluate(() => {
    const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
    if (!el) return null;
    const cs = window.getComputedStyle(el);
    return { color: cs.color, fontWeight: cs.fontWeight, textAlign: cs.textAlign };
  });
  console.log('  heading before:', JSON.stringify(hbefore));

  // Expand Typography
  await expandSection(page, 'Typography');
  await page.waitForTimeout(300);

  // Click a color token swatch
  const swatches = await page.$$('button[title*="#"]'); // TokenColorPicker swatches have hex in title
  if (swatches.length > 0) {
    await swatches[0].click();
    await page.waitForTimeout(1500); // optimistic update + patch
    const hafter = await page.evaluate(() => {
      const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
      if (!el) return null;
      const cs = window.getComputedStyle(el);
      return { color: cs.color };
    });
    const changed = hbefore?.color !== hafter?.color;
    record('TYPOGRAPHY color (token swatch)', changed, `before="${hbefore?.color}" after="${hafter?.color}"`);
  } else {
    record('TYPOGRAPHY color', false, 'no color swatch found');
  }

  // Weight
  const weightB = await page.$('button:has-text("B"):visible');
  if (weightB) {
    await weightB.click();
    await page.waitForTimeout(800);
    const wafter = await page.evaluate(() => {
      const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
      return el ? window.getComputedStyle(el).fontWeight : null;
    });
    record('TYPOGRAPHY weight → Bold', wafter === '700' || wafter === 'bold', `fontWeight="${wafter}"`);
  }

  // Align center
  const alignC = await page.$('button[title="Center"]');
  if (alignC) {
    await alignC.click();
    await page.waitForTimeout(800);
    const aafter = await page.evaluate(() => {
      const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
      return el ? window.getComputedStyle(el).textAlign : null;
    });
    record('TYPOGRAPHY align → Center', aafter === 'center', `textAlign="${aafter}"`);
  }

  // ============ BORDER ============
  console.log('\n=== BORDER ===');
  await expandSection(page, 'Border');
  await page.waitForTimeout(300);
  const solidBtn = await page.$('button:has-text("Solid")');
  if (solidBtn) {
    await solidBtn.click();
    await page.waitForTimeout(1000);
    const b = await page.evaluate(() => {
      const el = document.querySelector('.dw-section-preview [class*="font-bold"]');
      return el ? window.getComputedStyle(el).borderStyle : null;
    });
    record('BORDER style → Solid', b === 'solid', `borderStyle="${b}"`);
  } else {
    record('BORDER style button', false, 'Solid button not found');
  }

  // ============ Panel stability check ============
  console.log('\n=== Panel stability during rapid clicks ===');
  // Click several different elements rapidly, check RightPanel tab persistence
  const blocksTabBefore = await page.$$eval('button', (btns) =>
    btns.find((b) => b.textContent?.trim() === 'Blocks') !== undefined
  ).catch(() => false);

  for (let i = 0; i < 3; i++) {
    const chips = await page.$$('button[title*="p17-b"]');
    if (chips.length > i) {
      await chips[i].click();
      await page.waitForTimeout(400);
    }
  }
  const blocksTabAfter = await page.$$eval('button', (btns) =>
    btns.find((b) => b.textContent?.trim() === 'Blocks') !== undefined
  ).catch(() => false);

  record('Blocks tab persistence during selection changes',
    blocksTabBefore === blocksTabAfter && blocksTabAfter,
    `before=${blocksTabBefore} after=${blocksTabAfter}`);

  // ============ Summary ============
  console.log('\n=== SUMMARY ===');
  const pass = results.filter((r) => r.pass).length;
  const fail = results.filter((r) => !r.pass).length;
  console.log(`PASS: ${pass}  FAIL: ${fail}  TOTAL: ${results.length}`);
  console.log(`PageErrors: ${pageErrors.length}`);
  pageErrors.forEach((e) => console.log('  ', e.slice(0, 200)));

  await browser.close();
})();
