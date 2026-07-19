import asyncio, os, sys
from datetime import datetime, timezone
SP = r'C:/Users/JOHNKW~1/AppData/Local/Temp/claude/h--GitHub-DWSTUDIO-NanugiStudio/802840ea-702b-4570-b3d3-b2e80946a8f8/scratchpad'
os.environ['STOREFORGE_DATABASE_URL'] = open(f'{SP}/.dburl').read().strip()
sys.path.insert(0, 'api')
from sqlmodel import Session, select
from app.db import engine
from app.models import Store
from app.security import decrypt_token
from app.shopify import ShopifyClient, ShopifyError, mint_token
from app.engine.images import generate_one

STYLE_BY_TAG = [
    ('category:lace-wigs',    'a silky natural lace front wig, long flowing layers'),
    ('category:wigs',         'an elegant natural-looking wig'),
    ('category:crochet-hair', 'voluminous springy crochet twist curls'),
    ('category:pre-stretched-braid', 'sleek long pre-stretched braids'),
    ('category:braiding-hair','long premium knotless box braids'),
    ('category:braids',       'neat professional braided hairstyle'),
    ('category:weave',        'long flowing silky weave hairstyle'),
    ('category:ponytails',    'a sleek high drawstring ponytail extension'),
]
BASE = ("Uniform e-commerce catalog photograph: elegant Black woman model wearing {style}, "
        "three-quarter studio portrait framed head to chest, soft warm cream seamless background, "
        "gentle natural light, consistent premium catalog framing, photorealistic. "
        "STRICTLY NO text, NO letters, NO logos, NO watermarks.")

async def main():
    with Session(engine) as s:
        st = s.exec(select(Store).where(Store.shop_domain == 'dasomdev.myshopify.com')).first()
        cid, csec = decrypt_token(st.encrypted_client_id), decrypt_token(st.encrypted_client_secret)
    c = ShopifyClient(st.shop_domain, await mint_token(st.shop_domain, cid, csec))
    q = await c.graphql('query { products(first: 50, query: "vendor:Outre") { nodes { id title handle tags } } }')
    nodes = q['products']['nodes']
    print(f'대상 {len(nodes)}개')
    stamp = datetime.now(timezone.utc).strftime('%H%M%S')
    ok = fail = 0
    for i, n in enumerate(nodes):
        tags = n.get('tags') or []
        style = next((s2 for t, s2 in STYLE_BY_TAG if t in tags), 'premium hair extension styling')
        try:
            data = generate_one(BASE.format(style=style), '4:5')
            mime, ext = ('image/png','png') if data[:8]==b'\x89PNG\r\n\x1a\n' else ('image/jpeg','jpg')
            res = await c.stage_upload(f'sf-uni-{i}-{stamp}.{ext}', mime, data)
            await c.product_set({'id': n['id'], 'files': [{'originalSource': res, 'contentType': 'IMAGE', 'alt': n['title'][:120]}]})
            ok += 1
            print(f'✓ {i+1}/{len(nodes)} {n["title"][:40]}')
        except (ShopifyError, Exception) as e:
            fail += 1
            print(f'✗ {n["title"][:40]}: {str(e)[:80]}')
    print(f'완료 — 성공 {ok} / 실패 {fail}')
asyncio.run(main())
