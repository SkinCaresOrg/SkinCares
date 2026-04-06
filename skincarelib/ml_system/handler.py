import os
import re
import requests
from typing import Optional, Dict, Any

from skincarelib.ml_system.intent import detect_intent
from skincarelib.models.dupe_finder import find_dupes

# Initialize OpenAI client lazily (only when needed)
_client = None

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


def handle_chat(message: str, profile: Optional[Dict[str, Any]] = None) -> str:
    msg_lower = message.lower().strip()


    # 1. HARD RULES 
    # meaningless input
    if len(msg_lower) < 4 or not any(c.isalpha() for c in msg_lower):
        return _smart_fallback(message, profile)

    # Routine questions 
    if "routine" in msg_lower or "order" in msg_lower or "step" in msg_lower:
        return _smart_fallback(message, profile)

    # Dupe shortcuts 
    if "dupe" in msg_lower or "similar" in msg_lower or "alternative" in msg_lower:
        return handle_dupe(message, profile)

    
    # 2. INTENT DETECTION
    intent = detect_intent(message)

    if intent == "dupe":
        return handle_dupe(message, profile)

    elif intent == "recommend" or "should i use" in msg_lower:
        return handle_recommend(message, profile)

    elif intent == "info":
        return handle_info(message, profile)

    # 3. RULE-BASED FALLBACK

    fallback_response = _smart_fallback(message, profile)

    if "I'm not sure I fully understood" not in fallback_response:
        return fallback_response

    # 4. AI 
    return handle_ai_fallback(message, profile)

def handle_dupe(message: str, profile: Optional[Dict[str, Any]] = None) -> str:
    """Handle product dupe finding requests."""
    match = re.search(r"(dupe|alternative|similar).*(for|to)?\s*(.+)", message.lower())
    if match:
        product_name = match.group(3).strip()
    else:
        product_name = message.lower().strip()

    if not product_name:
        return "I'd be happy to help find dupes! Please tell me which product you're looking for dupes for (e.g., 'Find me a dupe for Cetaphil')."

    try:
        results = find_dupes(product_name)

        if results.empty:
            return f"I couldn't find cheaper alternatives for {product_name} in our database. Try browsing our products for similar items!"

        response = f"Great! Here are some possible dupes for {product_name}:\n"
        for idx, row in results.head(3).iterrows():
            response += f"- {row['name']} by {row['brand']} (${row['price']})\n"

        return response
    except Exception:
        return "I couldn't find dupes for that product. Please try browsing our products or asking for recommendations instead!"


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
                    personalized_tip = " For your fine line concerns, retinol is an excellent choice!"
                elif key == "salicylic acid" and ("acne" in concerns or skin_type == "oily"):
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
    if message_lower in ["hi", "hello", "hey", "greetings", "hiya", "what's up", "whats up"]:
        return "Hi! 👋 I can help you understand ingredients, find dupes, or recommend products based on your skin. What are you looking for?"

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
    if "wrinkle" in message_lower or "fine line" in message_lower or "aging" in message_lower:
        if "fine_lines" in concerns:
            return "To help reduce your fine lines, use sunscreen daily, moisturize regularly, and consider retinol or vitamin C products. Getting enough sleep and staying hydrated also helps maintain skin elasticity!"
        return "To reduce wrinkles, use sunscreen daily, moisturize regularly, and consider retinol or vitamin C products. Getting enough sleep and staying hydrated also helps maintain skin elasticity!"

    # Routine questions
    if "routine" in message_lower or "order" in message_lower or "step" in message_lower:
        return "A basic skincare routine involves: 1) Cleanser 2) Toner (optional) 3) Serums 4) Moisturizer 5) Sunscreen (AM). Apply products from thinnest to thickest consistency!"

    # Skincare tips/prevention/improvement
    if any(word in message_lower for word in ["prevent", "reduce", "help", "improve", "fix", "treat", "best", "good"]):
        return "A consistent skincare routine is key! Cleanse daily, use a moisturizer suited to your skin type, wear sunscreen, and add targeted treatments like serums or masks. Consistency matters more than complexity!"

    # General skincare importance
    if any(word in message_lower for word in ["important", "necessary", "why", "need", "should"]):
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