# To run:
# cd /Users/conradearney/Documents/repos/voice-llm-chat
# source .venv/bin/activate
# python run_voice_chat.py

from src.conversation import ConversationManager

def main():
    convo = ConversationManager()
    max_turns = 3

    for i in range(max_turns):
        print("\n--- Turn {}/{} ---".format(i + 1, max_turns))
        try:
            convo.process_turn()
        except KeyboardInterrupt:
            print("\n Stopping by user request.")
            break

    print("\n Conversation ended.")

if __name__ == "__main__":
    main()
