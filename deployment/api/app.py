import csv
from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
import re
from typing import Dict, List, Literal, Optional
from uuid import UUID as UUIDValue, uuid4

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from deployment.api.auth.models import User
from deployment.api.auth.security import hash_password
from deployment.api.auth.routes import router as auth_router
from deployment.api.db.init_db import init_db
from deployment.api.db.session import SessionLocal, get_db
from deployment.api.persistence.models import (
    ChatMessage,
    ModelCheckpoint,
    Product,
    ProductDupe,
    RecommendationLog,
    UserModelState,
    UserProductEvent,
    UserProfileState,
    UserWishlist,
)

from skincarelib.ml_system.ml_feedback_model import (
    LogisticRegressionFeedback,
    RandomForestFeedback,
    ContextualBanditFeedback,
    UserState,
)
from skincarelib.ml_system.swipe_session import SwipeSession
from skincarelib.ml_system.handler import handle_chat

logger = logging.getLogger(__name__)

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


class ChatRequest(BaseModel):
    user_id: Optional[str] = None
    message: str
    profile: Optional[OnboardingRequest] = None


class ChatResponse(BaseModel):
    response: str


class WishlistRequest(BaseModel):
    user_id: str
    product_id: int


class WishlistResponse(BaseModel):
    products: List[ProductCard]


@asynccontextmanager
async def lifespan(_: FastAPI):
    strict_db_init = os.getenv("DB_INIT_STRICT", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    db_ready = True

    try:
        init_db()
    except Exception as exc:
        db_ready = False
        logger.warning("Database initialization failed during startup: %s", exc)
        if strict_db_init:
            raise

    if db_ready:
        try:
            with SessionLocal() as db:
                _sync_products_table_from_csv(db)
                db.commit()
        except SQLAlchemyError as exc:
            logger.warning("Could not sync products table from CSV: %s", exc)
    else:
        logger.warning("Skipping products table sync because DB is unavailable.")
    yield


app = FastAPI(title="SkinCares API", version="1.0.0", lifespan=lifespan)

DEFAULT_CORS_ALLOW_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://skinscares.es",
    "https://www.skinscares.es",
]


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


raw_cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
extra_cors_origins = [
    _normalize_origin(origin)
    for origin in re.split(r"[,;\s]+", raw_cors_origins)
    if origin.strip()
]
cors_allow_origins = (
    extra_cors_origins
    if extra_cors_origins
    else [_normalize_origin(origin) for origin in DEFAULT_CORS_ALLOW_ORIGINS]
)
allow_all_origins = "*" in cors_allow_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else cors_allow_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Model selection thresholds (based on data availability patterns)
# These were validated on test users but not A/B tested yet.
# TODO: Fine-tune these based on production metrics.
EARLY_STAGE_THRESHOLD = 5  # Minimum interactions to start using complex models
MID_STAGE_THRESHOLD = 20  # Minimum interactions to use online learning
MAX_ONBOARDING_SEED_LIKES = 40
MAX_ONBOARDING_SEED_DISLIKES = 40


def normalize_category(raw_category: str, product_name: str = "") -> Category:
    """Map raw category strings from CSV to Category enum."""
    if not raw_category and not product_name:
        return "treatment"
    lower = raw_category.lower().strip()
    product_lower = product_name.lower().strip()
    combined = f"{lower} {product_lower}"

    if re.search(
        r"\b(spf\s*\d*|sunscreen|sun\s*screen|broad\s*spectrum|uv)\b", combined
    ):
        return "sunscreen"
    if "eye" in lower or "eye" in product_lower:
        return "eye_cream"
    if "mask" in lower or "mask" in product_lower:
        return "face_mask"
    if any(
        keyword in combined
        for keyword in [
            "clean",
            "cleanser",
            "wash",
            "soap",
            "micellar",
            "scrub",
            "exfoliat",
        ]
    ):
        return "cleanser"
    elif any(
        keyword in combined
        for keyword in ["moistur", "cream", "lotion", "balm", "hydrat", "ointment"]
    ):
        return "moisturizer"
    return "treatment"


def load_products_from_csv() -> Dict[int, ProductDetail]:
    """Load products from CSV file."""
    products = {}
    csv_path_env = os.getenv("PRODUCTS_CSV_PATH", "").strip()
    if csv_path_env:
        csv_path = Path(csv_path_env)
    else:
        csv_path = (
            Path(__file__).parent.parent.parent
            / "data"
            / "processed"
            / "products_with_signals.csv"
        )

    if not csv_path.exists():
        print(f"Warning: CSV file not found at {csv_path}")
        return products

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, start=1):
                product_name = row.get("product_name", "").strip()
                brand = row.get("brand", "").strip()

                # Clean product name: remove brand prefix and trim at first comma
                if brand and product_name.lower().startswith(brand.lower()):
                    product_name = product_name[len(brand) :].strip()

                if "," in product_name:
                    product_name = product_name.split(",")[0].strip()

                try:
                    price = float(row.get("price", 0))
                except ValueError:
                    price = 0.0

                usage_type = row.get("usage_type", "")
                category_col = row.get("category", "")
                category_raw = f"{usage_type} {category_col}".strip()
                category = normalize_category(category_raw, product_name=product_name)

                image_url = row.get("image_url", "").strip()

                ingredients = []
                if "ingredients" in row:
                    ing_str = row.get("ingredients", "").strip()
                    if ing_str:
                        ingredients = [
                            ing.strip() for ing in ing_str.split(",") if ing.strip()
                        ]

                product = ProductDetail(
                    product_id=idx,
                    product_name=product_name,
                    brand=brand,
                    category=category,
                    price=price,
                    image_url=image_url,
                    short_description="",
                    rating_count=0,
                    wishlist_supported=True,
                    ingredients=ingredients[:5],  # First 5 ingredients
                    ingredient_highlights=ingredients[:2],  # First 2 as highlights
                    concerns_targeted=[],
                    skin_types_supported=[],
                )
                products[idx] = product
    except Exception as e:
        print(f"Error loading CSV: {e}")

    return products


PRODUCTS = load_products_from_csv()

# Load ML assets
PROJECT_ROOT = Path(__file__).parent.parent.parent
PRODUCT_VECTORS_PATH = PROJECT_ROOT / "artifacts" / "product_vectors.npy"

try:
    PRODUCT_VECTORS = np.load(PRODUCT_VECTORS_PATH, mmap_mode="r")
except FileNotFoundError:
    print(f"⚠️  Warning: Product vectors not found at {PRODUCT_VECTORS_PATH}")
    PRODUCT_VECTORS = np.random.randn(len(PRODUCTS), 128).astype(np.float32)

# User sessions for online learning
USER_SESSIONS: Dict[str, SwipeSession] = {}
# User ML model states for generating recommendations
USER_STATES: Dict[str, UserState] = {}
USER_PROFILES: Dict[str, OnboardingRequest] = {}
USER_FEEDBACK: List[FeedbackRequest] = []
DB_INITIALIZED = False


def get_user_session(user_id: str) -> SwipeSession:
    """Get or create user's learning session."""
    if user_id not in USER_SESSIONS:
        product_metadata = pd.DataFrame(
            [
                {
                    "product_id": str(p.product_id),
                    "product_name": p.product_name,
                    "brand": p.brand,
                    "category": p.category,
                    "price": p.price,
                    "ingredients": ",".join(p.ingredients),
                }
                for p in PRODUCTS.values()
            ]
        )
        product_index = {p.product_id: i for i, p in enumerate(PRODUCTS.values())}

        USER_SESSIONS[user_id] = SwipeSession(
            user_id=user_id,
            product_vectors=PRODUCT_VECTORS,
            product_metadata=product_metadata,
            product_index=product_index,
        )
    return USER_SESSIONS[user_id]


def get_product_vector_safe(
    product_id: int, product_index: Dict[int, int]
) -> Optional[np.ndarray]:
    """Safely get product vector using product_index mapping.

    Args:
        product_id: The user-facing product ID
        product_index: Mapping from product_id to array index

    Returns:
        Product vector or None if not found

    Rationale:
        Using product_index mapping is safer than assuming product_id - 1 alignment.
        This handles any product ID gaps and future schema changes.
    """
    if product_id not in product_index:
        return None
    idx = product_index[product_id]
    if idx < 0 or idx >= len(PRODUCT_VECTORS):
        return None
    return PRODUCT_VECTORS[idx]


def get_user_state(user_id: str) -> UserState:
    """Get or create user's ML model state for recommendations."""
    if user_id not in USER_STATES:
        USER_STATES[user_id] = UserState(dim=PRODUCT_VECTORS.shape[1])
    return USER_STATES[user_id]


def _build_product_index() -> Dict[int, int]:
    return {p.product_id: i for i, p in enumerate(PRODUCTS.values())}


def _ensure_db_initialized() -> None:
    global DB_INITIALIZED
    if DB_INITIALIZED:
        return
    init_db()
    DB_INITIALIZED = True


def _generate_user_id() -> str:
    return str(uuid4())


def _ensure_user_exists(db: Session, user_id: str) -> None:
    _ensure_db_initialized()
    existing = db.query(User).filter(User.id == user_id).first()
    if existing is not None:
        return

    db.add(
        User(
            id=user_id,
            email=f"onboarding+{user_id}@local.test",
            hashed_password=hash_password(uuid4().hex),
        )
    )


def _normalize_optional_user_id(user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    try:
        return str(UUIDValue(user_id))
    except (TypeError, ValueError):
        return None


def _sync_products_table_from_csv(db: Session) -> None:
    _ensure_db_initialized()
    for product in PRODUCTS.values():
        db.merge(
            Product(
                product_id=product.product_id,
                product_name=product.product_name,
                brand=product.brand,
                category=product.category,
                price=product.price,
                image_url=product.image_url,
                ingredients=product.ingredients,
                short_description=product.short_description,
            )
        )


def _persist_user_model_state(db: Session, user_id: str, user_state: UserState) -> None:
    _ensure_db_initialized()
    row = db.query(UserModelState).filter(UserModelState.user_id == user_id).first()
    liked_reasons = list(getattr(user_state, "liked_reasons", []) or [])
    disliked_reasons = list(getattr(user_state, "disliked_reasons", []) or [])
    irritation_reasons = list(getattr(user_state, "irritation_reasons", []) or [])

    if row is None:
        row = UserModelState(user_id=user_id)
        db.add(row)

    row.interactions = int(user_state.interactions)
    row.liked_count = int(user_state.liked_count)
    row.disliked_count = int(user_state.disliked_count)
    row.irritation_count = int(user_state.irritation_count)
    row.liked_reasons = liked_reasons
    row.disliked_reasons = disliked_reasons
    row.irritation_reasons = irritation_reasons


def _persist_model_checkpoint(db: Session, user_id: str, user_state: UserState) -> None:
    _ensure_db_initialized()
    snapshot = {
        "interactions": int(user_state.interactions),
        "liked_count": int(user_state.liked_count),
        "disliked_count": int(user_state.disliked_count),
        "irritation_count": int(user_state.irritation_count),
    }
    db.add(
        ModelCheckpoint(
            user_id=user_id,
            model_type="user_state_snapshot",
            model_blob=json.dumps(snapshot).encode("utf-8"),
            n_updates=int(user_state.interactions),
        )
    )


def _log_recommendation_rows(
    db: Session,
    user_id: str,
    recommendations: List[tuple[ProductDetail, float]],
    model_name: str,
) -> None:
    _ensure_db_initialized()
    for position, (product, score) in enumerate(recommendations, start=1):
        db.add(
            RecommendationLog(
                user_id=user_id,
                product_id=product.product_id,
                model_used=model_name,
                rank_position=position,
                score=float(score),
            )
        )


def _load_dupes_from_db(db: Session, source_product_id: int) -> List[DupeProduct]:
    _ensure_db_initialized()
    rows = (
        db.query(ProductDupe)
        .filter(ProductDupe.source_product_id == source_product_id)
        .order_by(ProductDupe.dupe_score.desc())
        .limit(24)
        .all()
    )
    dupes: List[DupeProduct] = []
    for row in rows:
        product = PRODUCTS.get(row.dupe_product_id)
        if product is None:
            continue
        dupes.append(
            DupeProduct(
                **_product_to_card(product).model_dump(),
                dupe_score=float(row.dupe_score),
                explanation=row.explanation or "",
            )
        )
    return dupes


def _load_profile_from_db(db: Session, user_id: str) -> Optional[OnboardingRequest]:
    _ensure_db_initialized()
    profile_row = (
        db.query(UserProfileState).filter(UserProfileState.user_id == user_id).first()
    )
    if profile_row is None:
        return None
    return OnboardingRequest.model_validate(profile_row.profile)


def _save_profile_to_db(db: Session, user_id: str, payload: OnboardingRequest) -> None:
    _ensure_db_initialized()
    profile_row = (
        db.query(UserProfileState).filter(UserProfileState.user_id == user_id).first()
    )
    profile_data = payload.model_dump()
    if profile_row is None:
        profile_row = UserProfileState(user_id=user_id, profile=profile_data)
        db.add(profile_row)
    else:
        profile_row.profile = profile_data


def _save_feedback_to_db(db: Session, payload: FeedbackRequest) -> None:
    _ensure_db_initialized()

    if payload.has_tried and payload.reaction == "like":
        event_type = "tried_like"
    elif payload.has_tried and payload.reaction == "dislike":
        event_type = "tried_dislike"
    elif payload.has_tried and payload.reaction == "irritation":
        event_type = "tried_irritation"
    elif payload.has_tried:
        event_type = "tried"
    else:
        event_type = "not_tried"

    db.add(
        UserProductEvent(
            user_id=payload.user_id,
            product_id=payload.product_id,
            event_type=event_type,
            has_tried=payload.has_tried,
            reaction=payload.reaction,
            reason_tags=payload.reason_tags,
            free_text=payload.free_text,
            skipped_questionnaire=not payload.has_tried,
        )
    )


def _load_user_state_from_db(db: Session, user_id: str) -> UserState:
    _ensure_db_initialized()
    user_state = UserState(dim=PRODUCT_VECTORS.shape[1])
    product_index = _build_product_index()

    feedback_rows = (
        db.query(UserProductEvent)
        .filter(UserProductEvent.user_id == user_id)
        .filter(UserProductEvent.has_tried.is_(True))
        .order_by(UserProductEvent.id.asc())
        .all()
    )

    for feedback in feedback_rows:
        vec = get_product_vector_safe(feedback.product_id, product_index)
        if vec is None:
            continue

        reasons = list(feedback.reason_tags or [])
        if feedback.free_text:
            reasons.append(feedback.free_text)

        if feedback.reaction == "like":
            user_state.add_liked(vec, reasons=reasons if reasons else None)
        elif feedback.reaction == "dislike":
            user_state.add_disliked(vec, reasons=reasons if reasons else None)
        elif feedback.reaction == "irritation":
            user_state.add_irritation(vec, reasons=reasons if reasons else None)

    USER_STATES[user_id] = user_state
    return user_state


def _product_to_card(product: ProductDetail) -> ProductCard:
    return ProductCard(**product.model_dump())


def get_best_model(user_state: UserState):
    """
    Select the best model based on user's learning stage.

    Strategy:
    - Early stage (< 5 interactions): LogisticRegression (fast, lightweight)
    - Mid stage (5-20 interactions): RandomForest (captures complex patterns)
    - Experienced (20+ interactions): ContextualBandit (online learning, exploration)
    """
    interactions = user_state.interactions

    if interactions < EARLY_STAGE_THRESHOLD:
        # Early stage: need fast feedback (< 5 interactions)
        return LogisticRegressionFeedback(), "LogisticRegression (Early Stage)"
    elif interactions < MID_STAGE_THRESHOLD:
        # Mid stage: more data available, can handle complexity (5-20 interactions)
        return RandomForestFeedback(), "RandomForest (Mid Stage)"
    else:
        # Experienced user: use online learning with exploration
        return ContextualBanditFeedback(
            dim=PRODUCT_VECTORS.shape[1]
        ), "ContextualBandit (Online Learning)"


@app.options("/api/onboarding")
def options_onboarding():
    return {"detail": "OK"}


@app.options("/api/products")
def options_products():
    return {"detail": "OK"}


@app.options("/api/feedback")
def options_feedback():
    return {"detail": "OK"}


def _seed_user_model_from_onboarding(
    user_id: str,
    skin_type: str,
    skin_concerns: List[str],
) -> None:
    """
    Seed user's ML model with pseudo-feedback from onboarding answers.

    Improves Day 1 recommendations by giving the model initial training data
    based on the user's stated skin type and concerns.

    Args:
        user_id: User identifier
        skin_type: User's skin type (dry, oily, sensitive, etc.)
        skin_concerns: List of user's skin concerns (dryness, acne, etc.)
    """
    user_state = get_user_state(user_id)

    if not PRODUCTS:
        return  # No products to seed with

    concerns_lower = [c.lower() for c in skin_concerns]
    suited_products = []
    unsuited_products = []

    # Build product index for vector lookup
    product_index = {p.product_id: i for i, p in enumerate(PRODUCTS.values())}

    # Score products based on metadata match with user's profile
    for product in PRODUCTS.values():
        product_text = (
            f"{product.product_name.lower()} "
            f"{product.category.lower()} "
            f"{product.brand.lower()}"
        )

        # Count matching keywords
        match_count = sum(1 for concern in concerns_lower if concern in product_text)

        # Add bonus for common skincare keywords
        skincare_keywords = {
            "dry": ["hydrat", "moistur", "nourish", "repair"],
            "oily": ["oil control", "matte", "purifying", "sebum"],
            "sensitive": ["gentle", "soothing", "calm", "hypoallergen"],
            "acne": ["acne", "pimple", "blemish", "purifying"],
            "anti-aging": ["anti-aging", "wrinkle", "firming", "collagen"],
        }

        skin_keywords = skincare_keywords.get(skin_type.lower(), [])
        match_count += sum(1 for keyword in skin_keywords if keyword in product_text)

        if match_count > 0:
            suited_products.append((product.product_id, match_count))
        else:
            unsuited_products.append(product.product_id)

    # Add top-matched products as pseudo-likes
    if suited_products:
        suited_products.sort(key=lambda x: x[1], reverse=True)
        top_count = min(MAX_ONBOARDING_SEED_LIKES, max(1, len(suited_products) // 10))

        for product_id, _ in suited_products[:top_count]:
            vec = get_product_vector_safe(product_id, product_index)
            if vec is not None:
                user_state.add_liked(vec)

    # Add unsuitable products as pseudo-dislikes
    if unsuited_products:
        dislike_count = min(
            MAX_ONBOARDING_SEED_DISLIKES,
            max(1, len(unsuited_products) // 20),
        )
        for product_id in unsuited_products[:dislike_count]:
            vec = get_product_vector_safe(product_id, product_index)
            if vec is not None:
                user_state.add_disliked(vec)

    print(
        f"[Onboarding Seeding] user={user_id} skin_type={skin_type} "
        f"concerns={skin_concerns} suited={len(suited_products)} "
        f"unseeded by={len(unsuited_products)}"
    )


@app.post("/api/onboarding", response_model=OnboardingResponse)
def submit_onboarding(
    payload: OnboardingRequest,
    db: Session = Depends(get_db),
) -> OnboardingResponse:
    user_id = _generate_user_id()
    USER_PROFILES[user_id] = payload

    try:
        _ensure_user_exists(db, user_id)
        _save_profile_to_db(db, user_id, payload)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not persist onboarding profile for user_id=%s", user_id)
        raise HTTPException(
            status_code=500,
            detail="Could not persist onboarding profile",
        ) from exc

    # Seed the model with onboarding data
    _seed_user_model_from_onboarding(
        user_id=user_id,
        skin_type=payload.skin_type,
        skin_concerns=payload.concerns,
    )

    try:
        user_state = USER_STATES.get(user_id)
        if user_state is not None:
            _persist_user_model_state(db, user_id, user_state)
            _persist_model_checkpoint(db, user_id, user_state)
            db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning(
            "Could not persist initial model state for user_id=%s: %s", user_id, exc
        )

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
    items = list(PRODUCTS.values())

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
    paged = [_product_to_card(product) for product in items[offset : offset + limit]]

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
    db: Session = Depends(get_db),
) -> RecommendationsResponse:
    if user_id not in USER_PROFILES:
        db_profile = _load_profile_from_db(db, user_id)
        if db_profile is None:
            raise HTTPException(status_code=404, detail="User not found")
        USER_PROFILES[user_id] = db_profile

    user_state = USER_STATES.get(user_id) or _load_user_state_from_db(db, user_id)
    candidates = [product for product in PRODUCTS.values()]
    if category is not None:
        candidates = [product for product in candidates if product.category == category]

    # Score products using adaptive/conditional model based on interaction count
    scores = []
    model_name = "default"
    if user_state.interactions > 0:
        try:
            training_data = user_state.get_training_data()
            if training_data is None:
                scores = [0.5] * len(candidates)
            else:
                _, y = training_data
                if len(np.unique(y)) < 2:
                    scores = [0.5] * len(candidates)
                else:
                    # Select best model based on learning stage
                    model, model_name = get_best_model(user_state)
                    model.fit(user_state)

                    # Build product_index mapping for safe vector lookup
                    product_index = {
                        p.product_id: i for i, p in enumerate(PRODUCTS.values())
                    }

                    for product in candidates:
                        # Get vector for this product using safe mapping
                        vec = get_product_vector_safe(product.product_id, product_index)
                        if vec is not None:
                            score = float(model.predict_preference(vec))
                            scores.append(max(0.1, score))
                        else:
                            scores.append(0.5)
        except Exception as e:
            # Fallback to neutral if model fails
            logger.warning(
                "Model error in recommendations for user_id=%s: %s", user_id, e
            )
            scores = [0.5] * len(candidates)
    else:
        scores = [0.5] * len(candidates)

    # Sort by score (highest first)
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    result = [
        RecommendationsProduct(
            **_product_to_card(product).model_dump(),
            recommendation_score=score,
            explanation="Personalized based on your feedback"
            if score != 0.5
            else "Matches profile preferences",
        )
        for product, score in ranked[:limit]
    ]

    try:
        _log_recommendation_rows(db, user_id, ranked[:limit], model_name)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning(
            "Could not persist recommendation_log rows for user_id=%s: %s",
            user_id,
            exc,
        )

    return RecommendationsResponse(products=result)


@app.get("/api/dupes/{product_id}", response_model=DupesResponse)
def get_dupes(product_id: int, db: Session = Depends(get_db)) -> DupesResponse:
    source = PRODUCTS.get(product_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Product not found")

    db_dupes = _load_dupes_from_db(db, product_id)
    if db_dupes:
        return DupesResponse(source_product_id=product_id, dupes=db_dupes)

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
def submit_feedback(
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    if payload.user_id not in USER_PROFILES:
        db_profile = _load_profile_from_db(db, payload.user_id)
        if db_profile is None:
            raise HTTPException(status_code=404, detail="User not found")
        USER_PROFILES[payload.user_id] = db_profile

    if payload.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")

    USER_FEEDBACK.append(payload)

    try:
        _save_feedback_to_db(db, payload)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "Could not persist feedback event for user_id=%s product_id=%s",
            payload.user_id,
            payload.product_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not persist feedback event",
        ) from exc

    # Update ML model state with new feedback
    try:
        user_state = USER_STATES.get(payload.user_id) or _load_user_state_from_db(
            db, payload.user_id
        )
        if payload.has_tried:
            # Build product_index for this user session
            product_index = _build_product_index()
            vec = get_product_vector_safe(payload.product_id, product_index)
            if vec is not None:
                # Include reason_tags for richer learning signal
                reasons = payload.reason_tags or []
                if payload.free_text:
                    reasons = reasons + [payload.free_text]

                if payload.reaction == "like":
                    user_state.add_liked(vec, reasons=reasons if reasons else None)
                elif payload.reaction == "dislike":
                    user_state.add_disliked(vec, reasons=reasons if reasons else None)
                elif payload.reaction == "irritation":
                    user_state.add_irritation(vec, reasons=reasons if reasons else None)

            _persist_user_model_state(db, payload.user_id, user_state)
            _persist_model_checkpoint(db, payload.user_id, user_state)
            db.commit()
    except Exception as e:
        logger.warning(
            "Could not update ML model state for user_id=%s product_id=%s: %s",
            payload.user_id,
            payload.product_id,
            e,
        )

    return FeedbackResponse(success=True, message="Feedback recorded & model updated")


@app.get("/api/wishlist/{user_id}", response_model=WishlistResponse)
def get_wishlist(user_id: str, db: Session = Depends(get_db)) -> WishlistResponse:
    rows = db.query(UserWishlist).filter(UserWishlist.user_id == user_id).all()
    products = []
    for row in rows:
        product = PRODUCTS.get(row.product_id)
        if product is None:
            continue
        products.append(_product_to_card(product))
    return WishlistResponse(products=products)


@app.post("/api/wishlist", response_model=FeedbackResponse)
def add_to_wishlist(
    payload: WishlistRequest, db: Session = Depends(get_db)
) -> FeedbackResponse:
    if payload.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        db.query(UserWishlist)
        .filter(UserWishlist.user_id == payload.user_id)
        .filter(UserWishlist.product_id == payload.product_id)
        .first()
    )
    if existing is None:
        db.add(UserWishlist(user_id=payload.user_id, product_id=payload.product_id))
        db.commit()
    return FeedbackResponse(success=True, message="Wishlist updated")


@app.delete("/api/wishlist/{user_id}/{product_id}", response_model=FeedbackResponse)
def remove_from_wishlist(
    user_id: str,
    product_id: int,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    row = (
        db.query(UserWishlist)
        .filter(UserWishlist.user_id == user_id)
        .filter(UserWishlist.product_id == product_id)
        .first()
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return FeedbackResponse(success=True, message="Wishlist updated")


@app.get("/api/debug/user-state/{user_id}")
def get_user_debug_state(user_id: str, db: Session = Depends(get_db)) -> dict:
    """Debug endpoint to inspect ML model learning state."""
    if user_id not in USER_PROFILES:
        db_profile = _load_profile_from_db(db, user_id)
        if db_profile is None:
            raise HTTPException(status_code=404, detail="User not found")
        USER_PROFILES[user_id] = db_profile

    user_state = USER_STATES.get(user_id) or _load_user_state_from_db(db, user_id)

    return {
        "user_id": user_id,
        "interactions": user_state.interactions,
        "liked_count": user_state.liked_count,
        "disliked_count": user_state.disliked_count,
        "irritation_count": user_state.irritation_count,
        "has_training_data": user_state.interactions >= 2,
        "model_ready": user_state.liked_count > 0 and user_state.disliked_count > 0,
    }


@app.get("/api/debug/product-score/{user_id}/{product_id}")
def get_product_score(
    user_id: str,
    product_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Debug endpoint to get ML model score for a specific product."""
    if user_id not in USER_PROFILES:
        db_profile = _load_profile_from_db(db, user_id)
        if db_profile is None:
            raise HTTPException(status_code=404, detail="User not found")
        USER_PROFILES[user_id] = db_profile

    if product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")

    user_state = USER_STATES.get(user_id) or _load_user_state_from_db(db, user_id)
    product_data = PRODUCTS[product_id]

    # Get product vector using safe mapping
    product_index = {p.product_id: i for i, p in enumerate(PRODUCTS.values())}
    product_vector = get_product_vector_safe(product_id, product_index)
    if product_vector is None:
        raise HTTPException(status_code=400, detail="Product vector not found")

    # Score using adaptive model based on interaction count
    if user_state.liked_count > 0 and user_state.disliked_count > 0:
        try:
            # Select best model based on learning stage
            model, model_used = get_best_model(user_state)
            model.fit(user_state)
            score = float(model.predict_preference(product_vector))
        except Exception as e:
            print(f"Error scoring product: {e}")
            score = 0.5
            model_used = "error"
    else:
        score = 0.5  # Neutral score if not enough training data
        model_used = "default"

    return {
        "user_id": user_id,
        "product_id": product_id,
        "product_name": product_data.product_name,
        "score": score,
        "model_used": model_used,
        "training_data_available": user_state.liked_count > 0
        and user_state.disliked_count > 0,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Chat endpoint that handles ingredient questions, dupe finding, and recommendations"""
    try:
        normalized_user_id = _normalize_optional_user_id(request.user_id)
        response_text = handle_chat(request.message, profile=request.profile)
        try:
            db.add(
                ChatMessage(
                    user_id=normalized_user_id,
                    role="user",
                    content=request.message,
                )
            )
            db.add(
                ChatMessage(
                    user_id=normalized_user_id,
                    role="assistant",
                    content=response_text,
                )
            )
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.warning("Could not persist chat_messages row(s): %s", exc)
        return ChatResponse(response=response_text)
    except Exception as e:
        print(f"Chat error: {e}")
        return ChatResponse(response="Sorry, I encountered an error. Please try again.")


app.include_router(auth_router, prefix="/api", tags=["auth"])
