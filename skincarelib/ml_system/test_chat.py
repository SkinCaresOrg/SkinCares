from skincarelib.ml_system.handler import handle_chat


def run_tests():
    intent = None

    tests = [
        # 🔹 GREETING
        "hi",
        # 🔹 LINK HANDLING
        "how do I get recommendations",
        "where can I find dupes",
        # 🔹 RECOMMEND FLOW (multi-step)
        "recommend",
        "yes",
        "moisturizer",
        "dry skin",
        # 🔹 DIRECT RECOMMEND (one-shot)
        "serum for oily skin",
        # 🔹 EDGE: missing skin type
        "recommend cleanser",
        # 🔹 DUPE FLOW
        "dupe for cerave cleanser",
        # 🔹 INFO
        "what is niacinamide",
        # 🔹 AI FALLBACK (should trigger Ollama)
        "how should I layer my skincare",
        "what helps with redness",
        # 🔹 RANDOM / TYPO
        "recommnd skncare pls",
        # 🔹 CONTEXT FOLLOW-UP
        "yes",
    ]

    print("\n===== CHATBOT TEST START =====\n")

    for msg in tests:
        print("You:", msg)

        try:
            response, intent = handle_chat(msg, last_intent=intent)
            print("Bot:", response)
        except Exception as e:
            print("Bot ERROR:", e)

        print("-" * 50)

    print("\n===== TEST END =====\n")


if __name__ == "__main__":
    run_tests()
