import ai_utils

if __name__ == "__main__":
    history = []
    while True:
        q = input()
        a = ai_utils.chat_rag(q, history)
        print(a)
        history.append((q, a))