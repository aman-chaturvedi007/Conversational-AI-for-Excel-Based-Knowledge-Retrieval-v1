import json
import re
from typing import NotRequired

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

# pyrefly: ignore [missing-import]
from chatbot.data_catalog import refresh_database
# pyrefly: ignore [missing-import]
from chatbot.settings import ORACLE_DATA_OWNER_SCHEMA
# pyrefly: ignore [missing-import]
from chatbot.tools import ANALYTICS_TOOLS


class AgentState(MessagesState):
    dataset_context: NotRequired[str]


llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
)

llm_with_tools = llm.bind_tools(ANALYTICS_TOOLS)

MAX_TOOL_TEXT_FOR_MODEL = 2_500
CHART_REQUEST_PATTERN = re.compile(
    r"\b(?:chart|graph|plot|visuali[sz](?:e|ation)|histogram)\b",
    flags=re.IGNORECASE,
)


def messages_for_model(messages: list) -> list:
    """
    Keep chart JSON in LangGraph state for Flask to send to the browser,
    but replace it with a short confirmation before calling the LLM again.
    """
    prepared_messages = []

    for message in messages:
        if message.type != "tool":
            prepared_messages.append(message)
            continue

        content = str(message.content)

        try:
            tool_payload = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            tool_payload = {}

        if "chart" in tool_payload:
            compact_content = (
                "An interactive Plotly chart was created successfully. "
                "Briefly confirm that the chart is ready for the user."
            )
        else:
            compact_content = content[:MAX_TOOL_TEXT_FOR_MODEL]

            if len(content) > MAX_TOOL_TEXT_FOR_MODEL:
                compact_content += "\n_Result shortened for conversation context._"

        prepared_messages.append(
            ToolMessage(
                content=compact_content,
                tool_call_id=message.tool_call_id,
                name=message.name,
                id=message.id,
            )
        )

    return prepared_messages


def latest_request_is_for_chart(messages: list) -> bool:
    """Return whether the newest user message asks to see a chart."""
    for message in reversed(messages):
        if message.type == "human":
            return bool(CHART_REQUEST_PATTERN.search(str(message.content)))

    return False


def chart_tool_was_called_for_latest_request(messages: list) -> bool:
    """Avoid requesting a second chart after create_chart has already run."""
    for message in reversed(messages):
        if message.type == "human":
            return False

        if message.type != "ai":
            continue

        if any(
            tool_call["name"] == "create_chart"
            for tool_call in message.tool_calls
        ):
            return True

    return False


def retrieve_data_context(state: AgentState) -> dict:
    catalogue = refresh_database()

    readable_catalogue = "\n".join(
        (
            f"Schema: {ORACLE_DATA_OWNER_SCHEMA} | "
            f"Table: {item['table']} | "
            f"Columns: {', '.join(item['columns'])} | "
            f"Rows: {item['row_count']}"
        )
        for item in catalogue
    )

    return {"dataset_context": readable_catalogue}


def chatbot_node(state: AgentState) -> dict:
    system_instruction = SystemMessage(
        content=(
            "You are a careful Oracle data analyst. "
            "You must use tools before making claims about the data. "
            "Use run_data_query for numerical answers. "
            "Whenever the user asks for a graph, chart, plot, box plot, "
            "histogram, or visualization, you MUST call create_chart before "
            "writing a final answer. Never provide a text-only answer to a "
            "chart request. "
            f"Use only {ORACLE_DATA_OWNER_SCHEMA} tables. "
            "Use schema-qualified table names in SQL. "
            "Never invent tables, columns, or numerical values. "
            "Use only one SELECT or WITH SQL query. "
            "Write final answers in GitHub-flavored Markdown. "
            "Lead with a direct one- or two-sentence answer, then use short "
            "headings or bullet lists only when they improve readability. "
            "When presenting query results, use a Markdown table with clear "
            "column names. Never use ASCII-art tables, padded plain-text "
            "columns, or command-prompt-style output. "
            "Bold the most important metric when it helps the reader. "
            "Do not show SQL, tool calls, or implementation details unless "
            "the user explicitly asks for them. "
            f"\n\nAvailable Oracle metadata:\n{state['dataset_context']}"
        )
    )

    # Six recent messages keeps Groq requests below its token limit.
    recent_messages = state["messages"][-6:]

    model_messages = [
        system_instruction,
        *messages_for_model(recent_messages),
    ]

    response = llm_with_tools.invoke(model_messages)

    chart_is_required = (
        latest_request_is_for_chart(state["messages"])
        and not chart_tool_was_called_for_latest_request(state["messages"])
    )

    chart_was_requested = any(
        tool_call["name"] == "create_chart"
        for tool_call in response.tool_calls
    )

    if chart_is_required and not chart_was_requested:
        response = llm_with_tools.invoke(
            [
                *model_messages,
                SystemMessage(
                    content=(
                        "Correction: the user's newest request requires a "
                        "chart. Call create_chart now with an appropriate "
                        "query, chart type, columns, and title. Do not reply "
                        "with ordinary text."
                    )
                ),
            ]
        )

    return {"messages": [response]}


builder = StateGraph(AgentState)

builder.add_node("retrieve_data_context", retrieve_data_context)
builder.add_node("chatbot", chatbot_node)
builder.add_node("tools", ToolNode(ANALYTICS_TOOLS))

builder.add_edge(START, "retrieve_data_context")
builder.add_edge("retrieve_data_context", "chatbot")
builder.add_conditional_edges("chatbot", tools_condition)
builder.add_edge("tools", "chatbot")

memory = MemorySaver()

graph = builder.compile(checkpointer=memory)
