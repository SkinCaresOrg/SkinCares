import csv
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
from typing import Dict, List, Literal, Optional
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

from deployment.api.auth.routes import router as auth_router
from deployment.api.auth.dependencies import get_current_user, get_current_user_optional
from deployment.api.auth.models import User
from deployment.api.db.init_db import init_db
from deployment.api.db.session import SessionLocal, get_db
from deployment.api.feedback.models import QuestionnaireResponse, SwipeEvent
from deployment.api.persistence.models import (
    UserFeedbackEvent,
    UserProfileState,
    WishlistItem,
)

from skincarelib.ml_system.ml_feedback_model import (
    LogisticRegressionFeedback,
    RandomForestFeedback,
    GradientBoostingFeedback,
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
    ingredient_highlights: List[str] = Field(default_factory=list)
    skin_types_supported: List[SkinType] = Field(default_factory=list)


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
    items: List[ProductCard]
    hasMore: bool
    page: int
    products: List[ProductCard] = Field(default_factory=list)
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


class SwipeRequest(BaseModel):
    product_id: int
    direction: Literal["like", "dislike", "irritation", "skip"]


class SwipeResponse(BaseModel):
    swipe_event_id: int
    success: bool


class SwipeQuestionnaireRequest(BaseModel):
    reason_tags: List[str] = Field(default_factory=list)
    free_text: str = ""
    skipped: bool = False


class SwipeQueueResponse(BaseModel):
    products: List[RecommendationsProduct]
    hasMore: bool
    remaining: int


class WishlistResponse(BaseModel):
    items: List[ProductCard]


class WishlistToggleResponse(BaseModel):
    success: bool
    product_id: int


class ChatRequest(BaseModel):
    message: str
    profile: Optional[OnboardingRequest] = None


class ChatResponse(BaseModel):
    response: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
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

# Initialize Supabase for ML monitoring
supabase_client: Optional[Client] = None
if SUPABASE_AVAILABLE:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if supabase_url and supabase_key:
        supabase_client = create_client(supabase_url, supabase_key)
        logger.info("✓ Supabase connected for ML monitoring")
    else:
        logger.warning("⚠ Supabase credentials not found")


# Helper functions for ML monitoring
def log_prediction_to_supabase(
    user_id: str,
    product_id: int,
    predicted_score: float,
    actual_reaction: str,
    model_version: str = "vowpal_wabbit",
) -> bool:
    """Log prediction to Supabase for model evaluation"""
    if not supabase_client:
        return False
    
    try:
        # Determine if prediction was correct
        is_correct = (
            (predicted_score > 0.5 and actual_reaction == "like") or
            (predicted_score <= 0.5 and actual_reaction != "like")
        )
        
        supabase_client.table("model_predictions_audit").insert({
            "user_id": user_id,
            "product_id": product_id,
            "predicted_score": float(predicted_score),
            "actual_reaction": actual_reaction,
            "model_version": model_version,
            "is_correct": is_correct,
        }).execute()
        
        return True
    except Exception as e:
        logger.warning(f"Failed to log prediction: {e}")
        return False


def get_model_metrics_from_supabase() -> Dict:
    """Fetch current model accuracy metrics from Supabase"""
    if not supabase_client:
        return {"error": "Supabase not connected"}
    
    try:
        # Get accuracy by model
        response = supabase_client.table("model_predictions_audit").select(
            "model_version, is_correct"
        ).execute()
        
        if not response.data:
            return {"message": "No predictions logged yet"}
        
        df = pd.DataFrame(response.data)
        metrics = {}
        
        for model_type in df["model_version"].unique():
            model_data = df[df["model_version"] == model_type]
            accuracy = model_data["is_correct"].mean()
            total = len(model_data)
            
            metrics[model_type] = {
                "accuracy": float(accuracy),
                "total_predictions": int(total),
                "correct": int(model_data["is_correct"].sum()),
            }
        
        return metrics
    except Exception as e:
        logger.warning(f"Failed to get metrics: {e}")
        return {"error": str(e)}


# Model selection thresholds (based on data availability patterns)
# These were validated on test users but not A/B tested yet.
# TODO: Fine-tune these based on production metrics.
EARLY_STAGE_THRESHOLD = 5  # Minimum interactions to start using complex models
MID_STAGE_THRESHOLD = 20  # Minimum interactions to use online learning
MAX_ONBOARDING_SEED_LIKES = 40
MAX_ONBOARDING_SEED_DISLIKES = 40
DEBUG_ENDPOINTS_ENABLED = os.getenv("DEBUG_ENDPOINTS_ENABLED", "1").lower() in {
    "1",
    "true",
    "yes",
}

_PRICE_NEGATIVE_TRIGGERS = {"price too high", "too expensive", "expensive"}
_PRICE_POSITIVE_TRIGGERS = {"good value", "great value", "affordable"}
_SKIN_TYPE_POSITIVE_TRIGGERS = {"non irritating", "very gentle", "gentle"}
_INGREDIENT_POSITIVE_TRIGGERS = {
    "hydrating",
    "moisturizing",
    "absorbed well",
    "absorbed quickly",
}
_AVOID_INGREDIENT_TRIGGERS = {
    "contains fragrance": "fragrance",
    "fragrance": "fragrance",
}

_PROFILE_EXCLUSION_TO_INGREDIENT = {
    "fragrance": "fragrance",
    "alcohol": "alcohol",
    "essential_oils": "essential oil",
    "sulfates": "sulfate",
    "parabens": "paraben",
}

_FRONTEND_REASON_TAGS = {
    "hydrated well",
    "absorbed quickly",
    "felt lightweight",
    "non irritating",
    "good value",
    "too greasy",
    "not moisturizing enough",
    "felt sticky",
    "broke me out",
    "price too high",
    "not drying",
    "very gentle",
    "helped oil control",
    "other",
    "made skin dry tight",
    "didnt clean well",
    "irritated skin",
    "skin felt smoother",
    "more hydrated",
    "looked brighter",
    "helped oil acne",
    "smelled bad",
    "burned or stung",
    "too drying",
    "didnt see results",
    "uncomfortable",
    "helped acne",
    "helped dark spots",
    "helped hydration",
    "helped texture",
    "helped wrinkles",
    "didnt work",
    "too strong",
    "improved dryness",
    "improved dark circles",
    "improved puffiness",
    "improved fine lines",
    "improved eye bags",
    "moisturizing",
    "irritated eyes",
    "too heavy",
    "caused bumps",
    "absorbed well",
    "no white cast",
    "left white cast",
    "felt greasy",
    "caused sunburn",
    "burning",
    "stinging",
    "redness",
    "itching",
    "rash",
}

_IRRITANT_KEYWORDS = {
    "fragrance",
    "parfum",
    "alcohol",
    "menthol",
    "limonene",
    "linalool",
    "citral",
    "eugenol",
    "essential oil",
}
_COMEDOGENIC_KEYWORDS = {
    "isopropyl",
    "coconut",
    "lanolin",
    "myristate",
    "oleic",
    "stearic",
    "butter",
    "silicone",
}
_HYDRATION_KEYWORDS = {
    "hyaluronic",
    "glycerin",
    "ceramide",
    "panthenol",
    "squalane",
    "urea",
    "betaine",
}
_BRIGHTENING_KEYWORDS = {
    "niacinamide",
    "vitamin c",
    "ascorb",
    "tranexamic",
    "arbutin",
    "kojic",
    "licorice",
}
_ANTI_AGING_KEYWORDS = {
    "retinol",
    "retinal",
    "peptide",
    "bakuchiol",
    "collagen",
    "adenosine",
}
_SOOTHING_KEYWORDS = {
    "centella",
    "allantoin",
    "madecassoside",
    "bisabolol",
    "oat",
    "chamomile",
    "aloe",
}
_MINERAL_FILTER_KEYWORDS = {"zinc", "titanium", "oxide"}

_HEAVY_OR_GREASY_TAGS = {"too greasy", "felt greasy", "felt sticky", "too heavy"}
_DRYNESS_NEGATIVE_TAGS = {
    "not moisturizing enough",
    "made skin dry tight",
    "too drying",
}
_IRRITATION_NEGATIVE_TAGS = {
    "irritated skin",
    "burned or stung",
    "too strong",
    "irritated eyes",
    "burning",
    "stinging",
    "redness",
    "itching",
    "rash",
    "smelled bad",
    "uncomfortable",
}
_ACNE_NEGATIVE_TAGS = {"broke me out", "caused bumps"}
_LOW_EFFICACY_TAGS = {
    "didnt clean well",
    "didnt see results",
    "didnt work",
    "caused sunburn",
    "left white cast",
}
_HYDRATION_POSITIVE_TAGS = {
    "hydrated well",
    "more hydrated",
    "helped hydration",
    "moisturizing",
    "improved dryness",
    "not drying",
}
_GENTLE_POSITIVE_TAGS = {
    "non irritating",
    "very gentle",
    "absorbed quickly",
    "absorbed well",
    "felt lightweight",
}
_ACNE_POSITIVE_TAGS = {"helped acne", "helped oil acne", "helped oil control"}
_BRIGHTENING_POSITIVE_TAGS = {
    "looked brighter",
    "helped dark spots",
    "improved dark circles",
}
_TEXTURE_POSITIVE_TAGS = {
    "skin felt smoother",
    "helped texture",
    "improved fine lines",
    "helped wrinkles",
    "improved eye bags",
    "improved puffiness",
}
_UV_POSITIVE_TAGS = {"no white cast"}

_EXPLICIT_REASON_TAGS = (
    _HEAVY_OR_GREASY_TAGS
    | _DRYNESS_NEGATIVE_TAGS
    | _IRRITATION_NEGATIVE_TAGS
    | _ACNE_NEGATIVE_TAGS
    | _LOW_EFFICACY_TAGS
    | _HYDRATION_POSITIVE_TAGS
    | _GENTLE_POSITIVE_TAGS
    | _ACNE_POSITIVE_TAGS
    | _BRIGHTENING_POSITIVE_TAGS
    | _TEXTURE_POSITIVE_TAGS
    | _UV_POSITIVE_TAGS
    | {"price too high", "good value", "other", "contains fragrance", "fragrance"}
)

_UNMAPPED_REASON_TAGS = sorted(_FRONTEND_REASON_TAGS - _EXPLICIT_REASON_TAGS)
if _UNMAPPED_REASON_TAGS:
    logger.warning("Unmapped reason tags detected: %s", _UNMAPPED_REASON_TAGS)


def _normalize_phrase(value: str) -> str:
    return value.lower().replace("_", " ").strip()


def _normalize_ingredient_name(value: str) -> Optional[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return normalized or None


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _get_decay(last_seen_at: Optional[str], half_life_days: float = 180.0) -> float:
    if not last_seen_at:
        return 1.0
    parsed = _parse_iso_timestamp(last_seen_at)
    if parsed is None:
        return 1.0
    age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0)
    return float(np.exp(-age_days / half_life_days))


def _product_ingredient_tokens(product: ProductDetail) -> set[str]:
    tokens: set[str] = set()
    for ingredient in product.ingredients:
        normalized = _normalize_ingredient_name(ingredient)
        if not normalized:
            continue
        tokens.add(normalized)
        for token in normalized.split():
            if len(token) >= 3:
                tokens.add(token)
    return tokens


def _product_has_token(product: ProductDetail, token: str) -> bool:
    ingredient_tokens = _product_ingredient_tokens(product)
    return token in ingredient_tokens


def _phrase_matches_any(phrase: str, phrases: set[str]) -> bool:
    return any(candidate in phrase for candidate in phrases)


def _score_bool(flag: bool, present: float = 1.0, absent: float = -0.35) -> float:
    return present if flag else absent


def _product_features(product: ProductDetail) -> dict[str, bool]:
    product_tokens = _product_ingredient_tokens(product)
    product_name_lower = product.product_name.lower()
    brand_lower = product.brand.lower()
    category_lower = product.category.lower()
    combined_text = (
        f"{product_name_lower} {brand_lower} {category_lower} "
        + " ".join(product_tokens)
    )

    price_values = [p.price for p in PRODUCTS.values() if p.price > 0]
    median_price = float(np.median(price_values)) if price_values else 30.0

    return {
        "expensive": product.price > median_price,
        "irritant": _phrase_matches_any(combined_text, _IRRITANT_KEYWORDS),
        "comedogenic": _phrase_matches_any(combined_text, _COMEDOGENIC_KEYWORDS),
        "hydrating": _phrase_matches_any(combined_text, _HYDRATION_KEYWORDS),
        "brightening": _phrase_matches_any(combined_text, _BRIGHTENING_KEYWORDS),
        "anti_aging": _phrase_matches_any(combined_text, _ANTI_AGING_KEYWORDS),
        "soothing": _phrase_matches_any(combined_text, _SOOTHING_KEYWORDS),
        "mineral_filter": _phrase_matches_any(combined_text, _MINERAL_FILTER_KEYWORDS),
        "sunscreen": product.category == "sunscreen" or "spf" in combined_text,
        "lightweight": any(
            marker in combined_text for marker in ["gel", "water", "serum", "fluid"]
        ),
        "heavy": any(
            marker in combined_text
            for marker in ["butter", "oil", "rich", "occlusive", "wax"]
        ),
    }


def _reason_feature_signal(phrase: str, product: ProductDetail) -> float:
    if phrase in {"other"}:
        return 0.0

    features = _product_features(product)
    has_fragrance = _product_has_token(product, "fragrance")

    if phrase in {"contains fragrance", "fragrance"}:
        return _score_bool(has_fragrance)
    if phrase == "price too high":
        return _score_bool(features["expensive"])
    if phrase == "good value":
        return _score_bool(not features["expensive"])

    if phrase in _HEAVY_OR_GREASY_TAGS:
        return _score_bool(features["heavy"] or features["comedogenic"])
    if phrase in _DRYNESS_NEGATIVE_TAGS:
        return _score_bool(not features["hydrating"])
    if phrase in _IRRITATION_NEGATIVE_TAGS:
        return _score_bool(features["irritant"])
    if phrase in _ACNE_NEGATIVE_TAGS:
        return _score_bool(features["comedogenic"] or features["irritant"])
    if phrase in _LOW_EFFICACY_TAGS:
        if phrase == "caused sunburn":
            return _score_bool(not features["sunscreen"])
        if phrase == "left white cast":
            return _score_bool(features["mineral_filter"])
        return _score_bool(not (features["hydrating"] or features["soothing"]))

    if phrase in _HYDRATION_POSITIVE_TAGS:
        return _score_bool(features["hydrating"])
    if phrase in _GENTLE_POSITIVE_TAGS:
        return _score_bool(features["soothing"] or not features["irritant"])
    if phrase in _ACNE_POSITIVE_TAGS:
        return _score_bool(not features["comedogenic"])
    if phrase in _BRIGHTENING_POSITIVE_TAGS:
        return _score_bool(features["brightening"])
    if phrase in _TEXTURE_POSITIVE_TAGS:
        return _score_bool(features["anti_aging"] or features["hydrating"])
    if phrase in _UV_POSITIVE_TAGS:
        return _score_bool(not features["mineral_filter"])

    return 0.0


def _update_user_structured_preferences(
    user_state: UserState,
    reasons: List[str],
    reaction: Optional[str],
) -> None:
    if not reasons or reaction not in {"like", "dislike", "irritation"}:
        return

    if not hasattr(user_state, "avoid_ingredient_last_seen_at"):
        user_state.avoid_ingredient_last_seen_at = {}
    if not hasattr(user_state, "preferred_ingredient_last_seen_at"):
        user_state.preferred_ingredient_last_seen_at = {}
    if not hasattr(user_state, "reason_tag_last_seen_at"):
        user_state.reason_tag_last_seen_at = {}

    now_iso = datetime.now(timezone.utc).isoformat()

    for reason in reasons:
        phrase = _normalize_phrase(reason)
        if not phrase:
            continue

        reason_key = phrase.replace(" ", "_")
        user_state.reason_tag_last_seen_at[reason_key] = now_iso

        if phrase in _AVOID_INGREDIENT_TRIGGERS and reaction in {
            "dislike",
            "irritation",
        }:
            ingredient_key = _AVOID_INGREDIENT_TRIGGERS[phrase]
            user_state.avoid_ingredients[ingredient_key] = (
                user_state.avoid_ingredients.get(ingredient_key, 0.0) + 1.0
            )
            user_state.avoid_ingredient_last_seen_at[ingredient_key] = now_iso

        if phrase in _PRICE_NEGATIVE_TRIGGERS and reaction in {"dislike", "irritation"}:
            user_state.price_sensitivity = min(5.0, user_state.price_sensitivity + 0.5)
        elif phrase in _PRICE_POSITIVE_TRIGGERS and reaction == "like":
            user_state.price_sensitivity = max(
                -5.0, user_state.price_sensitivity - 0.25
            )

        if phrase in _INGREDIENT_POSITIVE_TRIGGERS and reaction == "like":
            user_state.preferred_ingredients[phrase] = (
                user_state.preferred_ingredients.get(phrase, 0.0) + 0.5
            )
            user_state.preferred_ingredient_last_seen_at[phrase] = now_iso


def _compute_reason_adjustment(product: ProductDetail, user_state: UserState) -> float:
    if not user_state.reason_tag_preferences:
        return 0.0

    reason_last_seen = getattr(user_state, "reason_tag_last_seen_at", {}) or {}
    adjustment = 0.0

    for reason_tag, weight in user_state.reason_tag_preferences.items():
        phrase = _normalize_phrase(reason_tag)
        decay = _get_decay(reason_last_seen.get(reason_tag))
        signal = _reason_feature_signal(phrase, product)
        if signal == 0.0:
            continue
        adjustment += float(weight) * 0.08 * signal * decay

    return adjustment


def _compute_structured_adjustment(
    product: ProductDetail,
    user_state: UserState,
    user_profile: OnboardingRequest,
) -> float:
    adjustment = 0.0
    product_tokens = _product_ingredient_tokens(product)

    avoid_last_seen = getattr(user_state, "avoid_ingredient_last_seen_at", {}) or {}
    preferred_last_seen = (
        getattr(user_state, "preferred_ingredient_last_seen_at", {}) or {}
    )

    avoid_keys = set(user_state.avoid_ingredients.keys())
    for ingredient, weight in user_state.avoid_ingredients.items():
        if ingredient in product_tokens:
            decay = _get_decay(avoid_last_seen.get(ingredient))
            adjustment -= min(0.45, 0.18 * float(weight) * decay)

    for ingredient, weight in user_state.preferred_ingredients.items():
        if ingredient in avoid_keys:
            continue
        if ingredient in product_tokens:
            decay = _get_decay(preferred_last_seen.get(ingredient))
            adjustment += min(0.25, 0.05 * float(weight) * decay)

    if (
        "fragrance" in user_profile.ingredient_exclusions
        and "fragrance" in product_tokens
    ):
        adjustment -= 2.0

    return adjustment


def _product_allowed_for_profile(
    product: ProductDetail,
    user_profile: OnboardingRequest,
) -> bool:
    if not user_profile.ingredient_exclusions:
        return True

    product_tokens = _product_ingredient_tokens(product)
    for exclusion in user_profile.ingredient_exclusions:
        token = _PROFILE_EXCLUSION_TO_INGREDIENT.get(exclusion)
        if token and token in product_tokens:
            return False
    return True


def _score_onboarding_match(
    product: ProductDetail, profile: OnboardingRequest
) -> float:
    product_name_lower = product.product_name.lower()
    brand_lower = product.brand.lower()
    category_lower = product.category.lower()
    ingredients_text = " ".join(_product_ingredient_tokens(product))
    text = (
        f"{product_name_lower} {brand_lower} {category_lower} "
        f"{ingredients_text}"
    )
    score = 0.3

    skin_rules = {
        "oily": ["niacinamide", "salicylic", "clay"],
        "dry": ["ceramide", "hyaluronic", "squalane"],
        "sensitive": ["fragrance free", "centella", "aloe"],
        "combination": ["lightweight", "gel", "balanced"],
    }

    for token in skin_rules.get(profile.skin_type, []):
        if token in text:
            score += 0.1

    concern_rules = {
        "acne": ["salicylic", "niacinamide", "acne", "blemish"],
        "dark_spots": ["vitamin c", "niacinamide", "bright"],
        "dryness": ["hyaluronic", "ceramide", "moistur"],
        "fine_lines": ["retinol", "peptide", "firm"],
        "redness": ["centella", "soothing", "calm"],
    }

    for concern in profile.concerns:
        for token in concern_rules.get(concern, []):
            if token in text:
                score += 0.05

    if profile.price_range == "budget" and product.price <= 20:
        score += 0.05
    if profile.price_range == "premium" and product.price >= 40:
        score += 0.05

    return max(0.0, min(1.0, score))


def _score_swipe_preference(
    product: ProductDetail,
    user_state: UserState,
    user_profile: OnboardingRequest,
) -> float:
    if user_state.interactions <= 0:
        return 0.5

    product_index = _build_product_index()
    vec = get_product_vector_safe(product.product_id, product_index)
    if vec is None:
        return 0.5

    score = 0.5
    training_data = user_state.get_training_data()
    if training_data is not None:
        _, y = training_data
        if len(np.unique(y)) >= 2:
            model, _ = get_best_model(user_state)
            model.fit(user_state)
            score = float(model.predict_preference(vec))

    score += _compute_reason_adjustment(product, user_state)
    score += _compute_structured_adjustment(product, user_state, user_profile)
    return max(0.0, min(1.0, score))


def _score_popularity(product: ProductDetail) -> float:
    raw = float(product.rating_count or 0)
    return max(0.0, min(1.0, raw / 1000.0))


def _compute_final_score(
    onboarding_match_score: float,
    swipe_preference_score: float,
    popularity_score: float,
    interactions: int,
) -> float:
    onboarding_weight = 0.4
    swipe_weight = 0.4
    popularity_weight = 0.2

    if interactions > 20:
        onboarding_weight = 0.2
        swipe_weight = 0.6

    return (
        onboarding_match_score * onboarding_weight
        + swipe_preference_score * swipe_weight
        + popularity_score * popularity_weight
    )


def _build_recommendation_explanation(
    product: ProductDetail,
    profile: OnboardingRequest,
    user_state: UserState,
) -> str:
    product_name_lower = product.product_name.lower()
    ingredients_text = " ".join(_product_ingredient_tokens(product))
    text = f"{product_name_lower} {ingredients_text}"
    if profile.skin_type == "oily" and any(
        token in text for token in ["niacinamide", "salicylic"]
    ):
        return "Recommended because it matches your oily-skin ingredient preferences."
    if profile.skin_type == "dry" and any(
        token in text for token in ["ceramide", "hyaluronic", "squalane"]
    ):
        return "Recommended because it supports your dry-skin hydration needs."
    if profile.skin_type == "sensitive" and any(
        token in text for token in ["centella", "aloe", "fragrance free"]
    ):
        return "Recommended because it aligns with your sensitive-skin profile."
    if user_state.liked_count >= 1:
        return "Recommended because it aligns with products you liked."
    return "Recommended based on your onboarding profile."


def _ensure_debug_enabled() -> None:
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


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
            / "products_dataset_processed.csv"
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
PROCESSED_QUESTIONNAIRE_RESPONSE_IDS: set[int] = set()
QUESTIONNAIRE_PIPELINE_STATUS: Dict[str, object] = {
    "startup_replay_processed": 0,
    "startup_replay_skipped": 0,
    "startup_replay_errors": 0,
    "last_run_processed_ids": [],
    "last_run_timestamp": None,
    "last_run_source": None,
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
    return f"user_{uuid4().hex[:12]}"


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
    db.add(
        UserFeedbackEvent(
            user_id=payload.user_id,
            product_id=payload.product_id,
            has_tried=payload.has_tried,
            reaction=payload.reaction,
            reason_tags=payload.reason_tags,
            free_text=payload.free_text or "",
        )
    )


def _load_user_state_from_db(db: Session, user_id: str) -> UserState:
    _ensure_db_initialized()
    user_state = UserState(dim=PRODUCT_VECTORS.shape[1])
    product_index = _build_product_index()

    feedback_rows = (
        db.query(UserFeedbackEvent)
        .filter(UserFeedbackEvent.user_id == user_id)
        .filter(UserFeedbackEvent.has_tried.is_(True))
        .order_by(UserFeedbackEvent.id.asc())
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

        _update_user_structured_preferences(
            user_state,
            reasons=reasons,
            reaction=feedback.reaction,
        )

    USER_STATES[user_id] = user_state
    return user_state


def _replay_questionnaire_feedback_from_db(source: str = "startup") -> dict:
    processed_ids: List[int] = []
    skipped = 0
    errors = 0

    db = SessionLocal()
    try:
        rows = (
            db.query(UserFeedbackEvent)
            .filter(UserFeedbackEvent.has_tried.is_(True))
            .order_by(UserFeedbackEvent.id.asc())
            .all()
        )

        product_index = _build_product_index()
        for row in rows:
            if row.id in PROCESSED_QUESTIONNAIRE_RESPONSE_IDS:
                skipped += 1
                continue

            try:
                state = USER_STATES.get(row.user_id) or _load_user_state_from_db(
                    db, row.user_id
                )
                vec = get_product_vector_safe(row.product_id, product_index)
                if vec is None:
                    skipped += 1
                    PROCESSED_QUESTIONNAIRE_RESPONSE_IDS.add(row.id)
                    continue

                reasons = list(row.reason_tags or [])
                if row.free_text:
                    reasons.append(row.free_text)

                if row.reaction == "like":
                    state.add_liked(vec, reasons=reasons if reasons else None)
                elif row.reaction == "dislike":
                    state.add_disliked(vec, reasons=reasons if reasons else None)
                elif row.reaction == "irritation":
                    state.add_irritation(vec, reasons=reasons if reasons else None)

                _update_user_structured_preferences(
                    state,
                    reasons=reasons,
                    reaction=row.reaction,
                )
                PROCESSED_QUESTIONNAIRE_RESPONSE_IDS.add(row.id)
                processed_ids.append(row.id)
            except Exception:
                errors += 1

        QUESTIONNAIRE_PIPELINE_STATUS["startup_replay_processed"] = int(
            QUESTIONNAIRE_PIPELINE_STATUS.get("startup_replay_processed", 0)
        ) + len(processed_ids)
        QUESTIONNAIRE_PIPELINE_STATUS["startup_replay_skipped"] = (
            int(QUESTIONNAIRE_PIPELINE_STATUS.get("startup_replay_skipped", 0))
            + skipped
        )
        QUESTIONNAIRE_PIPELINE_STATUS["startup_replay_errors"] = (
            int(QUESTIONNAIRE_PIPELINE_STATUS.get("startup_replay_errors", 0)) + errors
        )
        QUESTIONNAIRE_PIPELINE_STATUS["last_run_processed_ids"] = processed_ids
        QUESTIONNAIRE_PIPELINE_STATUS["last_run_timestamp"] = datetime.now(
            timezone.utc
        ).isoformat()
        QUESTIONNAIRE_PIPELINE_STATUS["last_run_source"] = source

        return {
            "processed_response_ids_count": len(PROCESSED_QUESTIONNAIRE_RESPONSE_IDS),
            **QUESTIONNAIRE_PIPELINE_STATUS,
        }
    finally:
        db.close()


def _compute_completion_metrics(db: Session) -> dict:
    total_swipes = db.query(UserFeedbackEvent).count()
    completed = (
        db.query(UserFeedbackEvent)
        .filter(UserFeedbackEvent.has_tried.is_(True))
        .count()
    )
    skipped = total_swipes - completed
    completion_rate = (float(completed) / float(total_swipes)) if total_swipes else 0.0
    return {
        "all_time": {
            "total_swipes": total_swipes,
            "completed_questionnaires": completed,
            "skipped_questionnaires": skipped,
            "completion_rate": completion_rate,
        }
    }


def _compute_outcome_metrics(db: Session) -> dict:
    rows = (
        db.query(UserFeedbackEvent)
        .order_by(UserFeedbackEvent.user_id.asc(), UserFeedbackEvent.id.asc())
        .all()
    )

    per_user: Dict[str, List[UserFeedbackEvent]] = {}
    for row in rows:
        per_user.setdefault(row.user_id, []).append(row)

    after_skipped_samples = 0
    after_skipped_likes = 0
    after_completed_samples = 0
    after_completed_likes = 0

    for user_rows in per_user.values():
        for idx in range(len(user_rows) - 1):
            current = user_rows[idx]
            next_row = user_rows[idx + 1]

            if not next_row.has_tried:
                continue

            if current.has_tried:
                after_completed_samples += 1
                if next_row.reaction == "like":
                    after_completed_likes += 1
            else:
                after_skipped_samples += 1
                if next_row.reaction == "like":
                    after_skipped_likes += 1

    after_skipped_like_rate = (
        float(after_skipped_likes) / float(after_skipped_samples)
        if after_skipped_samples
        else 0.0
    )
    after_completed_like_rate = (
        float(after_completed_likes) / float(after_completed_samples)
        if after_completed_samples
        else 0.0
    )

    absolute_uplift = after_completed_like_rate - after_skipped_like_rate
    relative_uplift = (
        (absolute_uplift / after_skipped_like_rate)
        if after_skipped_like_rate > 0
        else 0.0
    )

    completion = _compute_completion_metrics(db)["all_time"]

    return {
        "overall": completion,
        "cohorts": {
            "after_skipped": {
                "samples": after_skipped_samples,
                "like_rate": after_skipped_like_rate,
            },
            "after_completed": {
                "samples": after_completed_samples,
                "like_rate": after_completed_like_rate,
            },
        },
        "uplift": {
            "absolute_like_rate_uplift": absolute_uplift,
            "relative_like_rate_uplift": relative_uplift,
        },
    }


def _product_to_card(product: ProductDetail) -> ProductCard:
    return ProductCard(**product.model_dump())


def get_best_model(user_state: UserState):
    """
    Select the best model based on user's learning stage and dataset size.

    Adaptive strategy with scaling:
    - Early stage (< 5 interactions): LogisticRegression (fast, lightweight)
    - Mid stage (5-20 interactions): RandomForest (captures complex patterns)
    - Experienced (20-100 interactions): GradientBoosting (better accuracy)
    - Power users (100-500 interactions): LightGBM (optimized for large datasets)
    - Super users (500+ interactions): XLearn FFM (online learning, feature interactions)
    
    Falls back gracefully if advanced models unavailable.
    """
    interactions = user_state.interactions

    try:
        if interactions < EARLY_STAGE_THRESHOLD:  # < 5
            # Early stage: need fast feedback
            return LogisticRegressionFeedback(), "LogisticRegression (Early Stage)"
        elif interactions < MID_STAGE_THRESHOLD:  # 5-20
            # Mid stage: more data available, can handle complexity
            return RandomForestFeedback(), "RandomForest (Mid Stage)"
        elif interactions < 100:  # 20-100
            # Experienced: capture complex nonlinear patterns
            return GradientBoostingFeedback(), "GradientBoosting (Experienced)"
        elif interactions < 500:  # 100-500
            # Power user: LightGBM for large datasets
            from skincarelib.ml_system.ml_feedback_model import LIGHTGBM_AVAILABLE
            if LIGHTGBM_AVAILABLE:
                from skincarelib.ml_system.ml_feedback_model import LightGBMFeedback
                return LightGBMFeedback(), "LightGBM (Power User)"
            else:
                # Fallback to GradientBoosting
                return GradientBoostingFeedback(), "GradientBoosting (Power User - LightGBM unavailable)"
        else:  # 500+
            # Super user: XLearn FFM for ultra-large datasets
            from skincarelib.ml_system.ml_feedback_model import XLEARN_AVAILABLE
            if XLEARN_AVAILABLE:
                from skincarelib.ml_system.ml_feedback_model import XLearnFeedback
                return XLearnFeedback(), "XLearn FFM (Super User)"
            else:
                # Fallback to LightGBM
                from skincarelib.ml_system.ml_feedback_model import LIGHTGBM_AVAILABLE
                if LIGHTGBM_AVAILABLE:
                    from skincarelib.ml_system.ml_feedback_model import LightGBMFeedback
                    return LightGBMFeedback(), "LightGBM (Super User - XLearn unavailable)"
                else:
                    return ContextualBanditFeedback(
                        dim=PRODUCT_VECTORS.shape[1]
                    ), "ContextualBandit (Super User - advanced models unavailable)"
    except Exception as e:
        print(f"Warning selecting advanced model: {e}, falling back to ContextualBandit")
        return ContextualBanditFeedback(
            dim=PRODUCT_VECTORS.shape[1]
        ), "ContextualBandit (Fallback - error in model selection)"


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
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> OnboardingResponse:
    # For tests or anonymous onboarding, generate a temp user_id if not authenticated
    if current_user is None:
        user_id = str(uuid4())
    else:
        user_id = str(current_user.id)
        try:
            current_user.onboarding_completed = True
            db.add(current_user)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Could not persist onboarding profile for user_id=%s", user_id)
            raise HTTPException(
                status_code=500,
                detail="Could not persist onboarding profile",
            ) from exc

    USER_PROFILES[user_id] = payload

    try:
        _save_profile_to_db(db, user_id, payload)
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

    return OnboardingResponse(user_id=user_id, profile=payload)


@app.get("/api/products", response_model=ProductListResponse)
def list_products(
    category: Optional[Category] = None,
    sort: Optional[SortValue] = None,
    search: Optional[str] = None,
    skin_type: Optional[str] = None,
    concern: Optional[str] = None,
    brand: Optional[str] = None,
    ingredient: Optional[str] = None,
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
) -> ProductListResponse:
    limit = min(limit, 50)
    offset = (page - 1) * limit

    items = list(PRODUCTS.values())

    if category is not None:
        items = [product for product in items if product.category == category]

    if search:
        query = search.lower().strip()
        items = [
            product
            for product in items
            if query in product.product_name.lower()
            or query in product.brand.lower()
            or any(query in ing.lower() for ing in product.ingredients)
        ]

    if brand:
        brand_query = brand.lower().strip()
        items = [product for product in items if brand_query in product.brand.lower()]

    if ingredient:
        ingredient_query = ingredient.lower().strip()
        items = [
            product
            for product in items
            if any(ingredient_query in ing.lower() for ing in product.ingredients)
        ]

    if skin_type:
        skin_query = skin_type.lower().strip()
        skin_type_keywords = {
            "oily": ["niacinamide", "salicylic", "clay", "oil control"],
            "dry": ["ceramide", "hyaluronic", "squalane", "hydrat"],
            "sensitive": ["centella", "aloe", "soothing", "fragrance free"],
            "combination": ["lightweight", "gel", "balanced"],
            "normal": ["balance", "daily"],
        }
        keywords = skin_type_keywords.get(skin_query, [])
        if keywords:
            items = [
                product
                for product in items
                if any(
                    keyword
                    in (
                        f"{product.product_name.lower()} {' '.join(i.lower() for i in product.ingredients)}"
                    )
                    for keyword in keywords
                )
            ]

    if concern:
        concern_query = concern.lower().strip()
        concern_keywords = {
            "acne": ["acne", "salicylic", "niacinamide", "blemish"],
            "pigmentation": ["vitamin c", "bright", "dark spot", "niacinamide"],
            "dryness": ["hydrat", "ceramide", "hyaluronic", "squalane"],
            "anti-aging": ["retinol", "peptide", "firm", "wrinkle"],
            "sensitivity": ["soothing", "centella", "aloe", "fragrance free"],
        }
        keywords = concern_keywords.get(concern_query, [])
        if keywords:
            items = [
                product
                for product in items
                if any(
                    keyword
                    in (
                        f"{product.product_name.lower()} {' '.join(i.lower() for i in product.ingredients)}"
                    )
                    for keyword in keywords
                )
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
    has_more = offset + len(paged) < total

    return ProductListResponse(
        items=paged,
        products=paged,
        hasMore=has_more,
        page=page,
        total=total,
    )


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

    user_profile = USER_PROFILES[user_id]
    real_feedback_count = (
        db.query(UserFeedbackEvent)
        .filter(UserFeedbackEvent.user_id == user_id)
        .filter(UserFeedbackEvent.has_tried.is_(True))
        .count()
    )

    user_state = USER_STATES.get(user_id) or _load_user_state_from_db(db, user_id)
    candidates = [product for product in PRODUCTS.values()]
    if category is not None:
        candidates = [product for product in candidates if product.category == category]
    candidates = [
        product
        for product in candidates
        if _product_allowed_for_profile(product, user_profile)
    ]
    if user_state.avoid_ingredients.get("fragrance", 0.0) > 0:
        candidates = [
            product
            for product in candidates
            if not _product_has_token(product, "fragrance")
        ]

    scores: List[float] = []
    for product in candidates:
        onboarding_match_score = _score_onboarding_match(product, user_profile)
        swipe_preference_score = _score_swipe_preference(
            product,
            user_state,
            user_profile,
        )
        popularity_score = _score_popularity(product)
        score = _compute_final_score(
            onboarding_match_score=onboarding_match_score,
            swipe_preference_score=swipe_preference_score,
            popularity_score=popularity_score,
            interactions=user_state.interactions,
        )
        scores.append(score)

    # Sort by score (highest first)
    if real_feedback_count > 0:
        ranked = sorted(
            zip(candidates, scores),
            key=lambda x: (
                x[1],
                ((x[0].product_id * 31 + real_feedback_count) % 997) / 997.0,
            ),
            reverse=True,
        )
    else:
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    result = []
    for product, score in ranked[:limit]:
        rec_product = RecommendationsProduct(
            **_product_to_card(product).model_dump(),
            recommendation_score=score,
            explanation=_build_recommendation_explanation(
                product, user_profile, user_state
            ),
        )
        result.append(rec_product)
        
        # Log recommendation prediction for model monitoring
        try:
            model, model_name = get_best_model(user_state)
            log_prediction_to_supabase(
                user_id=user_id,
                product_id=product.product_id,
                predicted_score=float(score),
                actual_reaction="pending",  # Will be updated when user swipes
                model_version=model_name,
            )
        except Exception as e:
            logger.warning(f"Failed to log prediction for user {user_id}: {e}")

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

                _update_user_structured_preferences(
                    user_state,
                    reasons=reasons,
                    reaction=payload.reaction,
                )
    except Exception as e:
        logger.warning(
            "Could not update ML model state for user_id=%s product_id=%s: %s",
            payload.user_id,
            payload.product_id,
            e,
        )

    return FeedbackResponse(success=True, message="Feedback recorded & model updated")


@app.get("/api/swipe/queue", response_model=SwipeQueueResponse)
def get_swipe_queue(
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SwipeQueueResponse:
    user_id = str(current_user.id)
    if user_id not in USER_PROFILES:
        db_profile = _load_profile_from_db(db, user_id)
        if db_profile is None:
            raise HTTPException(status_code=404, detail="User profile not found")
        USER_PROFILES[user_id] = db_profile

    profile = USER_PROFILES[user_id]
    state = USER_STATES.get(user_id) or _load_user_state_from_db(db, user_id)

    swiped_ids = {
        row.product_id
        for row in db.query(SwipeEvent.product_id)
        .filter(SwipeEvent.user_id == user_id)
        .all()
    }

    candidates = [
        product
        for product in PRODUCTS.values()
        if product.product_id not in swiped_ids
        and _product_allowed_for_profile(product, profile)
    ]

    scored: List[tuple[ProductDetail, float]] = []
    for product in candidates:
        onboarding_match_score = _score_onboarding_match(product, profile)
        swipe_preference_score = _score_swipe_preference(product, state, profile)
        popularity_score = _score_popularity(product)
        final_score = _compute_final_score(
            onboarding_match_score=onboarding_match_score,
            swipe_preference_score=swipe_preference_score,
            popularity_score=popularity_score,
            interactions=state.interactions,
        )
        scored.append((product, final_score))

    scored.sort(key=lambda item: item[1], reverse=True)
    selected = scored[:limit]
    remaining = max(0, len(scored) - len(selected))

    return SwipeQueueResponse(
        products=[
            RecommendationsProduct(
                **_product_to_card(product).model_dump(),
                recommendation_score=score,
                explanation=_build_recommendation_explanation(product, profile, state),
            )
            for product, score in selected
        ],
        hasMore=remaining > 0,
        remaining=remaining,
    )


@app.post("/api/swipe", response_model=SwipeResponse)
def create_swipe_event(
    payload: SwipeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SwipeResponse:
    user_id = str(current_user.id)
    if payload.product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")

    has_tried = payload.direction != "skip"
    reaction: Optional[str] = None if payload.direction == "skip" else payload.direction
    event = SwipeEvent(
        user_id=user_id,
        product_id=payload.product_id,
        has_tried=has_tried,
        reaction=reaction,
        skipped_questionnaire=payload.direction == "skip",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    if payload.direction == "skip":
        feedback_payload = FeedbackRequest(
            user_id=user_id,
            product_id=payload.product_id,
            has_tried=False,
        )
        USER_FEEDBACK.append(feedback_payload)
        _save_feedback_to_db(db, feedback_payload)
        db.commit()

    return SwipeResponse(swipe_event_id=event.id, success=True)


@app.post("/api/swipe/{swipe_event_id}/questionnaire", response_model=FeedbackResponse)
def submit_swipe_questionnaire(
    swipe_event_id: int,
    payload: SwipeQuestionnaireRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse:
    user_id = str(current_user.id)
    event = (
        db.query(SwipeEvent)
        .filter(SwipeEvent.id == swipe_event_id, SwipeEvent.user_id == user_id)
        .first()
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Swipe event not found")

    event.skipped_questionnaire = payload.skipped
    db.add(event)

    response = QuestionnaireResponse(
        swipe_event_id=event.id,
        user_id=user_id,
        product_id=event.product_id,
        reaction=event.reaction or "dislike",
        reason_tags=str(payload.reason_tags),
        free_text=payload.free_text or "",
    )
    db.add(response)

    feedback_payload = FeedbackRequest(
        user_id=user_id,
        product_id=event.product_id,
        has_tried=event.has_tried,
        reaction=(event.reaction if event.has_tried else None),
        reason_tags=payload.reason_tags,
        free_text=payload.free_text,
    )

    USER_FEEDBACK.append(feedback_payload)
    _save_feedback_to_db(db, feedback_payload)
    db.commit()

    if feedback_payload.has_tried and feedback_payload.reaction is not None:
        user_state = USER_STATES.get(user_id) or _load_user_state_from_db(db, user_id)
        product_index = _build_product_index()
        vec = get_product_vector_safe(event.product_id, product_index)
        if vec is not None:
            reasons = feedback_payload.reason_tags or []
            if feedback_payload.free_text:
                reasons = reasons + [feedback_payload.free_text]
            if feedback_payload.reaction == "like":
                user_state.add_liked(vec, reasons=reasons if reasons else None)
            elif feedback_payload.reaction == "dislike":
                user_state.add_disliked(vec, reasons=reasons if reasons else None)
            elif feedback_payload.reaction == "irritation":
                user_state.add_irritation(vec, reasons=reasons if reasons else None)
            _update_user_structured_preferences(
                user_state,
                reasons=reasons,
                reaction=feedback_payload.reaction,
            )
            
            # Log actual user reaction to update model accuracy in Supabase
            try:
                model, model_name = get_best_model(user_state)
                log_prediction_to_supabase(
                    user_id=user_id,
                    product_id=event.product_id,
                    predicted_score=0.5,  # Placeholder (real score would be from recommendation)
                    actual_reaction=feedback_payload.reaction,
                    model_version=model_name,
                )
            except Exception as e:
                logger.warning(f"Failed to log feedback for user {user_id}: {e}")

    return FeedbackResponse(success=True, message="Questionnaire recorded")


@app.get("/api/wishlist", response_model=WishlistResponse)
def get_wishlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistResponse:
    user_id = str(current_user.id)
    rows = (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user_id)
        .order_by(WishlistItem.created_at.desc())
        .all()
    )
    products = []
    for row in rows:
        product = PRODUCTS.get(row.product_id)
        if product is not None:
            products.append(_product_to_card(product))
    return WishlistResponse(items=products)


@app.post("/api/wishlist/{product_id}", response_model=WishlistToggleResponse)
def add_to_wishlist(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistToggleResponse:
    user_id = str(current_user.id)
    if product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user_id, WishlistItem.product_id == product_id)
        .first()
    )
    if existing is None:
        db.add(WishlistItem(user_id=user_id, product_id=product_id))
        db.commit()
    return WishlistToggleResponse(success=True, product_id=product_id)


@app.delete("/api/wishlist/{product_id}", response_model=WishlistToggleResponse)
def remove_from_wishlist(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WishlistToggleResponse:
    user_id = str(current_user.id)
    (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user_id, WishlistItem.product_id == product_id)
        .delete()
    )
    db.commit()
    return WishlistToggleResponse(success=True, product_id=product_id)


@app.get("/api/debug/user-state/{user_id}")
def get_user_debug_state(user_id: str, db: Session = Depends(get_db)) -> dict:
    """Debug endpoint to inspect ML model learning state."""
    _ensure_debug_enabled()
    if user_id not in USER_PROFILES:
        db_profile = _load_profile_from_db(db, user_id)
        if db_profile is None:
            raise HTTPException(status_code=404, detail="User not found")
        USER_PROFILES[user_id] = db_profile

    user_state = USER_STATES.get(user_id) or _load_user_state_from_db(db, user_id)

    real_feedback_rows = (
        db.query(UserFeedbackEvent)
        .filter(UserFeedbackEvent.user_id == user_id)
        .filter(UserFeedbackEvent.has_tried.is_(True))
        .all()
    )

    real_interactions = len(real_feedback_rows)
    real_liked = sum(1 for row in real_feedback_rows if row.reaction == "like")
    real_disliked = sum(1 for row in real_feedback_rows if row.reaction == "dislike")
    real_irritation = sum(
        1 for row in real_feedback_rows if row.reaction == "irritation"
    )

    seeded_interactions = max(0, user_state.interactions - real_interactions)
    seeded_liked = max(0, user_state.liked_count - real_liked)
    seeded_disliked = max(0, user_state.disliked_count - real_disliked)
    seeded_irritation = max(0, user_state.irritation_count - real_irritation)
    reason_signal_count = len(getattr(user_state, "reason_tag_preferences", {}) or {})
    avoid_ingredient_count = len(getattr(user_state, "avoid_ingredients", {}) or {})
    preferred_ingredient_count = len(
        getattr(user_state, "preferred_ingredients", {}) or {}
    )

    return {
        "user_id": user_id,
        "interactions": user_state.interactions,
        "real_interactions": real_interactions,
        "seeded_interactions": seeded_interactions,
        "liked_count": real_liked,
        "disliked_count": real_disliked,
        "irritation_count": real_irritation,
        "seeded_liked_count": seeded_liked,
        "seeded_disliked_count": seeded_disliked,
        "seeded_irritation_count": seeded_irritation,
        "reason_signal_count": reason_signal_count,
        "avoid_ingredient_count": avoid_ingredient_count,
        "preferred_ingredient_count": preferred_ingredient_count,
        "has_training_data": real_interactions >= 2,
        "model_ready": real_liked > 0 and real_disliked > 0,
        "seeded_model_ready": user_state.liked_count > 0
        and user_state.disliked_count > 0,
    }


@app.get("/api/debug/product-score/{user_id}/{product_id}")
def get_product_score(
    user_id: str,
    product_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Debug endpoint to get ML model score for a specific product."""
    _ensure_debug_enabled()
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


@app.get("/api/debug/questionnaire-pipeline-status")
def get_questionnaire_pipeline_status() -> dict:
    _ensure_debug_enabled()
    return {
        **QUESTIONNAIRE_PIPELINE_STATUS,
        "processed_response_ids_count": len(PROCESSED_QUESTIONNAIRE_RESPONSE_IDS),
    }


@app.post("/api/debug/questionnaire-pipeline-replay")
def run_questionnaire_pipeline_replay() -> dict:
    _ensure_debug_enabled()
    return _replay_questionnaire_feedback_from_db(source="manual")


@app.get("/api/debug/questionnaire-completion-metrics")
def get_questionnaire_completion_metrics(db: Session = Depends(get_db)) -> dict:
    _ensure_debug_enabled()
    return _compute_completion_metrics(db)


@app.get("/api/debug/questionnaire-outcome-metrics")
def get_questionnaire_outcome_metrics(db: Session = Depends(get_db)) -> dict:
    _ensure_debug_enabled()
    return _compute_outcome_metrics(db)


# ==================== ML Model Monitoring Endpoints ====================

@app.get("/api/ml/model-metrics")
def get_model_metrics() -> Dict:
    """Get current accuracy and performance metrics for all ML models with availability info"""
    metrics = get_model_metrics_from_supabase()
    
    # Add model availability
    from skincarelib.ml_system.ml_feedback_model import (
        LIGHTGBM_AVAILABLE,
        XLEARN_AVAILABLE,
        VW_AVAILABLE,
    )
    
    metrics["available_models"] = {
        "logistic_regression": True,
        "random_forest": True,
        "gradient_boosting": True,
        "contextual_bandit_vowpal_wabbit": VW_AVAILABLE,
        "lightgbm": LIGHTGBM_AVAILABLE,
        "xlearn_ffm": XLEARN_AVAILABLE,
    }
    
    # Add current time for cache awareness
    from datetime import datetime, timezone
    metrics["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    return metrics


@app.post("/api/ml/log-prediction")
def log_prediction(
    user_id: str,
    product_id: int,
    predicted_score: float,
    actual_reaction: str,
    model_version: str = "vowpal_wabbit",
):
    """Manually log a prediction for evaluation"""
    success = log_prediction_to_supabase(
        user_id, product_id, predicted_score, actual_reaction, model_version
    )
    return {"logged": success}


@app.get("/api/ml/compare-models")
def compare_models_endpoint() -> Dict:
    """Compare performance across all trained models with ranking and metadata"""
    metrics = get_model_metrics_from_supabase()
    
    if "error" in metrics:
        return metrics
    
    # Model metadata for ranking display
    model_metadata = {
        "logistic_regression": {
            "threshold_interactions": 5,
            "description": "Fast & lightweight, early stage",
            "speed": "Fast",
            "memory": "Low",
        },
        "random_forest": {
            "threshold_interactions": 20,
            "description": "Captures patterns, medium stage",
            "speed": "Medium",
            "memory": "Medium",
        },
        "gradient_boosting": {
            "threshold_interactions": 100,
            "description": "Complex patterns, experienced users",
            "speed": "Medium",
            "memory": "Medium",
        },
        "contextual_bandit_vowpal_wabbit": {
            "threshold_interactions": 20,
            "description": "Online learning, real-time updates",
            "speed": "Fast",
            "memory": "Low",
        },
        "lightgbm": {
            "threshold_interactions": 500,
            "description": "Large datasets, power users",
            "speed": "Fast",
            "memory": "Low",
        },
        "xlearn_ffm": {
            "threshold_interactions": 5000,
            "description": "Feature interactions, super users",
            "speed": "Medium",
            "memory": "Medium",
        },
    }
    
    # Rank models by accuracy
    ranked_models = []
    if metrics:
        # Filter out non-model entries
        model_entries = {k: v for k, v in metrics.items() 
                        if k not in ["error", "message", "available_models", "last_updated"]
                        and isinstance(v, dict) and "accuracy" in v}
        
        sorted_models = sorted(
            model_entries.items(),
            key=lambda x: x[1].get("accuracy", 0),
            reverse=True
        )
        
        for rank, (name, data) in enumerate(sorted_models, 1):
            ranked_models.append({
                "rank": rank,
                "name": name,
                "accuracy": float(data.get("accuracy", 0)),
                "total_predictions": int(data.get("total_predictions", 0)),
                "correct_predictions": int(data.get("correct", 0)),
                "metadata": model_metadata.get(name, {}),
            })
        
        best_name = sorted_models[0][0] if sorted_models else None
        best_accuracy = sorted_models[0][1].get("accuracy", 0) if sorted_models else 0
        
        return {
            "all_metrics": metrics,
            "ranked_models": ranked_models,
            "best_model": {
                "name": best_name,
                "accuracy": float(best_accuracy),
                "rank": 1,
            } if best_name else None,
            "summary": {
                "total_models_compared": len(ranked_models),
                "models_with_predictions": len([m for m in ranked_models if m["total_predictions"] > 0]),
                "average_accuracy": float(sum(m["accuracy"] for m in ranked_models) / len(ranked_models)) if ranked_models else 0,
            }
        }
    
    return {
        "message": "No models evaluated yet",
        "ranked_models": [],
        "best_model": None,
        "summary": {
            "total_models_compared": 0,
            "models_with_predictions": 0,
            "average_accuracy": 0,
        }
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Chat endpoint that handles ingredient questions, dupe finding, and recommendations"""
    try:
        response_text = handle_chat(request.message, profile=request.profile)
        return ChatResponse(response=response_text)
    except Exception as e:
        print(f"Chat error: {e}")
        return ChatResponse(response="Sorry, I encountered an error. Please try again.")


app.include_router(auth_router, prefix="/api", tags=["auth"])
