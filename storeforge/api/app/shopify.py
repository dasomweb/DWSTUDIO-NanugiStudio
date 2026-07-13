"""Shopify Admin GraphQL 클라이언트.

축① 주입 경로는 metafieldsSet 하나뿐이다 (기획안 §4.3, §6.1).
write_themes(보호 스코프)를 쓰지 않는 것이 이 설계의 핵심이므로,
여기에 themeFilesUpsert 를 추가하고 싶어지면 먼저 기획안 §4.5 를 다시 읽을 것.
"""

from __future__ import annotations

import json
import re
import time
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


# client_credentials 로 받은 토큰은 수명이 짧다. 요청마다 새로 받으면 낭비이므로
# 만료 조금 전까지 재사용한다. (프로세스 메모리 캐시 — 재시작하면 비워진다)
_token_cache: dict[str, tuple[str, float]] = {}
_TOKEN_SAFETY_MARGIN = 60.0  # 초. 만료 직전 토큰을 쓰다 401 나는 것을 피한다.


async def mint_token(shop_domain: str, client_id: str, client_secret: str) -> str:
    """앱의 client_id/secret 으로 Admin API 액세스 토큰을 발급받는다.

    기존 테마 배포 워크플로(.github/workflows/deploy-theme.yml)가 쓰는 것과 같은 방식이다.
    영구 토큰을 DB 에 들고 있지 않아도 되므로 유출 리스크가 낮다.
    """
    cached = _token_cache.get(shop_domain)
    if cached and cached[1] > time.monotonic() + _TOKEN_SAFETY_MARGIN:
        return cached[0]

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"https://{shop_domain}/admin/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

    if resp.status_code >= 400:
        raise ShopifyError(
            "토큰 발급 실패 — Client ID/Secret 이 잘못됐거나 앱이 이 스토어에 설치되어 있지 않습니다. "
            f"(HTTP {resp.status_code})"
        )

    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise ShopifyError(f"토큰 발급 응답에 access_token 이 없습니다: {str(body)[:200]}")

    expires_in = float(body.get("expires_in", 3600))
    _token_cache[shop_domain] = (token, time.monotonic() + expires_in)
    return token


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
                "권한 부족 — 샵 메타필드 주입에는 스코프가 필요 없으므로, 이 오류가 났다면 "
                "앱이 이 스토어에 설치되어 있는지부터 확인하세요."
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

    async def access_scopes(self) -> list[str]:
        """이 앱에 실제로 부여된 스코프. 화면에 표시해 연동 상태를 눈으로 확인하는 용도다.

        축① 주입 자체는 스코프를 요구하지 않는다 (models.REQUIRED_SCOPES 주석 참고).
        스코프가 실재하는 리소스를 건드리는 축② 부터 이 값이 판단 근거가 된다.
        """
        data = await self.graphql(
            "{ currentAppInstallation { accessScopes { handle } } }"
        )
        scopes = data["currentAppInstallation"]["accessScopes"]
        return sorted(s["handle"] for s in scopes)

    # --- 샵 메타필드 (여러 모듈이 공유한다) --------------------------------------
    #
    # 소유자가 Shop 이므로 스코프가 필요 없다. 자세한 이유는 capabilities.py 주석 참고.
    async def shop_gid(self) -> str:
        return (await self.graphql("{ shop { id } }"))["shop"]["id"]

    async def set_shop_metafield(self, namespace: str, key: str, payload: dict) -> str:
        """샵 메타필드에 JSON 을 넣는다. 반환: metafield GID."""
        mutation = """
        mutation SetShopMetafield($metafields: [MetafieldsSetInput!]!) {
          metafieldsSet(metafields: $metafields) {
            metafields { id key namespace }
            userErrors { field message code }
          }
        }
        """
        variables = {
            "metafields": [
                {
                    "ownerId": await self.shop_gid(),
                    "namespace": namespace,
                    "key": key,
                    "type": "json",
                    "value": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                }
            ]
        }
        result = (await self.graphql(mutation, variables))["metafieldsSet"]

        if result["userErrors"]:
            msgs = "; ".join(
                f"{'.'.join(e.get('field') or [])}: {e['message']}" for e in result["userErrors"]
            )
            raise ShopifyError(f"metafieldsSet 실패 — {msgs}")

        return result["metafields"][0]["id"]

    async def delete_shop_metafield(self, namespace: str, key: str) -> None:
        """없으면 조용히 넘어간다 — '지워져 있어야 한다'가 목적이므로 없는 것도 성공이다."""
        mutation = """
        mutation ClearShopMetafield($metafields: [MetafieldIdentifierInput!]!) {
          metafieldsDelete(metafields: $metafields) {
            deletedMetafields { ownerId key }
            userErrors { field message }
          }
        }
        """
        variables = {
            "metafields": [
                {"ownerId": await self.shop_gid(), "namespace": namespace, "key": key}
            ]
        }
        await self.graphql(mutation, variables)

    async def get_shop_metafield(self, namespace: str, key: str) -> dict | None:
        query = """
        query GetShopMetafield($namespace: String!, $key: String!) {
          shop { metafield(namespace: $namespace, key: $key) { value updatedAt } }
        }
        """
        data = await self.graphql(query, {"namespace": namespace, "key": key})
        mf = data["shop"]["metafield"]
        if not mf:
            return None
        return {"value": json.loads(mf["value"]), "updated_at": mf["updatedAt"]}

    # --- 축① 주입 ---------------------------------------------------------------
    async def set_brand_metafield(self, payload: dict) -> str:
        """브랜드 페이로드를 shop.metafields.storeforge.brand 에 넣는다. 반환: metafield GID."""
        return await self.set_shop_metafield(NAMESPACE, KEY, payload)

    async def get_brand_metafield(self) -> dict | None:
        """현재 주입된 값을 읽는다. 온보딩 중복 실행을 막는 근거로 쓴다 (기획안 §1.4)."""
        return await self.get_shop_metafield(NAMESPACE, KEY)

    # --- ListPilot: 상품 등록 ------------------------------------------------------
    #
    # 원본(DW-ListPilot)은 REST /products.json 을 썼지만 상품 REST API 는 폐기 경로다
    # (공개앱 2025-02 / 커스텀앱 2025-04 마감). 기획안 §축② 도 productSet 을 지시한다.
    async def primary_location_gid(self) -> str | None:
        """재고 수량을 넣으려면 로케이션이 필요하다. 없으면 재고 없이 등록한다."""
        data = await self.graphql("{ locations(first: 1) { nodes { id } } }")
        nodes = data["locations"]["nodes"]
        return nodes[0]["id"] if nodes else None

    async def stage_upload(self, filename: str, content_type: str, data: bytes) -> str:
        """이미지 바이트를 Shopify 에 올리고 resourceUrl 을 받는다.

        R2 같은 중간 저장소가 필요 없다 — Shopify 가 직접 받아준다.
        """
        mutation = """
        mutation StageUpload($input: [StagedUploadInput!]!) {
          stagedUploadsCreate(input: $input) {
            stagedTargets {
              url
              resourceUrl
              parameters { name value }
            }
            userErrors { field message }
          }
        }
        """
        variables = {
            "input": [
                {
                    "filename": filename,
                    "mimeType": content_type,
                    "resource": "IMAGE",
                    "httpMethod": "POST",
                }
            ]
        }
        result = (await self.graphql(mutation, variables))["stagedUploadsCreate"]
        if result["userErrors"]:
            raise ShopifyError(
                "stagedUploadsCreate 실패 — "
                + "; ".join(e["message"] for e in result["userErrors"])
            )

        target = result["stagedTargets"][0]
        form = {p["name"]: p["value"] for p in target["parameters"]}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                target["url"],
                data=form,
                files={"file": (filename, data, content_type)},
            )
        if resp.status_code >= 400:
            raise ShopifyError(f"이미지 업로드 실패 (HTTP {resp.status_code})")

        return target["resourceUrl"]

    async def product_set(self, product_input: dict) -> str:
        """상품을 생성/갱신한다. 반환: product GID.

        productSet 은 옵션·변형을 한 번에 넘길 수 있다 (2024-04 이후 productCreate 로는
        변형을 직접 만들 수 없다).
        """
        mutation = """
        mutation ProductSet($input: ProductSetInput!) {
          productSet(synchronous: true, input: $input) {
            product { id handle }
            userErrors { field message code }
          }
        }
        """
        result = (await self.graphql(mutation, {"input": product_input}))["productSet"]

        if result["userErrors"]:
            msgs = "; ".join(
                f"{'.'.join(e.get('field') or [])}: {e['message']}" for e in result["userErrors"]
            )
            raise ShopifyError(f"productSet 실패 — {msgs}")

        return result["product"]["id"]

    # --- Pricewave: 할인 조회 -----------------------------------------------------
    async def active_discounts(self) -> list[dict]:
        """코드 할인 중 지금 살아 있는 것들 (원본 노드 그대로 — 해석은 engine.pricewave 가 한다).

        codeDiscountNodes 는 deprecated 라 discountNodes 를 쓴다.
        """
        query = """
        query ActiveDiscounts {
          discountNodes(first: 50, query: "status:active") {
            nodes {
              id
              discount {
                __typename
                ... on DiscountCodeBasic {
                  title
                  status
                  startsAt
                  endsAt
                  codes(first: 1) { nodes { code } }
                  customerGets {
                    value {
                      __typename
                      ... on DiscountPercentage { percentage }
                      ... on DiscountAmount { amount { amount currencyCode } }
                    }
                  }
                }
              }
            }
          }
        }
        """
        data = await self.graphql(query)
        return data["discountNodes"]["nodes"]
