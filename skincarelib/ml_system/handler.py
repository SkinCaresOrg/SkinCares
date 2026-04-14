import os
import time
from pathlib import Path
import requests
from typing import Optional, Dict, Any

from skincarelib.ml_system.intent import detect_intent
from skincarelib.models.dupe_finder import find_dupes, get_artifacts
from skincarelib.models.recommender_ranker import recommend

METADATA = None

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_ARTIFACTS: list[tuple[str, Path]] = [
    ("feature_schema.json", ROOT / "artifacts" / "feature_schema.json"),
    ("product_index.json", ROOT / "artifacts" / "product_index.json"),
    ("product_vectors.npy", ROOT / "artifacts" / "product_vectors.npy"),
    ("tfidf.joblib", ROOT / "artifacts" / "tfidf.joblib"),
    ("manifest.json", ROOT / "artifacts" / "manifest.json"),
]

OPTIONAL_ARTIFACTS: list[tuple[str, Path]] = [
    ("faiss.index", ROOT / "artifacts" / "faiss.index"),
]

REQUIRED_DATASETS: list[tuple[str, Path]] = [
    (
        "products_with_signals.csv",
        ROOT / "data" / "processed" / "products_with_signals.csv",
    ),
]


def _build_asset_url(
    supabase_url: str,
    bucket: str,
    prefix: str,
    remote_rel_path: str,
    public_bucket: bool,
) -> str:
    clean_base = supabase_url.rstrip("/")
    clean_prefix = prefix.strip("/")
    remote_part = remote_rel_path.strip("/")
    object_path = f"{clean_prefix}/{remote_part}" if clean_prefix else remote_part

    if public_bucket:
        return f"{clean_base}/storage/v1/object/public/{bucket}/{object_path}"
    return f"{clean_base}/storage/v1/object/{bucket}/{object_path}"


def _download_file(
    url: str,
    destination: Path,
    headers: dict[str, str],
    timeout_sec: int,
    retries: int = 3,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        response = requests.get(url, headers=headers, timeout=timeout_sec, stream=True)
        if response.status_code == 200:
            with destination.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output_file.write(chunk)
            return

        if attempt >= retries:
            raise RuntimeError(f"HTTP {response.status_code} downloading {url}")
        time.sleep(min(2**attempt, 5))


def _download_assets(
    items: list[tuple[str, Path]],
    *,
    supabase_url: str,
    bucket: str,
    prefix: str,
    public_bucket: bool,
    headers: dict[str, str],
    timeout_sec: int,
    required: bool,
) -> bool:
    all_ok = True
    for remote_rel, local_path in items:
        if local_path.exists():
            continue

        asset_url = _build_asset_url(
            supabase_url=supabase_url,
            bucket=bucket,
            prefix=prefix,
            remote_rel_path=remote_rel,
            public_bucket=public_bucket,
        )
        try:
            _download_file(
                url=asset_url,
                destination=local_path,
                headers=headers,
                timeout_sec=timeout_sec,
            )
        except Exception:
            all_ok = False
            if required:
                break

    return all_ok


def load_artifacts(force: bool = False) -> Dict[str, Any]:
    """Ensure required artifacts/datasets exist locally, downloading from Supabase when needed."""
    required_files = REQUIRED_ARTIFACTS + REQUIRED_DATASETS
    missing_required = [path for _, path in required_files if not path.exists()]

    if not force and not missing_required:
        return {
            "ok": True,
            "downloaded": False,
            "missing": [],
            "artifacts": {
                name: str(path)
                for name, path in REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS
            },
            "datasets": {name: str(path) for name, path in REQUIRED_DATASETS},
        }

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    if not supabase_url:
        return {
            "ok": False,
            "downloaded": False,
            "missing": [str(path) for path in missing_required],
            "error": "SUPABASE_URL is not set for artifact download.",
            "artifacts": {
                name: str(path)
                for name, path in REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS
            },
            "datasets": {name: str(path) for name, path in REQUIRED_DATASETS},
        }

    supabase_key = os.getenv("SUPABASE_KEY", "").strip()
    artifacts_bucket = os.getenv(
        "SUPABASE_ARTIFACTS_BUCKET", "skincares-artifacts"
    ).strip()
    datasets_bucket = os.getenv(
        "SUPABASE_DATASETS_BUCKET", "skincares-datasets"
    ).strip()
    artifacts_prefix = os.getenv("SUPABASE_ARTIFACTS_PREFIX", "v2").strip()
    datasets_prefix = os.getenv("SUPABASE_DATASETS_PREFIX", "v2").strip()
    timeout_sec = int(os.getenv("SUPABASE_DOWNLOAD_TIMEOUT", "120"))
    public_bucket = os.getenv("SUPABASE_ASSETS_PUBLIC", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }

    headers: dict[str, str] = {}
    if not public_bucket:
        if not supabase_key:
            return {
                "ok": False,
                "downloaded": False,
                "missing": [str(path) for path in missing_required],
                "error": "SUPABASE_KEY is required for private bucket download.",
                "artifacts": {
                    name: str(path)
                    for name, path in REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS
                },
                "datasets": {name: str(path) for name, path in REQUIRED_DATASETS},
            }
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }

    artifacts_ok = _download_assets(
        REQUIRED_ARTIFACTS,
        supabase_url=supabase_url,
        bucket=artifacts_bucket,
        prefix=artifacts_prefix,
        public_bucket=public_bucket,
        headers=headers,
        timeout_sec=timeout_sec,
        required=True,
    )
    if not artifacts_ok:
        return {
            "ok": False,
            "downloaded": True,
            "missing": [
                str(path) for _, path in REQUIRED_ARTIFACTS if not path.exists()
            ],
            "error": "Could not download required artifacts from Supabase.",
            "artifacts": {
                name: str(path)
                for name, path in REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS
            },
            "datasets": {name: str(path) for name, path in REQUIRED_DATASETS},
        }

    _download_assets(
        OPTIONAL_ARTIFACTS,
        supabase_url=supabase_url,
        bucket=artifacts_bucket,
        prefix=artifacts_prefix,
        public_bucket=public_bucket,
        headers=headers,
        timeout_sec=timeout_sec,
        required=False,
    )

    datasets_ok = _download_assets(
        REQUIRED_DATASETS,
        supabase_url=supabase_url,
        bucket=datasets_bucket,
        prefix=datasets_prefix,
        public_bucket=public_bucket,
        headers=headers,
        timeout_sec=timeout_sec,
        required=True,
    )
    if not datasets_ok:
        return {
            "ok": False,
            "downloaded": True,
            "missing": [
                str(path) for _, path in REQUIRED_DATASETS if not path.exists()
            ],
            "error": "Could not download required datasets from Supabase.",
            "artifacts": {
                name: str(path)
                for name, path in REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS
            },
            "datasets": {name: str(path) for name, path in REQUIRED_DATASETS},
        }

    missing_after = [str(path) for _, path in required_files if not path.exists()]
    if missing_after:
        return {
            "ok": False,
            "downloaded": True,
            "missing": missing_after,
            "error": "Artifacts download completed but files are still missing.",
            "artifacts": {
                name: str(path)
                for name, path in REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS
            },
            "datasets": {name: str(path) for name, path in REQUIRED_DATASETS},
        }

    return {
        "ok": True,
        "downloaded": True,
        "missing": [],
        "artifacts": {
            name: str(path) for name, path in REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS
        },
        "datasets": {name: str(path) for name, path in REQUIRED_DATASETS},
    }


def _get_metadata():
    global METADATA
    if METADATA is None:
        load_artifacts()
        _, _, _, METADATA = get_artifacts()
        if "product_name" not in METADATA.columns and "name" in METADATA.columns:
            METADATA["product_name"] = METADATA["name"]
    return METADATA


# Initialize OpenAI client lazily (only when needed)
_client = None


def _find_product_id(product_name: str):
    product_name = product_name.lower().strip()
    metadata = _get_metadata().copy()
    name_col = "product_name" if "product_name" in metadata.columns else "name"

    STOPWORDS = {
        "cream",
        "cleanser",
        "moisturizer",
        "serum",
        "lotion",
        "gel",
        "face",
        "skin",
        "care",
    }

    query_words = [w for w in product_name.split() if w not in STOPWORDS]

    def score(row):
        text = f"{row[name_col]} {row['brand']}".lower()

        matched = 0

        for word in query_words:
            if word in text:
                matched += 1

        # 🚨 HARD RULE: ALL important words must match
        if matched == 0:
            return -100  # reject completely

        score = matched * 3

        if product_name in text:
            score += 10

        return score

    metadata["match_score"] = metadata.apply(score, axis=1)  # ← ADD THIS BACK
    matches = metadata.sort_values("match_score", ascending=False)

    if matches.empty:
        return None

    best = matches.iloc[0]

    if best["match_score"] < 3:
        return None

    return best["product_id"]


def _get_profile_field(profile, field, default):
    if not profile:
        return default
    if isinstance(profile, dict):
        return profile.get(field, default)
    return getattr(profile, field, default)


def get_openai_client():
    """Get OpenAI client, only if openai package is installed and API key is set."""
    global _client
    if _client is None and os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI

            _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        except ImportError:
            print("Warning: openai package not installed. Skipping OpenAI integration.")
            return None
    return _client


def query_ollama(message: str, profile: Optional[Dict[str, Any]] = None) -> str:
    """Query local Ollama instance running on localhost:11434"""
    try:
        context = ""
        if profile:
            skin_type = _get_profile_field(profile, "skin_type", "")
            concerns = _get_profile_field(profile, "concerns", [])
            if skin_type or concerns:
                context = f" The user has {skin_type} skin and is concerned about {', '.join(concerns)}."

        prompt = f"You are a helpful skincare expert. Answer this question briefly (1-2 sentences):{context} {message}"

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7,
            },
            timeout=30,
        )

        if response.status_code == 200:
            return response.json().get("response", "").strip()
        return None
    except Exception as e:
        print(f"Ollama error: {e}")
        return None


def handle_chat(
    message: str,
    profile: Optional[Dict[str, Any]] = None,
    last_intent: Optional[str] = None,
):
    msg_lower = message.lower().strip()

    # 1. QUICK HANDLING (safe things only)
    if msg_lower in ["yes", "yeah", "y", "ok", "sure"]:
        if last_intent == "recommend":
            return (
                "Great 🙂 What category are you interested in? (moisturizer, cleanser, serum)",
                last_intent,
            )

    if any(greet in msg_lower for greet in ["hi", "hello", "hey"]):
        last_intent = "greeting"

        fallback = _smart_fallback(message, profile)

        return (
            fallback if fallback else "I'm not sure how to help with that yet."
        ), last_intent

    # 2. HARD RULES (only true garbage filtering)
    if len(msg_lower) < 4 or not any(c.isalpha() for c in msg_lower):
        return (
            "I didn’t quite get that 😅\n\n"
            "You can ask things like:\n"
            "• 'What is niacinamide?'\n"
            "• 'Find a dupe for CeraVe cleanser'\n"
            "• 'What should I use for acne?'\n"
        ), last_intent
    if any(
        q in msg_lower
        for q in [
            "where can i find",
            "how do i find",
            "how can i find",
            "how do i get",
            "how can i get",
            "where do i get",
            "how to get",
        ]
    ):
        if "recommend" in msg_lower or "routine" in msg_lower:
            return (
                "You can get personalized products by clicking on FOR YOU at the top of your screen and filling out our quick skin quiz when you create your account to get tailored recommendations",
                last_intent,
            )
        if "dupe" in msg_lower or "alternative" in msg_lower:
            return (
                "You can find product dupes by clicking on the product you want to find a dupe for, scroll and click on the ✨dupe button.",
                last_intent,
            )

    intent = detect_intent(message)

    if intent == "recommend":
        last_intent = "recommend"
    elif intent in ["dupe", "info"]:
        last_intent = intent

    # 4. HANDLE INTENTS FIRST (🔥 THIS FIXES YOUR BUG)

    # 4. HANDLE INTENTS FIRST

    if intent == "dupe":
        return handle_dupe(message, profile), last_intent

    elif intent == "info":
        return handle_info(message, profile), last_intent

    elif intent == "recommend" or last_intent == "recommend":
        SKIN_TYPES = ["oily", "dry", "sensitive", "combination", "normal"]
        detected_skin = next((s for s in SKIN_TYPES if s in msg_lower), None)

        # if user just answered skin type with no category, ask for category
        if detected_skin and not any(
            cat in msg_lower for cat in ["moisturizer", "cleanser", "serum"]
        ):
            skin_type = detected_skin
            return (
                "What category are you interested in? (moisturizer, cleanser, serum)",
                last_intent,
            )
        if any(cat in msg_lower for cat in ["moisturizer", "cleanser", "serum"]):
            category = next(
                cat for cat in ["moisturizer", "cleanser", "serum"] if cat in msg_lower
            )

            category = category.lower().strip()

            skin_type = _get_profile_field(profile, "skin_type", "")

            # ✅ ADD THIS BLOCK HERE
            SKIN_TYPES = ["oily", "dry", "sensitive", "combination", "normal"]

            detected_skin = next((s for s in SKIN_TYPES if s in msg_lower), None)

            if detected_skin:
                skin_type = detected_skin

            # 🔥 ADD THIS CHECK RIGHT AFTER
            if not skin_type:
                return (
                    "What’s your skin type? (oily, dry, combination, sensitive, normal)",
                    last_intent,
                )

            CATEGORY_MAP = {
                "moisturizer": ["moisturizer"],
                "cleanser": ["cleanser"],
                "serum": ["treatment", "serum"],
            }

            mapped_categories = CATEGORY_MAP.get(category, [])

            results = recommend(
                liked_product_ids=[],
                explicit_prefs={
                    "skin_type": skin_type,
                    "preferred_categories": mapped_categories,
                    "budget": 50,
                },
                constraints={"budget": 50},
                top_n=3,
            )

            if results is None or results.empty:
                return f"I couldn't find {category} recommendations 😕", last_intent

            metadata = _get_metadata()

            skin_text = f"{skin_type} " if skin_type else ""
            response = (
                f"Here are some {category} recommendations for {skin_text}skin:\n"
            )

            for _, row in results.iterrows():
                product_id = row["product_id"]

                product_info = metadata[metadata["product_id"] == product_id]

                if not product_info.empty:
                    product_info = product_info.iloc[0]
                    name = product_info.get("product_name", "Unknown")
                    brand = product_info.get("brand", "Unknown")
                    price = product_info.get("price", "?")
                else:
                    name, brand, price = "Unknown", "Unknown", "?"

                response += f"- {name} by {brand} (${price})\n"

            return response, last_intent

        # 🔗 LINK HANDLING (VERY IMPORTANT FOR UX)

        if any(
            q in msg_lower
            for q in ["how do i get", "how can i get", "where do i get", "how to get"]
        ):
            if "recommend" in msg_lower or "routine" in msg_lower:
                return (
                    "You can get personalized recommendations by filling out our quick skin quiz here:\n"
                    "👉 [recommendation page link]"
                ), last_intent

            if "dupe" in msg_lower or "alternative" in msg_lower:
                return (
                    "You can find product dupes using our dupe finder here:\n"
                    "👉 [dupe finder link]"
                ), last_intent

        # If we are still in recommendation flow → guide user
        if last_intent == "recommend":
            return (
                "What category are you interested in? (moisturizer, cleanser, serum)",
                last_intent,
            )

        else:
            return handle_ai_fallback(message, profile), last_intent

    else:  # ← THIS, at the same level as the if/elif above
        return handle_ai_fallback(message, profile), last_intent


def handle_dupe(message: str, profile=None) -> str:
    msg = message.lower()

    # 🔹 extract product name
    product_name = (
        msg.replace("dupe for", "")
        .replace("dupe", "")
        .replace("similar to", "")
        .replace("similar", "")
        .replace("alternative to", "")
        .replace("alternative", "")
        .strip()
    )

    if not product_name:
        return "Tell me which product you want a dupe for 🙂"

    try:
        # 🔹 STEP 1: find product
        product_id = _find_product_id(product_name)

        # 🔥 STEP 2: fallback → suggestions
        if not product_id:
            metadata = (
                _get_metadata().copy()
            )  # copy to avoid mutating the shared singleton
            name_col = "product_name" if "product_name" in metadata.columns else "name"
            STOPWORDS = {"cream", "cleanser", "moisturizer", "serum", "lotion", "gel"}

            # 🔹 smarter scoring
            def loose_score(row):
                text = f"{row[name_col]} {row['brand']}".lower()
                return sum(
                    word in text
                    for word in product_name.split()
                    if word not in STOPWORDS
                )

            metadata["loose_score"] = metadata.apply(loose_score, axis=1)

            suggestions = metadata.sort_values("loose_score", ascending=False).head(3)

            if suggestions.empty:
                return f"I couldn't find '{product_name}' 😕"

            # 🔹 extract meaningful keywords
            keywords_used = [w for w in product_name.split() if w not in STOPWORDS]

            keywords_str = ", ".join(keywords_used) if keywords_used else product_name

            # 🔹 category hint
            if "cream" in product_name:
                category_hint = "creams"
            elif "cleanser" in product_name:
                category_hint = "cleansers"
            elif "serum" in product_name:
                category_hint = "serums"
            else:
                category_hint = "products"

            # 🔹 response
            response = f"I couldn't find '{product_name}' in our dataset 😕\n"
            response += f"But here are similar {category_hint} based on keywords like {keywords_str}:\n"

            for _, row in suggestions.iterrows():
                response += f"- {row[name_col]} by {row['brand']} (${row['price']})\n"

            return response

        # 🔹 STEP 4: find dupes
        results = find_dupes(product_id)

        if "product_name" not in results.columns and "name" in results.columns:
            results = results.rename(columns={"name": "product_name"})

        if results.empty:
            return "No cheaper dupes found 😢"

        # 🔹 STEP 5: build response
        response = f"Here are dupes for {product_name}:\n"
        for _, row in results.head(3).iterrows():
            response += f"- {row['product_name']} by {row['brand']} (${row['price']})\n"

        return response

    except Exception:
        return "Something went wrong while finding dupes"


def handle_recommend(message: str, profile: Optional[Dict[str, Any]] = None) -> str:
    skin_type = _get_profile_field(profile, "skin_type", "your")
    concerns = _get_profile_field(profile, "concerns", [])
    concerns_str = ", ".join(concerns) if concerns else "skin concerns"

    response = f"Based on your {skin_type} skin and {concerns_str}, I'd recommend checking out our personalized products. "
    response += "Would you like recommendations for a specific category like moisturizer, cleanser, or treatment?"

    return response


def handle_info(message: str, profile: Optional[Dict[str, Any]] = None) -> str:
    """Handle ingredient and skincare information requests."""
    ingredient = (
        message.replace("what is", "")
        .replace("tell me about", "")
        .replace("info about", "")
        .strip()
    )
    if ingredient.endswith("?"):
        ingredient = ingredient[:-1].strip()

    ingredient_lower = ingredient.lower()

    ingredient_info = {
        "niacinamide": "Niacinamide (Vitamin B3) is a water-soluble vitamin that helps regulate sebum production, improves skin barrier function, and reduces redness. Great for all skin types, especially oily and combination skin.",
        "hyaluronic acid": "Hyaluronic Acid is a humectant that attracts and retains moisture from the environment into the skin. It can hold up to 1000x its weight in water, making it excellent for hydration.",
        "retinol": "Retinol is a form of Vitamin A that promotes cell turnover and collagen production. It helps reduce fine lines, wrinkles, and improves skin texture. Use SPF during the day as it increases sun sensitivity.",
        "salicylic acid": "Salicylic Acid is a beta-hydroxy acid (BHA) that exfoliates inside pores. It's excellent for oily and acne-prone skin. It helps unclog pores and reduce breakouts.",
        "glycolic acid": "Glycolic Acid is an alpha-hydroxy acid (AHA) that exfoliates the skin surface. It helps improve skin texture, reduces fine lines, and brightens the complexion.",
        "ceramides": "Ceramides are lipids that form the skin barrier. They help trap moisture and protect against irritants. Essential for anyone with a compromised or dry skin barrier.",
        "vitamin c": "Vitamin C (Ascorbic Acid) is an antioxidant that brightens skin, reduces hyperpigmentation, and boosts collagen production. It provides protection against environmental damage.",
    }

    for key, value in ingredient_info.items():
        if key in ingredient_lower:
            personalized_tip = ""
            if profile:
                skin_type = _get_profile_field(profile, "skin_type", "")
                concerns = _get_profile_field(profile, "concerns", [])

                if key == "retinol" and "fine_lines" in concerns:
                    personalized_tip = (
                        " For your fine line concerns, retinol is an excellent choice!"
                    )
                elif key == "salicylic acid" and (
                    "acne" in concerns or skin_type == "oily"
                ):
                    personalized_tip = " Perfect for your skin type and concerns!"
                elif key == "hyaluronic acid" and skin_type == "dry":
                    personalized_tip = " This is especially great for your dry skin!"
                elif key == "niacinamide" and skin_type == "oily":
                    personalized_tip = " An ideal ingredient for your oily skin!"

            return value + personalized_tip

    return (
        f"That's an interesting ingredient! I don't have specific information about {ingredient} "
        "in my database, but I'd recommend checking product labels and consulting with a dermatologist for personalized advice."
    )


def handle_ai_fallback(message: str, profile: Optional[Dict[str, Any]] = None) -> str:
    """Handle general skincare questions using Ollama (local) or OpenAI. Last resort only."""
    ollama_response = query_ollama(message, profile)
    if ollama_response:
        return ollama_response

    client = get_openai_client()

    if client:
        try:
            context = ""
            if profile:
                context = f"The user has {_get_profile_field(profile, 'skin_type', '')} skin and concerns: {', '.join(_get_profile_field(profile, 'concerns', []))}."

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a helpful skincare expert assistant. {context} Keep responses concise (1-2 sentences).",
                    },
                    {"role": "user", "content": message},
                ],
                temperature=0.7,
                max_tokens=150,
            )

            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI error: {e}")

    return _smart_fallback(message, profile)


def _smart_fallback(message: str, profile: Optional[Any] = None) -> str:
    """Smart fallback responses based on keywords and patterns, personalized with user profile"""
    message_lower = message.lower().strip()

    skin_type = _get_profile_field(profile, "skin_type", "")
    concerns = _get_profile_field(profile, "concerns", [])

    # Greetings
    if message_lower in [
        "hi",
        "hello",
        "hey",
        "greetings",
        "hiya",
        "what's up",
        "whats up",
    ]:
        return (
            "Hi there! 👋 I’m here to help you find dupes and product recommendations tailored to your skin.\n\n"
            "Want a personalized product recommendation?\n"
            "👉 Take our skin quiz\n\n"
            "Looking for a cheaper alternative to a product?\n"
            "👉 Try our dupe finder\n\n"
            "Or just ask me directly:\n"
            "• 'Recommend a moisturizer for oily skin'\n"
            "• 'Find a dupe for CeraVe cleanser'\n"
            "• 'What is niacinamide?'\n\n"
            "I’m here to help 🙂"
        )
    # Dry skin
    if any(word in message_lower for word in ["dry", "dehydrated"]):
        if skin_type == "dry":
            return "Since you have dry skin, I especially recommend using a rich moisturizer, avoiding hot water, and adding hydrating ingredients like hyaluronic acid or glycerin. Consider a facial oil or humidifier to lock in moisture!"
        return "For dry skin, use a rich moisturizer, avoid hot water, and add hydrating ingredients like hyaluronic acid or glycerin. Consider a facial oil or humidifier to lock in moisture!"

    # Oily skin
    if any(word in message_lower for word in ["oily", "greasy"]):
        if skin_type == "oily":
            return "For your oily skin, use a gentle cleanser, apply oil-free moisturizer, and try ingredients like niacinamide or salicylic acid. Don't skip moisturizer—it helps balance oil production!"
        return "For oily skin, use a gentle cleanser, apply oil-free moisturizer, and try ingredients like niacinamide or salicylic acid. Don't skip moisturizer—it helps balance oil production!"

    # Acne
    if any(word in message_lower for word in ["acne", "pimple", "breakout"]):
        if "acne" in concerns:
            return "To help with your acne concerns, maintain a consistent skincare routine with a gentle cleanser, non-comedogenic moisturizer, and try ingredients like salicylic acid or benzoyl peroxide. Keep your skin clean and avoid touching your face!"
        return "To prevent acne, maintain a consistent skincare routine with a gentle cleanser, non-comedogenic moisturizer, and try ingredients like salicylic acid or benzoyl peroxide. Keep your skin clean and avoid touching your face!"

    # Wrinkles/aging
    if (
        "wrinkle" in message_lower
        or "fine line" in message_lower
        or "aging" in message_lower
    ):
        if "fine_lines" in concerns:
            return "To help reduce your fine lines, use sunscreen daily, moisturize regularly, and consider retinol or vitamin C products. Getting enough sleep and staying hydrated also helps maintain skin elasticity!"
        return "To reduce wrinkles, use sunscreen daily, moisturize regularly, and consider retinol or vitamin C products. Getting enough sleep and staying hydrated also helps maintain skin elasticity!"

    # Routine questions
    if (
        "routine" in message_lower
        or "order" in message_lower
        or "step" in message_lower
    ):
        return "A basic skincare routine involves: 1) Cleanser 2) Toner (optional) 3) Serums 4) Moisturizer 5) Sunscreen (AM). Apply products from thinnest to thickest consistency!"

    # Skincare tips/prevention/improvement
    if any(
        word in message_lower
        for word in [
            "prevent",
            "reduce",
            "help",
            "improve",
            "fix",
            "treat",
            "best",
            "good",
        ]
    ):
        return "A consistent skincare routine is key! Cleanse daily, use a moisturizer suited to your skin type, wear sunscreen, and add targeted treatments like serums or masks. Consistency matters more than complexity!"

    # General skincare importance
    if any(
        word in message_lower
        for word in ["important", "necessary", "why", "need", "should"]
    ):
        return "Skincare is important for maintaining healthy, youthful skin. A basic routine of cleansing, moisturizing, and sun protection goes a long way!"

    # DEFAULT
    return (
        "I'm not sure I fully understood 😅\n\n"
        "You can try things like:\n"
        "• 'What is niacinamide?'\n"
        "• 'Find a dupe for CeraVe cleanser'\n"
        "• 'What should I use for acne?'\n\n"
        "Tell me what you're looking for and I'll help you 👍"
    )
