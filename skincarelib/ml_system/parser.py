# Extracting user preferences from their message based on keywords
def extract_preferences(message: str) -> dict:
    message = message.lower()

    prefs = {
        "skin_type": None,
        "concern": None,
        "price": None,
    }

    if "oily" in message:
        prefs["skin_type"] = "oily"
    elif "dry" in message:
        prefs["skin_type"] = "dry"

    if "acne" in message:
        prefs["concern"] = "acne"
    elif "anti-aging" in message or "wrinkles" in message:
        prefs["concern"] = "anti-aging"

    if "cheap" in message or "budget" in message:
        prefs["price"] = "low"

    return prefs