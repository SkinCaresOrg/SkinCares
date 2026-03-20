from itertools import count
from typing import Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

Category = Literal[
    "cleanser",
    "moisturizer",
    "sunscreen",
    "treatment",
    "face_mask",
    "eye_cream",
]

Reaction = Literal["like", "dislike", "irritation"]
SortValue = Literal["price_asc", "price_desc"]

SkinType = Literal[
    "normal",
    "dry",
    "oily",
    "combination",
    "sensitive",
    "not_sure",
]

SensitivityLevel = Literal[
    "very_sensitive",
    "somewhat_sensitive",
    "rarely_sensitive",
    "not_sensitive",
    "not_sure",
]

PriceRange = Literal[
    "budget",
    "affordable",
    "mid_range",
    "premium",
    "no_preference",
]

RoutineSize = Literal["minimal", "basic", "moderate", "extensive"]

IngredientExclusion = Literal[
    "fragrance",
    "alcohol",
    "essential_oils",
    "sulfates",
    "parabens",
]

Concern = Literal[
    "acne",
    "dryness",
    "oiliness",
    "redness",
    "dark_spots",
    "fine_lines",
    "dullness",
    "large_pores",
    "maintenance",
]

ProductInterests = Category


class OnboardingRequest(BaseModel):
    skin_type: SkinType
    concerns: List[Concern] = Field(default_factory=list)
    sensitivity_level: SensitivityLevel
    ingredient_exclusions: List[IngredientExclusion] = Field(default_factory=list)
    price_range: PriceRange
    routine_size: RoutineSize
    product_interests: List[ProductInterests] = Field(default_factory=list)


class OnboardingResponse(BaseModel):
    user_id: str
    profile: OnboardingRequest


class ProductCard(BaseModel):
    product_id: int
    product_name: str
    brand: str
    category: Category
    price: float
    image_url: str
    short_description: str = ""
    rating_count: int = 0
    wishlist_supported: bool = True


class ProductDetail(ProductCard):
    ingredients: List[str] = Field(default_factory=list)
    ingredient_highlights: List[str] = Field(default_factory=list)
    concerns_targeted: List[Concern] = Field(default_factory=list)
    skin_types_supported: List[SkinType] = Field(default_factory=list)


class RecommendationsProduct(ProductCard):
    recommendation_score: float
    explanation: str = ""


class DupeProduct(ProductCard):
    dupe_score: float
    explanation: str = ""


class ProductListResponse(BaseModel):
    products: List[ProductCard]
    total: int


class RecommendationsResponse(BaseModel):
    products: List[RecommendationsProduct]


class DupesResponse(BaseModel):
    source_product_id: int
    dupes: List[DupeProduct]


class FeedbackRequest(BaseModel):
    user_id: str
    product_id: int
    has_tried: bool
    reaction: Optional[Reaction] = None
    reason_tags: List[str] = Field(default_factory=list)
    free_text: Optional[str] = ""

    @model_validator(mode="after")
    def validate_reaction_rules(self) -> "FeedbackRequest":
        if self.has_tried and self.reaction is None:
            raise ValueError("reaction is required when has_tried is true")
        if not self.has_tried:
            self.reaction = None
            self.reason_tags = []
            self.free_text = ""
        return self


class FeedbackResponse(BaseModel):
    success: bool
    message: str


app = FastAPI(title="SkinCares API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PRODUCTS: Dict[int, ProductDetail] = {
    101: ProductDetail(
        product_id=101,
        product_name="Daily Barrier Cream",
        brand="CeraVe",
        category="moisturizer",
        price=18.99,
        image_url="/images/101.jpg",
        short_description="Barrier-supporting daily moisturizer",
        rating_count=124,
        wishlist_supported=True,
        ingredients=["ceramides", "glycerin", "cholesterol"],
        ingredient_highlights=["ceramides", "glycerin"],
        concerns_targeted=["dryness", "redness"],
        skin_types_supported=["dry", "sensitive", "combination"],
    ),
    220: ProductDetail(
        product_id=220,
        product_name="Invisible Daily SPF 50",
        brand="Beauty of Joseon",
        category="sunscreen",
        price=17.50,
        image_url="/images/220.jpg",
        short_description="Lightweight SPF for daily wear",
        rating_count=216,
        wishlist_supported=True,
        ingredients=["rice extract", "niacinamide", "uv filters"],
        ingredient_highlights=["niacinamide"],
        concerns_targeted=["oiliness", "redness", "maintenance"],
        skin_types_supported=["oily", "combination", "sensitive"],
    ),
    305: ProductDetail(
        product_id=305,
        product_name="Light Gel SPF 50",
        brand="Isntree",
        category="sunscreen",
        price=15.00,
        image_url="/images/305.jpg",
        short_description="Hydrating gel sunscreen",
        rating_count=89,
        wishlist_supported=True,
        ingredients=["hyaluronic acid", "uv filters"],
        ingredient_highlights=["hyaluronic acid"],
        concerns_targeted=["dryness", "maintenance"],
        skin_types_supported=["normal", "dry", "combination"],
    ),
}

USER_PROFILES: Dict[str, OnboardingRequest] = {}
USER_ID_COUNTER = count(start=1)
USER_FEEDBACK: List[FeedbackRequest] = []


def _product_to_card(product: ProductDetail) -> ProductCard:
    return ProductCard(**product.model_dump())


@app.post("/api/onboarding", response_model=OnboardingResponse)
def submit_onboarding(payload: OnboardingRequest) -> OnboardingResponse:
    user_id = f"user_{next(USER_ID_COUNTER)}"
    USER_PROFILES[user_id] = payload
    return OnboardingResponse(user_id=user_id, profile=payload)


@app.get("/api/products", response_model=ProductListResponse)
def list_products(
    category: Optional[Category] = None,
    sort: Optional[SortValue] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductListResponse:
    items = [_product_to_card(product) for product in PRODUCTS.values()]

    if category is not None:
        items = [product for product in items if product.category == category]

    if search:
        query = search.lower().strip()
        items = [
            product
            for product in items
            if query in product.product_name.lower() or query in product.brand.lower()
        ]

    if min_price is not None:
        items = [product for product in items if product.price >= min_price]

    if max_price is not None:
        items = [product for product in items if product.price <= max_price]

    if sort == "price_asc":
        items.sort(key=lambda product: product.price)
    elif sort == "price_desc":
        items.sort(key=lambda product: product.price, reverse=True)

    total = len(items)
    paged = items[offset : offset + limit]

    return ProductListResponse(products=paged, total=total)


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: int) -> ProductDetail:
    product = PRODUCTS.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/api/recommendations/{user_id}", response_model=RecommendationsResponse)
def get_recommendations(
    user_id: str,
    category: Optional[Category] = None,
    limit: int = Query(default=12, ge=1, le=100),
) -> RecommendationsResponse:
    if user_id not in USER_PROFILES:
        raise HTTPException(status_code=404, detail="User not found")

    candidates = [product for product in PRODUCTS.values()]
    if category is not None:
        candidates = [product for product in candidates if product.category == category]

    ranked = sorted(candidates, key=lambda product: product.product_id)

    result = [
        RecommendationsProduct(
            **_product_to_card(product).model_dump(),
            recommendation_score=max(0.1, 1.0 - (index * 0.08)),
            explanation=("Matches profile preferences and concern alignment"),
        )
        for index, product in enumerate(ranked[:limit])
    ]

    return RecommendationsResponse(products=result)


@app.get("/api/dupes/{product_id}", response_model=DupesResponse)
def get_dupes(product_id: int) -> DupesResponse:
    source = PRODUCTS.get(product_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Product not found")

    alternatives = [
        product
        for product in PRODUCTS.values()
        if product.product_id != product_id and product.category == source.category
    ]

    dupes = [
        DupeProduct(
            **_product_to_card(product).model_dump(),
            dupe_score=max(0.1, 0.92 - (index * 0.07)),
            explanation="Similar texture and use case at a comparable/lower price",
        )
        for index, product in enumerate(alternatives)
    ]

    return DupesResponse(source_product_id=product_id, dupes=dupes)


@app.post("/api/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    if payload.user_id not in USER_PROFILES:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")

    USER_FEEDBACK.append(payload)

    return FeedbackResponse(success=True, message="Feedback recorded")
