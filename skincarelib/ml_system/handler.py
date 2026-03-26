from skincarelib.ml_system.intent import detect_intent
from skincarelib.ml_system.parser import extract_preferences
from skincarelib.models.dupe_finder import find_dupes
from skincarelib.models.recommender_ranker import recommend_products


def handle_chat(message: str) -> str:
    intent = detect_intent(message)

    if intent == "dupe":
        return handle_dupe(message)

    elif intent == "recommend":
        return handle_recommend(message)

    else:
        return "Sorry, I didn’t fully understand. Try asking for a recommendation or a dupe!"


def handle_dupe(message: str) -> str:
    product_name = message.replace(
        "dupe", ""
    ).strip()  # Basic extraction (need to improve)

    results = find_dupes(product_name)

    if not results:
        return "I couldn't find dupes for that product."

    response = "Here are some possible dupes:\n"
    for r in results[:3]:
        response += f"- {r['name']} (${r['price']})\n"

    return response


def handle_recommend(message: str) -> str:
    prefs = extract_preferences(message)

    results = recommend_products(
        skin_type=prefs["skin_type"],
        concern=prefs["concern"],
        price_pref=prefs["price"],
    )

    if not results:
        return "I couldn't find good matches for your request."

    response = "Based on your needs, here are some options:\n"
    for r in results[:3]:
        response += f"- {r['name']} (${r['price']})\n"

    return response
