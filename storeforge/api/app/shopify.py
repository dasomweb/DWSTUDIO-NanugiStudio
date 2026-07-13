"""Shopify Admin GraphQL 클라이언트.

축① 주입 경로는 metafieldsSet 하나뿐이다 (기획안 §4.3, §6.1).
write_themes(보호 스코프)를 쓰지 않는 것이 이 설계의 핵심이므로,
여기에 themeFilesUpsert 를 추가하고 싶어지면 먼저 기획안 §4.5 를 다시 읽을 것.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from .config import get_settings
from .engine.brand import KEY, NAMESPACE

_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$")


class ShopifyError(RuntimeError):
    pass


def normalize_domain(value: str) -> str:
    """'https://nanugi.myshopify.com/admin' 같은 입력도 받아준다."""
    d = value.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0]
    if "." not in d:
        d = f"{d}.myshopify.com"
    if not _DOMAIN_RE.match(d):
        raise ValueError(f"올바른 *.myshopify.com 도메인이 아닙니다: {value!r}")
    return d


@dataclass
class ShopInfo:
    name: str
    plan: str
    myshopify_domain: str


class ShopifyClient:
    def __init__(self, shop_domain: str, access_token: str) -> None:
        self.shop_domain = shop_domain
        self._token = access_token
        self._version = get_settings().shopify_api_version

    @property
    def endpoint(self) -> str:
        return f"https://{self.shop_domain}/admin/api/{self._version}/graphql.json"

    async def graphql(self, query: str, variables: dict | None = None) -> dict:
        headers = {
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.endpoint,
                headers=headers,
                json={"query": query, "variables": variables or {}},
            )

        if resp.status_code == 401:
            raise ShopifyError("인증 실패 — Admin API 토큰이 잘못됐거나 만료됐습니다.")
        if resp.status_code == 403:
            raise ShopifyError(
                "권한 부족 — 커스텀 앱에 write_metafields / read_products 스코프가 있는지 확인하세요."
            )
        if resp.status_code == 404:
            raise ShopifyError(
                f"엔드포인트를 찾을 수 없습니다 — 도메인({self.shop_domain})을 확인하세요."
            )
        if resp.status_code >= 400:
            raise ShopifyError(f"Shopify HTTP {resp.status_code}: {resp.text[:300]}")

        body = resp.json()
        if body.get("errors"):
            raise ShopifyError(f"GraphQL 오류: {json.dumps(body['errors'], ensure_ascii=False)[:400]}")
        return body["data"]

    # --- 연결 테스트 ------------------------------------------------------------
    async def verify(self) -> ShopInfo:
        """관리자 페이지의 '연결 테스트'가 부르는 것. 토큰이 실제로 동작하는지 확인한다."""
        data = await self.graphql(
            "{ shop { name myshopifyDomain plan { displayName } } }"
        )
        shop = data["shop"]
        return ShopInfo(
            name=shop["name"],
            plan=shop["plan"]["displayName"],
            myshopify_domain=shop["myshopifyDomain"],
        )

    # --- 축① 주입 ---------------------------------------------------------------
    async def set_brand_metafield(self, payload: dict) -> str:
        """브랜드 페이로드를 shop.metafields.storeforge.brand 에 넣는다. 반환: metafield GID."""
        shop_gid = (await self.graphql("{ shop { id } }"))["shop"]["id"]

        mutation = """
        mutation SetBrand($metafields: [MetafieldsSetInput!]!) {
          metafieldsSet(metafields: $metafields) {
            metafields { id key namespace }
            userErrors { field message code }
          }
        }
        """
        variables = {
            "metafields": [
                {
                    "ownerId": shop_gid,
                    "namespace": NAMESPACE,
                    "key": KEY,
                    "type": "json",
                    "value": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                }
            ]
        }
        data = await self.graphql(mutation, variables)
        result = data["metafieldsSet"]

        if result["userErrors"]:
            msgs = "; ".join(
                f"{'.'.join(e.get('field') or [])}: {e['message']}" for e in result["userErrors"]
            )
            raise ShopifyError(f"metafieldsSet 실패 — {msgs}")

        return result["metafields"][0]["id"]

    async def get_brand_metafield(self) -> dict | None:
        """현재 주입된 값을 읽는다. 온보딩 중복 실행을 막는 근거로 쓴다 (기획안 §1.4)."""
        query = """
        query { shop { metafield(namespace: "%s", key: "%s") { value updatedAt } } }
        """ % (NAMESPACE, KEY)
        data = await self.graphql(query)
        mf = data["shop"]["metafield"]
        if not mf:
            return None
        return {"value": json.loads(mf["value"]), "updated_at": mf["updatedAt"]}
