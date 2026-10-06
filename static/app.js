const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("chat-messages");
const sendButton = document.getElementById("send-button");
const suggestions = document.querySelectorAll(".suggestion");

let sessionId = sessionStorage.getItem("oracle_chat_session_id") || "";


function scrollToLatestMessage() {
    messages.scrollTop = messages.scrollHeight;
}


function renderAssistantMarkdown(container, markdown) {
    if (!window.marked || !window.DOMPurify) {
        const paragraph = document.createElement("p");
        paragraph.textContent = markdown;
        container.appendChild(paragraph);
        return;
    }

    const unsafeHtml = window.marked.parse(markdown, {
        breaks: true,
        gfm: true,
    });

    container.innerHTML = window.DOMPurify.sanitize(unsafeHtml);

    for (const table of container.querySelectorAll("table")) {
        const wrapper = document.createElement("div");
        wrapper.className = "table-wrapper";
        wrapper.tabIndex = 0;
        table.before(wrapper);
        wrapper.appendChild(table);
    }
}


function addMessage(text, role) {
    const article = document.createElement("article");
    article.className = `message ${role}-message`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "user" ? "You" : "AI";

    const content = document.createElement("div");
    content.className = "message-content";

    if (role === "assistant") {
        renderAssistantMarkdown(content, text);
    } else {
        const paragraph = document.createElement("p");
        paragraph.textContent = text;
        content.appendChild(paragraph);
    }

    article.appendChild(avatar);
    article.appendChild(content);
    messages.appendChild(article);

    scrollToLatestMessage();

    return article;
}


function addLoadingMessage() {
    const article = document.createElement("article");
    article.className = "message assistant-message";

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "AI";

    const content = document.createElement("div");
    content.className = "message-content";

    const dots = document.createElement("div");
    dots.className = "typing-dots";

    for (let index = 0; index < 3; index += 1) {
        dots.appendChild(document.createElement("span"));
    }

    content.appendChild(dots);
    article.appendChild(avatar);
    article.appendChild(content);
    messages.appendChild(article);

    scrollToLatestMessage();

    return article;
}


function addChart(chartSpec) {
    const article = document.createElement("article");
    article.className = "chart-card";

    const chartContainer = document.createElement("div");
    chartContainer.className = "plotly-chart";

    article.appendChild(chartContainer);
    messages.appendChild(article);

    Plotly.newPlot(
        chartContainer,
        chartSpec.data || [],
        chartSpec.layout || {},
        {
            responsive: true,
            displaylogo: false,
            modeBarButtonsToRemove: ["select2d", "lasso2d"],
        },
    );

    scrollToLatestMessage();
}


async function sendMessage(question) {
    addMessage(question, "user");

    input.value = "";
    input.disabled = true;
    sendButton.disabled = true;

    const loadingMessage = addLoadingMessage();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                message: question,
                session_id: sessionId,
            }),
        });

        const result = await response.json();
        loadingMessage.remove();

        if (!response.ok) {
            addMessage(
                result.error || "Something went wrong.",
                "assistant",
            );
            return;
        }

        sessionId = result.session_id;
        sessionStorage.setItem("oracle_chat_session_id", sessionId);

        addMessage(result.answer, "assistant");

        for (const chartSpec of result.chart_specs || []) {
            addChart(chartSpec);
        }
    } catch (error) {
        loadingMessage.remove();

        addMessage(
            "The server could not be reached. Confirm Flask and Oracle are running.",
            "assistant",
        );
    } finally {
        input.disabled = false;
        sendButton.disabled = false;
        input.focus();
    }
}


form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = input.value.trim();

    if (question) {
        await sendMessage(question);
    }
});


for (const suggestion of suggestions) {
    suggestion.addEventListener("click", async () => {
        const question = suggestion.textContent.trim();

        if (!input.disabled) {
            await sendMessage(question);
        }
    });
}
