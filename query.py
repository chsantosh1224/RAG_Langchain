"""Local CLI chat against the LangGraph RAG agent.

Usage: python query.py [conversation_id]
Re-using a conversation_id continues that conversation (history is in Postgres).
"""
import sys
import warnings

from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore")

from langchain_core.messages import HumanMessage

from app.graph import build_graph, get_checkpoint_pool


def main():
    conversation_id = sys.argv[1] if len(sys.argv) > 1 else "demo"
    # Locally there is no logged-in user; the API will use the Cognito user ID here.
    config = {"configurable": {"thread_id": f"local:{conversation_id}"}}

    with get_checkpoint_pool() as pool:
        graph = build_graph(pool)
        print(f"Conversation '{conversation_id}'. Type 'exit' to quit.\n")

        while True:
            try:
                question = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not question:
                continue
            if question.lower() in ("exit", "quit"):
                break

            state = graph.invoke({"messages": [HumanMessage(question)]}, config=config)

            if state["standalone_question"] != question:
                print(f"  (searched for: {state['standalone_question']})")
            print(f"\nAI: {state['messages'][-1].content}")
            sources = ", ".join(f"{s['source']} p.{s['page']}" for s in state["sources"])
            print(f"Sources: {sources}\n" + "-" * 60)


if __name__ == "__main__":
    main()
