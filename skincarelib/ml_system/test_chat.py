from skincarelib.ml_system.handler import handle_chat

chat_history = []

def chat():
    print("Start chatting (type 'exit' to stop)\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() == "exit":
            break

        chat_history.append({"role": "user", "content": user_input})

        response = handle_chat(user_input)

        chat_history.append({"role": "assistant", "content": response})

        print("Bot:", response)
        print()

chat()