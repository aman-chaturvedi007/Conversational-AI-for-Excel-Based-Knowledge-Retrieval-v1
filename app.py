import json
from uuid import uuid4

from flask import Flask, jsonify, render_template, request
from langchain_core.messages import HumanMessage

# pyrefly: ignore [missing-import]
from chatbot.graph import graph

app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)

    question = payload.get("message", "").strip()
    session_id = payload.get("session_id") or str(uuid4())

    if not question:
        return jsonify({"error": "Please enter a question."}), 400

    config = {"configurable": {"thread_id": session_id}}

    try:
        # Count the previously saved session messages.
        previous_state = graph.get_state(config)
        previous_message_count = len(
            previous_state.values.get("messages", [])
        )

        result = graph.invoke(
            {"messages": [HumanMessage(content=question)]},
            config=config,
        )
    except Exception:
        app.logger.exception("Chat request failed")

        return jsonify(
            {
                "error": (
                    "The assistant could not process that request. "
                    "Please try a shorter, more specific question."
                )
            }
        ), 502

    # Keep only messages produced for this browser request.
    current_messages = result["messages"][previous_message_count:]

    chart_specs = []

    for message in current_messages:
        if message.type != "tool":
            continue

        try:
            tool_payload = json.loads(message.content)
        except (TypeError, json.JSONDecodeError):
            continue

        chart = tool_payload.get("chart")

        if chart:
            chart_specs.append(chart)

    answer = next(
        (
            message.content
            for message in reversed(current_messages)
            if message.type == "ai"
        ),
        "I could not generate an answer.",
    )

    return jsonify(
        {
            "session_id": session_id,
            "answer": answer,
            "chart_specs": chart_specs,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)