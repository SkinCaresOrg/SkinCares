# Detecting user intent based on keywords in the message
def detect_intent(message: str) -> str:
    message = message.lower()

    if "dupe" in message:
        return "dupe"
    elif any(
        word in message for word in ["recommend", "suggest", "looking for", "need"]
    ):
        return "recommend"
    elif any(word in message for word in ["what is", "tell me about", "info"]):
        return "info"
    else:
        return "unknown"
