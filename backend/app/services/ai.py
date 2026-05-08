# backend/app/services/ai.py
import asyncio
import logging
import os
from typing import Annotated, Any, Sequence, TypedDict

import httpx
from langchain_chroma import Chroma
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from tenacity import retry, stop_after_attempt, wait_exponential  # <-- CRITICAL for Phase 1 reliability

# Classic LangChain chains for Phase 1 - standardized usage
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever

# Reusing configurations from our modular config service
from ..core.config import settings

# Setup standardized logging for this service
logger = logging.getLogger("chatbot-ai-service")

# --- LangGraph State & Prompts (Extracted from old monolithic script) ---

class State(TypedDict):
    input: str
    chat_history: Annotated[Sequence[BaseMessage], add_messages]
    answer: str
    context: Annotated[list, "Docs"]


contextualize_q_system_prompt = (
    "Given the chat history and the latest user question, rewrite the question so it can "
    "be understood without prior context. Do not answer it."
)

contextualize_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ]
)


# --- Helpers ---

def build_system_prompt(site_config: dict[str, Any]) -> str:
    """Builds the customized prompt for a specific tenant."""
    prompt = (
        f"You are {site_config['brand_name']}'s website assistant. "
        "Answer using the retrieved context when available. "
        "If the answer is not in context, be honest and provide a helpful fallback. "
        "Keep responses concise, clear, and formatted in Markdown. "
        "Use bullet points when listing items and clickable Markdown links for contact information."
    )
    if site_config.get("system_prompt_suffix"):
        prompt = f"{prompt}\n\n{site_config['system_prompt_suffix']}"
    return f"{prompt}\n\n{{context}}"


# PHASE 1 RELIABILITY FIX: Timeouts and Retries on LLM Node
@retry(
    stop=stop_after_attempt(3), # Attempt LLM call up to 3 times total
    wait=wait_exponential(multiplier=1, min=2, max=10), # Exponential backoff: 2s, 4s, 8s
    reraise=True, # Raise final exception if all retries fail
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying LLM call, attempt {retry_state.attempt_number}..."
    )
)
async def invoke_rag_with_retry(rag_chain, state: State, site_id: str):
    """Invoke RAG chain with retry and strict timeout mechanism."""
    # We must invoke ainvoke from the context of an asyncio event loop.
    # Enforce a strict 25s timeout per attempt, allowing 5s for the overall workflow request
    try:
        return await asyncio.wait_for(rag_chain.ainvoke(state), timeout=25)
    except asyncio.TimeoutError:
        logger.error(f"Timeout during LLM ainvoke call for site {site_id}")
        raise # Raise for Tenacity to catch and retry


def build_workflow(site_config: dict[str, Any]):
    """Compiles the secure, reliable LangGraph workflow for a given site config."""

    # Ignore inherited proxy env vars. They break local OpenAI calls in this MVP setup.
    sync_http_client = httpx.Client(timeout=30.0, trust_env=False)
    async_http_client = httpx.AsyncClient(timeout=30.0, trust_env=False)

    # Initialize components using modular settings
    embeddings = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
        http_client=sync_http_client,
        http_async_client=async_http_client,
    )

    # PHASE 1 SCALABILITY FIX: Standardized Chroma-as-a-Service Connection
    # We always prioritize an HTTP connected server. We don't do local connections in production.
    # For Phase 1 ship, we rely on having this setup in the target cloud.
    chroma_host = settings.CHROMA_SERVER_HOST
    chroma_port = settings.CHROMA_SERVER_HTTP_PORT

    if chroma_host and settings.APP_ENV != "development":
        logger.info(f"Workflow for {site_config['site_id']} connecting to CHROMA SERVER at {chroma_host}:{chroma_port}")
        vector_store = Chroma(
            embedding_function=embeddings,
            host=chroma_host,
            port=chroma_port,
            # Phase 1 Limitation: We connect to a shared collection, not segmented ones.
            # RAG Segmentation will come in Phase 2.
        )
    else:
        # Development / Small scale fallback - Segmented Local pattern enforced
        # NOTICE: We use the segmented path `./akinfoChroma/{site_id}` that our cli tool just created.
        local_chroma_dir = settings.CHROMA_DIR / site_config['site_id']
        logger.warning(f"Workflow for {site_config['site_id']} using LOCAL Chroma SQLite (segmented) at {local_chroma_dir}. Not scalable.")
        vector_store = Chroma(
            persist_directory=str(local_chroma_dir),
            embedding_function=embeddings,
        )

    retriever = vector_store.as_retriever()
    # Standard 30s timeout on LLM instantiation for MVP safety
    llm = ChatOpenAI(
        model=site_config["openai_chat_model"],
        streaming=True,
        timeout=30,
        http_client=sync_http_client,
        http_async_client=async_http_client,
    )
    
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", build_system_prompt(site_config)),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ]
    )

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    # --- Compile Workflow Graph ---
    workflow = StateGraph(State)

    async def qa_node(state: State):
        """The AI service node in the LangGraph."""
        try:
            # RAG Node handles timeouts/retries internally
            response = await invoke_rag_with_retry(rag_chain, state, site_config['site_id'])
            return {
                "chat_history": state["chat_history"] + [
                    HumanMessage(content=state["input"]),
                    AIMessage(content=response["answer"]),
                ],
                "answer": response["answer"],
                "context": response["context"],
                # Pass original site_id back for clean tenant identification
                "site_id": site_config['site_id'],
            }
        except Exception:
            # Final failure log. Raise to allow the WS endpoint to handle the failure UX.
            logger.exception(
                f"Critical failure at LLM execution node (tenant: {site_config['site_id']}) after retries."
            )
            raise 

    workflow.add_node("qa", qa_node)
    workflow.add_edge(START, "qa")
    workflow.add_edge("qa", END)
    
    # [SCALABILITY LIMITATION ACCEPTED]: MemorySaver is LOCAL memory only.
    # User history is coupled to this specific app worker.
    # To support scaling out in Phase 1, the client widget must handle disconnections gracefully.
    return workflow.compile(checkpointer=MemorySaver())
