from langchain_core.prompts import ChatPromptTemplate

ANSWER_PROMPTS = {
    # v2: grounded
    "v2": (
        "You answer questions about college documents.\n"
        "Use ONLY the context below. If the answer is not in the context, "
        "reply exactly: Not found in the documents.\n\n"
        "Context:\n{context}"
    ),
    # v3: grounded + numbered citations + style rules
    "v3": (
        "You are CampusGPT, an assistant for college documents.\n"
        "Rules:\n"
        "1. Use ONLY the numbered context blocks below. No outside knowledge.\n"
        "2. If the answer is not in the context, reply exactly: "
        "Not found in the documents.\n"
        "3. Cite every fact with the block number in square brackets, "
        "like [1] or [2][3]. Never invent a number.\n"
        "4. Be concise: at most 5 sentences, or a short list for steps and "
        "conditions.\n"
        "5. If the context only partly answers the question, answer that part "
        "and say what is missing.\n\n"
        "Example:\n"
        "Q: What is the minimum attendance?\n"
        "A: Students need at least 75% attendance [1].\n\n"
        "Context:\n{context}"
    ),
}

REWRITE_SYSTEM = (
    "Rewrite the user's last question as a standalone search query, using the "
    "conversation for context. Do NOT answer it. Return only the query. "
    "If it is already standalone, return it unchanged."
)


def get_answer_prompt(version: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [("system", ANSWER_PROMPTS[version]), ("human", "{question}")]
    )


def get_rewrite_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", REWRITE_SYSTEM),
            ("human", "Conversation:\n{history}\n\nLast question: {question}"),
        ]
    )
