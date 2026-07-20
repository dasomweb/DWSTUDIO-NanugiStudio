"""Outre 전체 카탈로그 스크랩 — 실스토어 임포트 매니페스트

Playwright 기반 상품 수집. 처음 8개 카테고리에서 샘플링.
"""
import asyncio, json, sys, os, re
from urllib.parse import urljoin
sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

BASE = 'https://www.outre.com'
SCRATCH = r'C:/Users/JOHNKW~1/AppData/Local/Temp/claude/h--GitHub-DWSTUDIO-NanugiStudio/802840ea-702b-4570-b3d3-b2e80946a8f8/scratchpad'


async def scrape_list_page(page, url):
    """카테고리/목록 페이지 — 상품 링크만 추출"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(1000)
    except:
        return []

    hrefs = await page.locator('a[href*="/product/"]').all()
    prods = []
    seen = set()
    for a in hrefs[:15]:
        try:
            h = await a.get_attribute('href')
            if h and h not in seen:
                seen.add(h)
                prods.append(urljoin(BASE, h))
        except: pass
    return prods


async def scrape_product(page, url):
    """상품 상세 메타"""
    try:
        await page.goto(url, wait_until='networkidle', timeout=60000)
    except:
        return None

    try:
        # 제목
        h1 = await page.query_selector('h1')
        title = (await h1.inner_text()).strip() if h1 else ""
        if not title:
            return None

        # 갤러리 (Small image of)
        gallery = []
        imgs = await page.locator('img[alt^="Small image of"]').all()
        for im in imgs[:10]:
            try:
                s = await im.get_attribute('src')
                if s:
                    if 'api.outre' in s and '?url=' in s:
                        m = re.search(r'\?url=([^&]+)', s)
                        if m:
                            s = m.group(1)
                    gallery.append(s)
            except: pass

        # 컬러 리스트
        colors = []
        try:
            txt = await page.inner_text('body')
            if 'AVAILABLE COLORS' in txt:
                after = txt.split('AVAILABLE COLORS')[-1].split('\n')[0].strip()
                colors = [c.strip() for c in re.split(r'[,/]', after) if c.strip()]
        except: pass

        # 스펙 텍스트
        specs = {}
        for label in ['HAIR MATERIAL', 'TEXTURE', 'STYLE', 'COLOR SHOWN']:
            try:
                elems = await page.locator(f'text={label}').all()
                if elems:
                    parent = await elems[0].evaluate('el => el.parentElement?.innerText || ""')
                    val = parent.replace(label, '').strip()[:60]
                    if val:
                        specs[label.lower().replace(' ', '_')] = val
            except: pass

        # Lengths 버튼
        lengths = []
        try:
            buttons = await page.locator('button').all()
            for b in buttons:
                t = (await b.inner_text()).strip()
                if re.match(r'^\d+"$', t):
                    lengths.append(t)
        except: pass
        lengths = sorted(set(lengths))

        # 칩: alt="color"
        chips = {}
        try:
            imgs = await page.locator('img[alt="color"]').all()
            for im in imgs:
                try:
                    s = await im.get_attribute('src')
                    if s:
                        if 'api.outre' in s and '?url=' in s:
                            m = re.search(r'\?url=([^&]+)', s)
                            if m:
                                s = m.group(1)
                        stem = re.sub(r'\.(jpg|jpeg|png|webp)$', '', s.split('/')[-1], flags=re.I)
                        code = stem.replace('-', '/').upper()
                        chips[code] = s
                except: pass
        except: pass

        # 칩: alt∈colors (신형)
        try:
            color_set = {c.upper() for c in colors}
            imgs = await page.locator('img').all()
            for im in imgs:
                try:
                    alt = (await im.get_attribute('alt') or '').strip().upper()
                    if alt and alt in color_set and alt not in chips:
                        s = await im.get_attribute('src')
                        if s:
                            if 'api.outre' in s and '?url=' in s:
                                m = re.search(r'\?url=([^&]+)', s)
                                if m:
                                    s = m.group(1)
                            chips[alt] = s
                except: pass
        except: pass

        # YouTube
        yt = []
        try:
            as_ = await page.locator('a[href*="youtube.com"], a[href*="youtu.be"]').all()
            for a in as_:
                h = await a.get_attribute('href')
                if h:
                    yt.append(h)
        except: pass
        yt = list(set(yt))[:2]

        return {
            'title': title,
            'href': url,
            'gallery': gallery,
            'colors': colors,
            'lengths': lengths,
            'specs': specs,
            'chips': chips,
            'youtube': yt
        }
    except Exception as e:
        return None


async def main():
    print('📦 Outre 카탈로그 스크랩 (Playwright)\n')

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})

        # 카테고리 샘플
        cats = [
            ('Lace Wigs', f'{BASE}/product-category/lace-wigs/'),
            ('Wigs', f'{BASE}/product-category/wigs/'),
            ('Weaves', f'{BASE}/product-category/weaves/'),
            ('Braids', f'{BASE}/product-category/braids/'),
            ('Hair Pieces', f'{BASE}/product-category/hair-pieces/'),
            ('X-Pression', f'{BASE}/brands/x-pression/'),
            ('MyTresses', f'{BASE}/brands/mytresses/'),
            ('Pretty Quick', f'{BASE}/brands/pretty-quick/'),
        ]

        all_urls = []
        seen = set()

        for cat_name, cat_url in cats:
            print(f'📁 {cat_name:25}', end=' ', flush=True)
            try:
                urls = await scrape_list_page(page, cat_url)
                print(f'→ {len(urls):3} 상품')
                for u in urls:
                    if u not in seen:
                        seen.add(u)
                        all_urls.append(u)
            except Exception as e:
                print(f'⚠ {str(e)[:40]}')

        # 상품 상세
        print(f'\n{len(all_urls)}개 상품 수집 중...')
        all_prods = []
        for i, url in enumerate(all_urls):
            pct = int(100 * (i + 1) / len(all_urls))
            title = url.split('/')[-2][:32]
            print(f'[{pct:3}%] {title:32}', end=' ', flush=True)
            prod = await scrape_product(page, url)
            if prod:
                all_prods.append(prod)
                n_color = len(prod.get('colors', []))
                n_chip = len(prod.get('chips', {}))
                status = f"{n_color:2}색 {n_chip:2}칩"
                if prod.get('lengths'):
                    status += " ✓LEN"
                if prod.get('youtube'):
                    status += " ✓YT"
                print(f'✓ {status}')
            else:
                print('✗')

        await browser.close()

    # 저장
    out = f'{SCRATCH}/outre-catalog.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(all_prods, f, ensure_ascii=False, indent=1)

    print(f'\n✓ {out}')
    print(f'  총 {len(all_prods)}개')
    print(f'  칩 연결: {sum(1 for p in all_prods if p.get("chips"))}개')
    print(f'  LENGTH: {sum(1 for p in all_prods if p.get("lengths"))}개')
    print(f'  YouTube: {sum(1 for p in all_prods if p.get("youtube"))}개')


if __name__ == '__main__':
    asyncio.run(main())
