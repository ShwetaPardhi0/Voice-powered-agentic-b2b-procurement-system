from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Represents the state of the multi-agent system.
    
    Attributes:
        messages: Conversation history (handled by LangGraph add_messages).
        next: The next node to execute. Can be one of the sub-agents, "supervisor", or "__end__".
        context: Shared workspace containing structured B2B variables passed between agents.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str
    context: dict
