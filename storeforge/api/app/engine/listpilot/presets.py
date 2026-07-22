"""업종별 상품 타입·태그 축 프리셋 (DW-ListPilot `services/product_type.py` 이식).

Gemini 가 뱉은 힌트를 이 프리셋에 맞춰 정규화한다. 프리셋에 없는 값이 오면 버리지 않고
정규화만 해서 쓴다 — 새 업종·새 카테고리를 만날 때마다 코드를 고치게 만들면 안 된다.
"""

from __future__ import annotations

INDUSTRY_PRESETS: dict[str, dict] = {
    "fashion": {
        "product_types": [
            "Tops", "Bottoms", "Dresses", "Outerwear", "Activewear",
            "Swimwear", "Underwear", "Sleepwear", "Suits", "Jumpsuits",
        ],
        "tag_axes": {
            "category": ["tops", "bottoms", "dresses", "outerwear", "activewear"],
            "material": ["cotton", "linen", "polyester", "wool", "silk", "denim", "leather"],
            "season": ["spring25", "summer25", "aw25", "fw25"],
            "style": ["casual", "minimal", "streetwear", "formal", "bohemian"],
            "target": ["women", "men", "unisex", "kids"],
            "color": ["black", "white", "navy", "beige", "grey", "red", "green"],
            "promo": ["sale", "new-arrival", "bestseller", "limited"],
        },
    },
    "footwear": {
        "product_types": [
            "Sneakers", "Boots", "Sandals", "Heels", "Flats",
            "Loafers", "Athletic", "Slippers", "Oxfords",
        ],
        "tag_axes": {
            "category": ["sneakers", "boots", "sandals", "heels", "loafers"],
            "material": ["leather", "suede", "canvas", "mesh", "rubber"],
            "season": ["spring25", "summer25", "aw25", "fw25"],
            "target": ["women", "men", "unisex", "kids"],
            "promo": ["sale", "new-arrival", "bestseller"],
        },
    },
    "accessories": {
        "product_types": [
            "Bags", "Jewelry", "Hats", "Scarves", "Belts",
            "Sunglasses", "Watches", "Wallets", "Backpacks",
        ],
        "tag_axes": {
            "category": ["bags", "jewelry", "hats", "scarves", "belts", "sunglasses"],
            "material": ["leather", "canvas", "metal", "fabric", "plastic"],
            "style": ["casual", "luxury", "minimal", "statement"],
            "target": ["women", "men", "unisex"],
            "promo": ["sale", "new-arrival", "gift"],
        },
    },
    "beauty": {
        "product_types": [
            "Moisturizer", "Serum", "Cleanser", "Sunscreen",
            "Toner", "Makeup", "Hair Care", "Body Care", "Supplements",
        ],
        "tag_axes": {
            "category": ["skincare", "makeup", "haircare", "bodycare"],
            "skin_type": ["dry", "oily", "combination", "sensitive", "all"],
            "benefit": ["hydrating", "brightening", "anti-aging", "acne-care"],
            "ingredient": ["hyaluronic-acid", "niacinamide", "retinol", "vitamin-c"],
            "promo": ["sale", "new-arrival", "bestseller"],
        },
    },
    "electronics": {
        "product_types": [
            "Smartphones", "Laptops", "Tablets", "Audio",
            "Wearables", "Accessories", "Cameras", "Gaming",
        ],
        "tag_axes": {
            "category": ["phones", "computers", "audio", "wearables", "accessories"],
            "brand": [],
            "compatible": [],
            "promo": ["sale", "new-arrival", "refurbished"],
        },
    },
}

INDUSTRIES = tuple(INDUSTRY_PRESETS)
DEFAULT_INDUSTRY = "fashion"
