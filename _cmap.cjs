const { chromium } = require('@playwright/test');
const fs = require('fs');
const SP = process.env.SP;
const items = JSON.parse(fs.readFileSync(`${SP}/outre-deep.json`, 'utf8'));
const dec = u => { try { return u.includes('image?url=') ? decodeURIComponent(u.split('image?url=')[1].split('&')[0]) : u; } catch { return u; } };
(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({viewport:{width:1440,height:900}})).newPage();
  const out = [];
  for (const it of items) {
    if (!it.colors || !it.colors.length) { out.push({ href: it.href, title: it.title, map: {} }); continue; }
    const map = {};
    try {
      await page.goto(it.href, { waitUntil: 'networkidle', timeout: 90000 });
      await page.waitForTimeout(2000);
      for (const color of it.colors.slice(0, 10)) {
        try {
          const btn = page.locator(`button:text-is("${color}"), [role=button]:text-is("${color}"), li:text-is("${color}")`).first();
          await btn.click({ timeout: 4000 });
          await page.waitForTimeout(1200);
          const src = await page.evaluate(() => {
            const main = [...document.images].find(i => /^image of/i.test(i.alt || '')) ||
                         [...document.images].filter(i => i.naturalWidth > 500 && /uploads/.test(i.src)).sort((a,b)=>b.naturalWidth-a.naturalWidth)[0];
            return main ? (main.currentSrc || main.src) : null;
          });
          if (src) map[color] = dec(src);
        } catch {}
      }
      out.push({ href: it.href, title: it.title, map });
      console.log('✓', it.title.slice(0, 38), '→', Object.keys(map).length + '/' + it.colors.length);
    } catch (e) { console.log('✗', it.title.slice(0, 38), e.message.slice(0, 40)); out.push({ href: it.href, title: it.title, map }); }
  }
  fs.writeFileSync(`${SP}/color-map.json`, JSON.stringify(out, null, 1));
  console.log('저장 완료');
  await browser.close();
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
