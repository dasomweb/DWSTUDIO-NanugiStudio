"""ListPilot (축②) — 상품 원본 데이터 → AI 상품 초안 → Shopify 등록.

`dasomweb/DW-ListPilot` 에서 이식했다. 원본과 달라진 점:

  - **DB**: async SQLAlchemy + Alembic → 통합 앱의 sync SQLModel. 자체 Store/OAuth/암호화
    모델은 버렸다 — 통합 앱이 이미 갖고 있고, 두 벌을 두면 자격증명이 두 곳에 생긴다.
  - **Shopify 등록**: REST `/products.json` → GraphQL `productSet`.
    상품 REST API 는 폐기 경로다(2025-02 공개앱 / 2025-04 커스텀앱 마감). 기획안 §축② 도
    `productSet` 을 지시하고 있었다. 그대로 옮겼다면 죽은 코드를 이식하는 셈이었다.
  - **이미지 저장소**: Cloudflare R2 → Shopify staged upload.
    R2 를 쓰면 버킷·공개 URL·수명주기를 우리가 떠안는데, 어차피 이미지의 종착지는 Shopify 다.
    staged upload 는 기획안 §축② 가 지시한 경로이기도 하다. 인프라 의존이 하나 줄었다.

가져오지 않은 것: 바코드 카메라 조회, Gemini 이미지 검색(grounding), 태그 사용 이력.
쓰는 곳이 생기면 그때 붙인다.
"""
