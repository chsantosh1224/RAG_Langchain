"""FastAPI query API: POST /chat runs the LangGraph agent, GET /health is for the ALB.

Run locally: uvicorn app.main:app --port 8000
"""
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Response
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.config import load_config

load_config()  # before the imports below, which read settings at import time

from app.auth import get_current_user
from app.embeddings import TEI_URL
from app.graph import build_graph, get_checkpoint_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build once at startup: one connection pool and one compiled graph for all requests.
    with get_checkpoint_pool() as pool:
        app.state.pool = pool
        app.state.graph = build_graph(pool)
        yield


app = FastAPI(title="RAG query API", lifespan=lifespan)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=100)


class Source(BaseModel):
    source: str
    page: int


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    standalone_question: str
    sources: list[Source]


# Plain `def`: the graph is synchronous, so FastAPI runs this in a worker thread.
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user_id: str = Depends(get_current_user)):
    conversation_id = req.conversation_id or str(uuid.uuid4())
    # The user ID is part of the thread ID, so users can't read each other's conversations.
    config = {"configurable": {"thread_id": f"{user_id}:{conversation_id}"}}

    state = app.state.graph.invoke({"messages": [HumanMessage(req.question)]}, config=config)

    return ChatResponse(
        conversation_id=conversation_id,
        answer=state["messages"][-1].content,
        standalone_question=state["standalone_question"],
        sources=state["sources"],
    )


@app.get("/health")
def health(response: Response):
    checks = {}
    try:
        with app.state.pool.connection(timeout=2) as conn:
            conn.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "down"
    try:
        httpx.get(f"{TEI_URL}/health", timeout=2).raise_for_status()
        checks["embeddings"] = "ok"
    except Exception:
        checks["embeddings"] = "down"

    healthy = all(v == "ok" for v in checks.values())
    response.status_code = 200 if healthy else 503
    return {"status": "ok" if healthy else "degraded", **checks}
