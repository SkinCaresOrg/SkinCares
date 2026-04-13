from __future__ import annotations

import csv
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
    GradientBoostingFeedback,
    ContextualBanditFeedback,
    LightGBMFeedback,
    XLearnFeedback,
    UserState,
    LIGHTGBM_AVAILABLE,
    XLEARN_AVAILABLE,
)
from skincarelib.ml_system.swipe_session import SwipeSession
from skincarelib.ml_system.handler import handle_chat

logger = logging.getLogger(__name__)

# === Debug & Monitoring Flags ===
DEBUG_ENDPOINTS_ENABLED = True  # Can be disabled in production or via tests

# === Structured Reason Tag Triggers ===
# These map frontend reaction tags to backend trigger detection
# Used for creating structured learning signals from user feedback

_PRICE_NEGATIVE_TRIGGERS = (
    "price_too_high",
    "expensive",
    "not worth the price",
    "overpriced",
)

_PRICE_POSITIVE_TRIGGERS = (
    "good_value",
    "worth the price",
    "great deal",
    "affordable",
)

_SKIN_TYPE_POSITIVE_TRIGGERS = (
    "helped with dryness",
    "helped with oiliness",
    "helped with sensitivity",
    "perfect for my skin type",
    "helped with combination skin",
)

_INGREDIENT_POSITIVE_TRIGGERS = (
    "non_irritating",
    "gentle",
    "soothing",
    "hypoallergenic",
    "no fragrance",
)

_AVOID_INGREDIENT_TRIGGERS = {
    "contains_fragrance": "fragrance",
    "contains_alcohol": "alcohol",
    "contains_sulfates": "sulfates",
    "contains_parabens": "parabens",
    "contains_essential_oils": "essential_oils",
}


# === Helper Functions for Questionnaire Pipeline ===

def _normalize_ingredient_name(ingredient: str) -> str:
    """Normalize ingredient names for comparison."""
    return ingredient.lower().strip().replace("_", " ")


def _compute_reason_adjustment(product: ProductDetail, user_state: UserState) -> float:
    """Compute adjustment factor based on reason tags with time decay.
    
    Args:
        product: Product to evaluate
        user_state: User's state with reason preferences and timestamps
        
    Returns:
        Adjustment factor (negative for avoided reasons, positive for preferred)
    """
    if not hasattr(user_state, 'reason_tag_preferences') or not user_state.reason_tag_preferences:
        return 0.0
    
    if not hasattr(product, 'ingredients') or not product.ingredients:
        return 0.0
    
    now = datetime.now(timezone.utc)
    total_adjustment = 0.0
    active_preferences = 0
    
    # Check each reason tag preference
    for reason_tag, preference_strength in user_state.reason_tag_preferences.items():
        if reason_tag not in _AVOID_INGREDIENT_TRIGGERS:
            continue
            
        target_ingredient = _AVOID_INGREDIENT_TRIGGERS[reason_tag].lower()
        
        # Check if any product ingredient matches
        has_match = any(
            target_ingredient in _normalize_ingredient_name(ing)
            for ing in product.ingredients
        )
        
        if not has_match:
            continue
        
        active_preferences += 1
        
        # Apply time decay
        decay_factor = 1.0
        if reason_tag in user_state.reason_tag_last_seen_at:
            try:
                last_seen_str = user_state.reason_tag_last_seen_at[reason_tag]
                last_seen = datetime.fromisoformat(last_seen_str)
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                days_ago = (now - last_seen).days
                # Decay: 0 days = 1.0x, 365 days = 0.1x
                decay_factor = max(0.1, 1.0 - (days_ago / 365.0) * 0.9)
            except (ValueError, AttributeError):
                decay_factor = 1.0
        
        total_adjustment += preference_strength * decay_factor
    
    return total_adjustment if active_preferences > 0 else 0.0


def _compute_structured_adjustment(
    product: ProductDetail,
    user_state: UserState,
    user_profile: OnboardingRequest
) -> float:
    """Compute adjustment factor for structured signals (ingredient avoidance) with time decay.
    
    Args:
        product: Product to evaluate
        user_state: User's state with avoid_ingredients tracking
        user_profile: User's profile with ingredient_exclusions
        
    Returns:
        Adjustment factor (negative for avoided ingredients)
    """
    if not hasattr(product, 'ingredients') or not product.ingredients:
        return 0.0
    
    now = datetime.now(timezone.utc)
    total_adjustment = 0.0
    active_avoids = 0
    
    # Check profile-level ingredient exclusions first (highest priority)
    if hasattr(user_profile, 'ingredient_exclusions') and user_profile.ingredient_exclusions:
        for exclusion in user_profile.ingredient_exclusions:
            exclusion_norm = _normalize_ingredient_name(exclusion)
            has_match = any(
                exclusion_norm in _normalize_ingredient_name(ing)
                for ing in product.ingredients
            )
            if has_match:
                # Profile exclusions override everything
                return -1.0
    
    # Check avoid_ingredients with time decay
    if hasattr(user_state, 'avoid_ingredients') and user_state.avoid_ingredients:
        for ingredient_key, avoidance_strength in user_state.avoid_ingredients.items():
            # Check if any product ingredient matches
            has_match = any(
                ingredient_key in _normalize_ingredient_name(ing)
                or _normalize_ingredient_name(ing) in ingredient_key
                for ing in product.ingredients
            )
            
            if not has_match:
                continue
            
            active_avoids += 1
            
            # Apply time decay
            decay_factor = 1.0
            if hasattr(user_state, 'avoid_ingredient_last_seen_at'):
                if ingredient_key in user_state.avoid_ingredient_last_seen_at:
                    try:
                        last_seen_str = user_state.avoid_ingredient_last_seen_at[ingredient_key]
                        last_seen = datetime.fromisoformat(last_seen_str)
                        if last_seen.tzinfo is None:
                            last_seen = last_seen.replace(tzinfo=timezone.utc)
                        days_ago = (now - last_seen).days
                        # Decay: 0 days = 1.0x, 365 days = 0.1x
                        decay_factor = max(0.1, 1.0 - (days_ago / 365.0) * 0.9)
                    except (ValueError, AttributeError):
                        decay_factor = 1.0
            
            # Strong penalty for matched ingredients (scale: 5 dislikes = ~0.8 penalty before decay)
            penalty = min(0.95, avoidance_strength / 10.0) * decay_factor
            total_adjustment -= penalty
    
    return total_adjustment if active_avoids > 0 else 0.0


def _replay_questionnaire_feedback_from_db() -> dict:
    """Replay questionnaire feedback from database to rebuild user models."""
    global PROCESSED_QUESTIONNAIRE_RESPONSE_IDS, QUESTIONNAIRE_PIPELINE_STATUS
    
    try:
        db = SessionLocal()
        
        # Query UserProductEvent entries that haven't been processed yet
        all_events = db.query(UserProductEvent).all()
        new_event_ids = []
        
        for event in all_events:
            if event.id not in PROCESSED_QUESTIONNAIRE_RESPONSE_IDS:
                PROCESSED_QUESTIONNAIRE_RESPONSE_IDS.add(event.id)
                new_event_ids.append(event.id)
                
                # Try to update user state based on event
                if hasattr(event, 'user_id') and hasattr(event, 'reaction'):
                    user_state = get_user_state(event.user_id)
                    
                    # Update interaction counts based on reaction
                    if event.reaction == "like":
                        user_state.liked_count += 1
                        user_state.interactions += 1
                    elif event.reaction == "dislike":
                        user_state.disliked_count += 1
                        user_state.interactions += 1
                    elif event.reaction == "irritation":
                        user_state.irritation_count += 1
                        user_state.interactions += 1
                    
                    if hasattr(event, 'reason_tags') and event.reason_tags:
                        # Track reason tags with timestamp
                        now = datetime.now(timezone.utc).isoformat()
                        for reason_tag in event.reason_tags:
                            if event.reaction == "like":
                                user_state.reason_tag_preferences[reason_tag] = user_state.reason_tag_preferences.get(reason_tag, 0.0) + 1.0
                            else:
                                user_state.reason_tag_preferences[reason_tag] = user_state.reason_tag_preferences.get(reason_tag, 0.0) - 1.0
                            user_state.reason_tag_last_seen_at[reason_tag] = now
                            user_state.reason_signal_count += 1
                            
                            # Also track avoided ingredients for structured signals
                            if reason_tag in _AVOID_INGREDIENT_TRIGGERS:
                                ingredient_key = _AVOID_INGREDIENT_TRIGGERS[reason_tag].lower()
                                if event.reaction == "dislike" or event.reaction == "irritation":
                                    user_state.avoid_ingredients[ingredient_key] = (
                                        user_state.avoid_ingredients.get(ingredient_key, 0.0) + 1.0
                                    )
                                    user_state.avoid_ingredient_last_seen_at[ingredient_key] = now
        
        QUESTIONNAIRE_PIPELINE_STATUS["startup_replay_processed"] += len(new_event_ids)
        QUESTIONNAIRE_PIPELINE_STATUS["last_run_processed_ids"] = new_event_ids
        
        db.close()
        
    except Exception as e:
        logger.error(f"Error in questionnaire replay: {e}")
        QUESTIONNAIRE_PIPELINE_STATUS["startup_replay_errors"] += 1
    
    return QUESTIONNAIRE_PIPELINE_STATUS


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
    init_db()
    try:
        with SessionLocal() as db:
            _sync_products_table_from_csv(db)
            db.commit()
    except SQLAlchemyError as exc:
        logger.warning("Could not sync products table from CSV: %s", exc)
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
EARLY_STAGE_THRESHOLD = 5  # Minimum interactions to start considering more complex models
MID_STAGE_THRESHOLD = 20  # Mid-stage interaction threshold used by model selection heuristics
LARGE_SCALE_THRESHOLD = 100  # Minimum interactions where large-scale/online-learning models may be selected
ULTRA_LARGE_THRESHOLD = 500  # Minimum interactions where ultra-large-scale advanced models (for example XLearn FFM) may be selected
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
    # Filter PRODUCTS to only include products with available vectors
    MAX_PRODUCT_ID_WITH_VECTOR = len(PRODUCT_VECTORS)
    PRODUCTS = {pid: p for pid, p in PRODUCTS.items() if pid <= MAX_PRODUCT_ID_WITH_VECTOR}
except FileNotFoundError:
    print(f"⚠️  Warning: Product vectors not found at {PRODUCT_VECTORS_PATH}")
    PRODUCT_VECTORS = np.random.randn(len(PRODUCTS), 128).astype(np.float32)

# User sessions for online learning
USER_SESSIONS: Dict[str, SwipeSession] = {}
# User ML model states for generating recommendations
USER_STATES: Dict[str, UserState] = {}
USER_PROFILES: Dict[str, OnboardingRequest] = {}
USER_FEEDBACK: List[FeedbackRequest] = []
USER_LAST_ACTION: Dict[str, Optional[dict]] = {}  # Track last action per user for cohort analysis
DB_INITIALIZED = False

# Questionnaire pipeline tracking
PROCESSED_QUESTIONNAIRE_RESPONSE_IDS: set = set()
QUESTIONNAIRE_PIPELINE_STATUS: Dict = {
    "startup_replay_processed": 0,
    "startup_replay_skipped": 0,
    "startup_replay_errors": 0,
    "last_run_processed_ids": [],
    "last_run_timestamp": None,
    "last_run_source": None,
}
QUESTIONNAIRE_COMPLETION_METRICS: Dict = {
    "total_swipes": 0,
    "completed_questionnaires": 0,
    "skipped_questionnaires": 0,
}
QUESTIONNAIRE_OUTCOME_METRICS: Dict = {
    "cohorts": {
        "after_skipped": {"samples": 0, "like_count": 0, "dislike_count": 0},
        "after_completed": {"samples": 0, "like_count": 0, "dislike_count": 0},
    },
    "uplift": {
        "absolute_like_rate_uplift": 0.0,
        "relative_like_rate_uplift": 0.0,
    }
}


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
    avoid_ingredients = dict(getattr(user_state, "avoid_ingredients", {}) or {})
    avoid_ingredient_last_seen_at = dict(getattr(user_state, "avoid_ingredient_last_seen_at", {}) or {})

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
    row.avoid_ingredients = avoid_ingredients
    row.avoid_ingredient_last_seen_at = avoid_ingredient_last_seen_at


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

    # Restore persisted ingredient preferences from UserModelState
    model_state_row = (
        db.query(UserModelState)
        .filter(UserModelState.user_id == user_id)
        .first()
    )
    if model_state_row:
        user_state.avoid_ingredients = dict(model_state_row.avoid_ingredients or {})
        user_state.avoid_ingredient_last_seen_at = dict(
            model_state_row.avoid_ingredient_last_seen_at or {}
        )

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
    - Large scale (20-100 interactions): GradientBoosting (more complex patterns)
    - Power user (100-500 interactions): LightGBM (very fast, scalable)
    - Ultra-scale (500+): XLearn FFM (optimal for ultra-large datasets)
    - Fallback: ContextualBandit (online learning with exploration)
    """
    interactions = user_state.interactions

    # Try ultra-large scale model first
    if interactions >= ULTRA_LARGE_THRESHOLD and XLEARN_AVAILABLE:
        try:
            return XLearnFeedback(), "XLearn FFM (Ultra-Scale)"
        except Exception:
            pass  # Fall through to next option

    # Try large-scale model
    if interactions >= LARGE_SCALE_THRESHOLD and LIGHTGBM_AVAILABLE:
        try:
            return LightGBMFeedback(), "LightGBM (Power User)"
        except Exception:
            pass  # Fall through to next option

    # Standard progression for typical users
    if interactions < EARLY_STAGE_THRESHOLD:
        # Early stage: need fast feedback (< 5 interactions)
        return LogisticRegressionFeedback(), "LogisticRegression (Early Stage)"
    elif interactions < MID_STAGE_THRESHOLD:
        # Mid stage: more data available, can handle complexity (5-20 interactions)
        return RandomForestFeedback(), "RandomForest (Mid Stage)"
    elif interactions < LARGE_SCALE_THRESHOLD:
        # Growing user: even more data (20-100 interactions)
        return GradientBoostingFeedback(), "GradientBoosting (Growth Stage)"
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
                user_state.add_liked(vec, product_id=product_id)

    # Add unsuitable products as pseudo-dislikes
    if unsuited_products:
        dislike_count = min(
            MAX_ONBOARDING_SEED_DISLIKES,
            max(1, len(unsuited_products) // 20),
        )
        for product_id in unsuited_products[:dislike_count]:
            vec = get_product_vector_safe(product_id, product_index)
            if vec is not None:
                user_state.add_disliked(vec, product_id=product_id)

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
    
    # DEBUG: Log the user_state.interactions
    logger.info(f"[DEBUG] get_recommendations: user_id={user_id}, interactions={user_state.interactions}, from_cache={user_id in USER_STATES}")
    
    candidates = [product for product in PRODUCTS.values()]
    if category is not None:
        candidates = [product for product in candidates if product.category == category]

    # Score products using adaptive/conditional model based on interaction count
    scores = []
    model_name = "default"
    print(f"[DEBUG] Starting scoring: user_state.interactions={user_state.interactions}, liked_count={user_state.liked_count}, disliked_count={user_state.disliked_count}")
    logger.info(f"[DEBUG] Starting scoring: user_state.interactions={user_state.interactions}")
    if user_state.interactions > 0:
        try:
            training_data = user_state.get_training_data()
            print(f"[DEBUG] training_data={training_data is not None}")
            if training_data is None:
                scores = [0.5] * len(candidates)
            else:
                _, y = training_data
                if len(np.unique(y)) < 2:
                    print(f"[SINGLE-CLASS] user {user_id}: y={y}, unique={np.unique(y)}, interactions={user_state.interactions}")
                    # Single class case: use repeated feedback tracking to boost products
                    # This handles early feedback and profile-only scenarios
                    product_index = {
                        p.product_id: i for i, p in enumerate(PRODUCTS.values())
                    }
                    
                    scores = []
                    
                    # Build product-to-count mapping from user state feedback tracking
                    product_like_counts: Dict[int, int] = {}
                    product_dislike_counts: Dict[int, int] = {}
                    
                    if user_state.liked_vectors:
                        # We have liked feedback, but we need to know which product each vector belongs to
                        # Since we don't have product_id directly from vectors, we need to use a different approach
                        # Directly count from user_state's tracked product IDs (includes onboarding seeds + real feedback)
                        for product_id in user_state.liked_product_ids:
                            product_like_counts[product_id] = product_like_counts.get(product_id, 0) + 1
                        
                        logger.info(f"[DEBUG recommend] user {user_id}: liked_product_ids={user_state.liked_product_ids}, counts={product_like_counts}")
                        
                        # Find the mean of all liked vectors
                        mean_vector = np.mean(user_state.liked_vectors, axis=0)
                        preferred_class = 1.0
                    elif user_state.disliked_vectors:
                        # Directly count from user_state's tracked product IDs
                        for product_id in user_state.disliked_product_ids:
                            product_dislike_counts[product_id] = product_dislike_counts.get(product_id, 0) + 1
                        
                        mean_vector = np.mean(user_state.disliked_vectors, axis=0)
                        preferred_class = 0.0
                    else:
                        mean_vector = None
                        preferred_class = 1.0
                    
                    for product in candidates:
                        if mean_vector is not None:
                            vec = get_product_vector_safe(product.product_id, product_index)
                            if vec is not None:
                                # Compute cosine similarity
                                similarity = np.dot(vec, mean_vector) / (
                                    np.linalg.norm(vec) * np.linalg.norm(mean_vector) + 1e-7
                                )
                                # Map similarity to [0, 1]
                                score = (similarity + 1.0) / 2.0
                                
                                # Handle dislike case: penalize similar products, neutral for others
                                if preferred_class == 0.0:
                                    # Penalize products similar to dislikes: scale down similarity scores
                                    # Products with high similarity to dislike mean get low scores
                                    # This ensures disliked types are deprioritized rather than excluded completely
                                    score = 0.3 * score  # Scale similarity down by 70%
                                
                                # Boost score for products with repeated feedback
                                product_feedback_count = product_like_counts.get(product.product_id, 0) or product_dislike_counts.get(product.product_id, 0)
                                if product.product_id in product_like_counts or product.product_id in product_dislike_counts:
                                    logger.info(f"[DEBUG score] product {product.product_id}: feedback_count={product_feedback_count}")
                                if product_feedback_count >= 5:
                                    # Strong boost for products with 5+ feedbacks (user shown clear preference)
                                    # For boost: 5 -> +0.3, 6 -> +0.35, 7 -> +0.4, 8+ -> +0.4
                                    boost = min(0.4, 0.2 + (product_feedback_count - 5) * 0.05)
                                    if preferred_class == 1.0:
                                        # For liked products, use multiplicative boost for low scores
                                        original_score = score
                                        if score < 0.7:
                                            score = min(1.0, score * (1.0 + boost))
                                        else:
                                            score = min(1.0, score + boost)
                                        logger.info(f"[DEBUG BOOST] product {product.product_id}: count={product_feedback_count}, original={original_score:.4f}, boosted={score:.4f}")
                                    else:
                                        # For disliked products, penalize significantly
                                        score = max(0.0, score - boost)
                                
                                # Apply adjustments
                                reason_adjustment = _compute_reason_adjustment(product, user_state)
                                user_profile = USER_PROFILES.get(user_id)
                                if user_profile:
                                    structured_adjustment = _compute_structured_adjustment(
                                        product, user_state, user_profile
                                    )
                                else:
                                    structured_adjustment = 0.0
                                
                                if structured_adjustment < -0.5:
                                    combined_score = 0.0
                                elif structured_adjustment < 0:
                                    combined_score = score * (1.0 + structured_adjustment)
                                else:
                                    combined_score = score + reason_adjustment + structured_adjustment
                                
                                scores.append(max(0.0, min(1.0, combined_score)))
                            else:
                                scores.append(0.5)
                        else:
                            scores.append(0.5)
                else:
                    # Select best model based on learning stage
                    model, model_name = get_best_model(user_state)
                    model.fit(user_state)

                    # Build product_index mapping for safe vector lookup
                    product_index = {
                        p.product_id: i for i, p in enumerate(PRODUCTS.values())
                    }
                    
                    # Build product feedback counts for boost logic
                    product_like_counts: Dict[int, int] = {}
                    product_dislike_counts: Dict[int, int] = {}
                    for product_id in user_state.liked_product_ids:
                        product_like_counts[product_id] = product_like_counts.get(product_id, 0) + 1
                    for product_id in user_state.disliked_product_ids:
                        product_dislike_counts[product_id] = product_dislike_counts.get(product_id, 0) + 1
                    print(f"[DEBUG multi-class] user {user_id}: liked_counts={product_like_counts}, disliked_counts={product_dislike_counts}")

                    for product in candidates:
                        # Get vector for this product using safe mapping
                        vec = get_product_vector_safe(product.product_id, product_index)
                        if vec is not None:
                            score = float(model.predict_preference(vec))
                            
                            # Apply boost for repeated feedback before other adjustments
                            product_feedback_count = product_like_counts.get(product.product_id, 0) or product_dislike_counts.get(product.product_id, 0)
                            if product_feedback_count >= 5:
                                boost = min(0.4, 0.2 + (product_feedback_count - 5) * 0.05)
                                if product_like_counts.get(product.product_id, 0):
                                    # Product with many likes - boost positively
                                    if score < 0.7:
                                        score = min(1.0, score * (1.0 + boost))
                                    else:
                                        score = min(1.0, score + boost)
                                    print(f"[DEBUG BOOST multi] product {product.product_id}: count={product_feedback_count}, boosted_score={score:.4f}")
                                else:
                                    # Product with many dislikes - penalize
                                    score = max(0.0, score - boost)
                            
                            # Apply reason-based and structured adjustments
                            reason_adjustment = _compute_reason_adjustment(product, user_state)
                            user_profile = USER_PROFILES.get(user_id)
                            if user_profile:
                                structured_adjustment = _compute_structured_adjustment(
                                    product, user_state, user_profile
                                )
                            else:
                                structured_adjustment = 0.0
                            
                            # Combine adjustments: structured takes priority with multiplicative effect
                            # If structured is strongly negative (profile exclusion), heavily penalize
                            if structured_adjustment < -0.5:
                                combined_score = 0.0  # Exclude completely
                            elif structured_adjustment < 0:
                                # Moderate penalty: apply as fraction multiplier
                                combined_score = score * (1.0 + structured_adjustment)
                            else:
                                # Apply both additively for positive adjustments
                                combined_score = score + reason_adjustment + structured_adjustment
                            
                            # Clamp to valid range
                            scores.append(max(0.0, min(1.0, combined_score)))
                        else:
                            scores.append(0.5)
        except Exception as e:
            # Fallback to neutral if model fails
            logger.warning(
                "Model error in recommendations for user_id=%s: %s", user_id, e
            )
            scores = [0.5] * len(candidates)
    else:
        # New user with no interactions - still apply profile exclusions
        user_profile = USER_PROFILES.get(user_id)
        scores = []
        for product in candidates:
            base_score = 0.5
            if user_profile:
                structured_adjustment = _compute_structured_adjustment(
                    product, user_state, user_profile
                )
                if structured_adjustment < -0.5:
                    base_score = 0.0  # Exclude completely based on profile
            scores.append(base_score)

    # Sort by score (highest first)
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    # DEBUG: Log scores when interactions > 0
    if user_state.interactions > 0:
        top5 = [(ranked[i][0].product_id, ranked[i][1], ranked[i][0].category) for i in range(min(5, len(ranked)))]
        logger.info(f"[DEBUG] Scores for user_id={user_id}: top5 = {top5}")
        if category:
            cat_ranked = [(r[0].product_id, r[1]) for r in ranked if r[0].category == category]
            logger.info(f"[DEBUG] Category {category}: {len(cat_ranked)} products, top = {cat_ranked[:5]}")

    # Filter out products with 0.0 score (completely excluded)
    # Then take top limit products
    non_excluded = [(product, score) for product, score in ranked if score > 0.0]
    
    result = [
        RecommendationsProduct(
            **_product_to_card(product).model_dump(),
            recommendation_score=score,
            explanation="Personalized based on your feedback"
            if score != 0.5
            else "Matches profile preferences",
        )
        for product, score in non_excluded[:limit]
    ]

    try:
        _log_recommendation_rows(db, user_id, non_excluded[:limit], model_name)
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
        user_state = USER_STATES.get(payload.user_id)
        if user_state is None:
            print(f"[FEEDBACK] Loading user_state from DB for {payload.user_id}")
            user_state = _load_user_state_from_db(db, payload.user_id)
        else:
            print(f"[FEEDBACK] Using cached user_state for {payload.user_id}, has {len(user_state.liked_product_ids)} liked_product_ids")
        if payload.has_tried:
            print(f"[FEEDBACK RECEIVED] user_id={payload.user_id}, product_id={payload.product_id}, reaction={payload.reaction}")
            # Build product_index for this user session
            product_index = _build_product_index()
            # Include reason_tags for richer learning signal
            reasons = payload.reason_tags or []
            if payload.free_text:
                reasons = reasons + [payload.free_text]
            
            vec = get_product_vector_safe(payload.product_id, product_index)
            print(f"[FEEDBACK] vec is {'None' if vec is None else 'available'} for product {payload.product_id}")
            # Track feedback for repeated feedback boost logic, even if vector is missing
            if payload.reaction == "like":
                if vec is not None:
                    user_state.add_liked(vec, product_id=payload.product_id, reasons=reasons if reasons else None)
                else:
                    # Still track the product_id for boost logic, even without vector
                    user_state.liked_product_ids.append(payload.product_id)
                    user_state.interactions += 1
                    user_state.liked_count += 1
                    print(f"[add_liked no-vec] Added product_id={payload.product_id} without vector, now has {len(user_state.liked_product_ids)} likes")
            elif payload.reaction == "dislike":
                if vec is not None:
                    user_state.add_disliked(vec, product_id=payload.product_id, reasons=reasons if reasons else None)
                else:
                    user_state.disliked_product_ids.append(payload.product_id)
                    user_state.interactions += 1
                    user_state.disliked_count += 1
            elif payload.reaction == "irritation":
                if vec is not None:
                    user_state.add_irritation(vec, product_id=payload.product_id, reasons=reasons if reasons else None)
                else:
                    user_state.irritation_product_ids.append(payload.product_id)
                    user_state.interactions += 1
                    user_state.irritation_count += 1
            
            # Update reason tag preferences with time tracking (moved outside if/elif/else)
            now = datetime.now(timezone.utc).isoformat()
            if payload.reason_tags:
                for reason_tag in payload.reason_tags:
                    if payload.reaction == "like":
                        user_state.reason_tag_preferences[reason_tag] = (
                            user_state.reason_tag_preferences.get(reason_tag, 0.0) + 1.0
                        )
                    elif payload.reaction == "dislike" or payload.reaction == "irritation":
                        user_state.reason_tag_preferences[reason_tag] = (
                            user_state.reason_tag_preferences.get(reason_tag, 0.0) - 1.0
                        )
                    user_state.reason_tag_last_seen_at[reason_tag] = now
                    user_state.reason_signal_count += 1
                    
                    # Also track avoided ingredients for structured signals
                    if reason_tag in _AVOID_INGREDIENT_TRIGGERS:
                        ingredient_key = _AVOID_INGREDIENT_TRIGGERS[reason_tag].lower()
                        if payload.reaction == "dislike" or payload.reaction == "irritation":
                            user_state.avoid_ingredients[ingredient_key] = (
                                user_state.avoid_ingredients.get(ingredient_key, 0.0) + 1.0
                            )
                            user_state.avoid_ingredient_last_seen_at[ingredient_key] = now

            _persist_user_model_state(db, payload.user_id, user_state)
            _persist_model_checkpoint(db, payload.user_id, user_state)
            
            # Update in-memory cache so subsequent get_recommendations() calls see the updated state
            USER_STATES[payload.user_id] = user_state
            
            db.commit()
    except Exception as e:
        logger.warning(
            "Could not update ML model state for user_id=%s product_id=%s: %s",
            payload.user_id,
            payload.product_id,
            e,
        )

    # Update questionnaire completion metrics
    QUESTIONNAIRE_COMPLETION_METRICS["total_swipes"] += 1
    if payload.has_tried and payload.reaction:
        QUESTIONNAIRE_COMPLETION_METRICS["completed_questionnaires"] += 1
    if not payload.has_tried:
        QUESTIONNAIRE_COMPLETION_METRICS["skipped_questionnaires"] += 1

    # Update questionnaire outcome cohort metrics
    # Track the cohort this action belongs to based on the previous action
    last_action = USER_LAST_ACTION.get(payload.user_id)
    
    # If this is a second action (after a previous action), track the outcome
    if last_action is not None:
        if last_action.get("has_tried") is False:
            # This action is after a skip, so it's in the "after_skipped" cohort
            QUESTIONNAIRE_OUTCOME_METRICS["cohorts"]["after_skipped"]["samples"] += 1
            if payload.reaction == "like":
                QUESTIONNAIRE_OUTCOME_METRICS["cohorts"]["after_skipped"]["like_count"] += 1
            elif payload.reaction == "dislike":
                QUESTIONNAIRE_OUTCOME_METRICS["cohorts"]["after_skipped"]["dislike_count"] += 1
        elif last_action.get("has_tried") is True and last_action.get("reaction"):
            # This action is after a completed questionnaire, so it's in the "after_completed" cohort
            QUESTIONNAIRE_OUTCOME_METRICS["cohorts"]["after_completed"]["samples"] += 1
            if payload.reaction == "like":
                QUESTIONNAIRE_OUTCOME_METRICS["cohorts"]["after_completed"]["like_count"] += 1
            elif payload.reaction == "dislike":
                QUESTIONNAIRE_OUTCOME_METRICS["cohorts"]["after_completed"]["dislike_count"] += 1
    
    # Update overall metrics from completion metrics
    QUESTIONNAIRE_OUTCOME_METRICS["overall"] = {
        "total_swipes": QUESTIONNAIRE_COMPLETION_METRICS["total_swipes"],
        "completed_questionnaires": QUESTIONNAIRE_COMPLETION_METRICS["completed_questionnaires"],
        "skipped_questionnaires": QUESTIONNAIRE_COMPLETION_METRICS["skipped_questionnaires"],
    }
    
    # Calculate uplift metrics
    after_skipped = QUESTIONNAIRE_OUTCOME_METRICS["cohorts"]["after_skipped"]
    after_completed = QUESTIONNAIRE_OUTCOME_METRICS["cohorts"]["after_completed"]
    
    # Calculate like rates for each cohort
    skip_like_rate = (
        after_skipped["like_count"] / after_skipped["samples"]
        if after_skipped["samples"] > 0 else 0.0
    )
    completed_like_rate = (
        after_completed["like_count"] / after_completed["samples"]
        if after_completed["samples"] > 0 else 0.0
    )
    
    # Calculate uplift
    absolute_uplift = completed_like_rate - skip_like_rate
    relative_uplift = (
        (absolute_uplift / skip_like_rate) if skip_like_rate > 0 else 0.0
    )
    
    QUESTIONNAIRE_OUTCOME_METRICS["uplift"] = {
        "absolute_like_rate_uplift": absolute_uplift,
        "relative_like_rate_uplift": relative_uplift,
    }
    
    # Store this action as the last action for this user
    USER_LAST_ACTION[payload.user_id] = {
        "has_tried": payload.has_tried,
        "reaction": payload.reaction,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

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
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    
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
        "reason_signal_count": user_state.interactions,
        "avoid_ingredient_count": len(user_state.avoided_ingredients),
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
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    
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

    # Check if product was explicitly disliked
    if product_id in user_state.disliked_product_ids:
        # Explicitly disliked product scores near-zero
        score = 0.0001
        model_used = "explicit-dislike"
    # Score using adaptive model based on interaction count
    elif user_state.liked_count > 0 and user_state.disliked_count > 0:
        try:
            # Select best model based on learning stage
            model, model_used = get_best_model(user_state)
            model.fit(user_state)
            score = float(model.predict_preference(product_vector))
        except Exception as e:
            print(f"Error scoring product: {e}")
            score = 0.5
            model_used = "error"
    elif user_state.disliked_count > 0:
        # Single-class dislike-only case: penalize products similar to dislikes
        mean_vector = np.mean(user_state.disliked_vectors, axis=0)
        similarity = np.dot(product_vector, mean_vector) / (
            np.linalg.norm(product_vector) * np.linalg.norm(mean_vector) + 1e-7
        )
        score = (similarity + 1.0) / 2.0
        # Penalize by scaling down - makes similar products score low
        score = 0.3 * score
        model_used = "single-class-dislike"
    elif user_state.liked_count > 0:
        # Single-class like-only case: boost products similar to likes
        mean_vector = np.mean(user_state.liked_vectors, axis=0)
        similarity = np.dot(product_vector, mean_vector) / (
            np.linalg.norm(product_vector) * np.linalg.norm(mean_vector) + 1e-7
        )
        score = (similarity + 1.0) / 2.0
        model_used = "single-class-like"
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


@app.get("/api/debug/questionnaire-pipeline-status")
def debug_questionnaire_status() -> dict:
    """Get questionnaire pipeline status."""
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "processed_response_ids_count": len(PROCESSED_QUESTIONNAIRE_RESPONSE_IDS),
        **QUESTIONNAIRE_PIPELINE_STATUS
    }


@app.get("/api/debug/questionnaire-completion-metrics")
def debug_questionnaire_completion() -> dict:
    """Get questionnaire completion metrics."""
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    total = (QUESTIONNAIRE_COMPLETION_METRICS["completed_questionnaires"] + 
             QUESTIONNAIRE_COMPLETION_METRICS["skipped_questionnaires"])
    completion_rate = (
        QUESTIONNAIRE_COMPLETION_METRICS["completed_questionnaires"] / total
        if total > 0 else 0.0
    )
    return {
        "completion_rate": completion_rate,
        "all_time": {
            "total_swipes": QUESTIONNAIRE_COMPLETION_METRICS["total_swipes"],
            "completed_questionnaires": QUESTIONNAIRE_COMPLETION_METRICS["completed_questionnaires"],
            "skipped_questionnaires": QUESTIONNAIRE_COMPLETION_METRICS["skipped_questionnaires"],
            "completion_rate": completion_rate,
        }
    }


@app.get("/api/debug/questionnaire-outcome-metrics")
def debug_questionnaire_outcome() -> dict:
    """Get questionnaire outcome metrics."""
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    return QUESTIONNAIRE_OUTCOME_METRICS


@app.post("/api/debug/questionnaire-pipeline-replay")
def debug_questionnaire_replay(db: Session = Depends(get_db)) -> dict:
    """Replay questionnaire pipeline from DB."""
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Perform the replay
    _replay_questionnaire_feedback_from_db()
    
    # Update status to indicate manual replay
    QUESTIONNAIRE_PIPELINE_STATUS["last_run_source"] = "manual"
    QUESTIONNAIRE_PIPELINE_STATUS["last_run_timestamp"] = datetime.now(timezone.utc).isoformat()
    
    return {
        "processed_response_ids_count": len(PROCESSED_QUESTIONNAIRE_RESPONSE_IDS),
        "last_run_source": QUESTIONNAIRE_PIPELINE_STATUS["last_run_source"],
        "last_run_timestamp": QUESTIONNAIRE_PIPELINE_STATUS["last_run_timestamp"],
        "last_run_processed_ids": QUESTIONNAIRE_PIPELINE_STATUS["last_run_processed_ids"],
    }


app.include_router(auth_router, prefix="/api", tags=["auth"])
