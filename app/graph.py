"""LangGraph RAG agent: rewrite_query -> retrieve -> generate.

Conversation state is checkpointed in Postgres (schema agent_state), keyed by
thread_id, so a conversation survives restarts and can continue on any server.
"""
import os

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.embeddings import TEIEmbeddings
from app.vectorstore import DATABASE_URL, get_engine, get_vectorstore

TOP_K = 4
HISTORY_WINDOW = 10  # previous messages sent to the LLM

# History goes in as a plain transcript, not chat turns; otherwise the model
# slips into answering the question instead of rewriting it.
REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You rewrite questions; you never answer them. Rewrite the latest question "
     "as a standalone question that can be understood without the conversation. "
     "If it is already standalone, return it unchanged. Return only the question."),
    ("human", "Conversation:\n{transcript}\n\nLatest question: {question}\n\nStandalone question:"),
])

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Answer the question using only the context below. If the context does not "
     "contain the answer, say you don't know instead of guessing.\n\nContext:\n{context}"),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])


class RAGState(MessagesState):
    standalone_question: str
    context: str
    sources: list[dict]


def get_llm():
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENROUTER_BASE_URL"),
        temperature=0,
    ).with_retry(stop_after_attempt=3)


def get_checkpoint_pool() -> ConnectionPool:
    # PostgresSaver needs autocommit + dict rows; search_path puts its tables in agent_state.
    return ConnectionPool(
        DATABASE_URL,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": "-c search_path=agent_state",
        },
        open=True,
    )


def build_graph(pool: ConnectionPool):
    llm = get_llm()
    store = get_vectorstore(get_engine(), TEIEmbeddings())
    rewrite_chain = REWRITE_PROMPT | llm | StrOutputParser()
    answer_chain = ANSWER_PROMPT | llm | StrOutputParser()

    def history(state: RAGState):
        return state["messages"][:-1][-HISTORY_WINDOW:]

    def rewrite_query(state: RAGState):
        question = state["messages"][-1].content
        if len(state["messages"]) == 1:  # first question has nothing to resolve
            return {"standalone_question": question}
        transcript = "\n".join(
            f"{'User' if m.type == 'human' else 'Assistant'}: {m.content[:500]}"
            for m in history(state)
        )
        rewritten = rewrite_chain.invoke({"transcript": transcript, "question": question})
        return {"standalone_question": rewritten.strip()}

    def retrieve(state: RAGState):
        docs = store.similarity_search(state["standalone_question"], k=TOP_K)
        sources = []
        for d in docs:
            ref = {"source": d.metadata.get("source"), "page": (d.metadata.get("page") or 0) + 1}
            if ref not in sources:
                sources.append(ref)
        return {"context": "\n\n".join(d.page_content for d in docs), "sources": sources}

    def generate(state: RAGState):
        answer = answer_chain.invoke({
            "context": state["context"],
            "history": history(state),
            "question": state["messages"][-1].content,
        })
        return {"messages": [AIMessage(answer)]}

    builder = StateGraph(RAGState)
    builder.add_node("rewrite_query", rewrite_query)
    builder.add_node("retrieve", retrieve)
    builder.add_node("generate", generate)
    builder.add_edge(START, "rewrite_query")
    builder.add_edge("rewrite_query", "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)

    checkpointer = PostgresSaver(pool)
    checkpointer.setup()  # creates checkpoint tables on first run
    return builder.compile(checkpointer=checkpointer)
