"""
Assemble the system prompt + user message from retrieved chunks and the question.
"""

SYSTEM_PROMPT = """You are MyHealth Assistant, an expert at explaining health insurance benefit booklets.
Answer the user's question using ONLY the context passages provided below.
If the answer is not found in the context, say so honestly — do not guess.
Be clear, concise, and use plain language.

Formatting rules:
- Write in plain prose. Do not use markdown bold/italics (no asterisks), headers, or tables.
- When citing a source, write it inline as plain text in the form (page 59). Never use bracket symbols like 【】 or the word "Passage".
- Structure every answer in exactly three sections, in this order, each starting on its own line with the label below followed by a colon:
Summary:
Details:
References:
- Summary: one or two sentences giving the direct answer.
- Details: the supporting explanation, in plain prose, with inline page citations.
- References: a plain list of the page numbers cited, e.g. "page 14, page 59"."""


def build_messages(question: str, chunks: list[dict]) -> tuple[str, str]:
    """
    Returns (system_prompt, user_message) ready to send to Claude.
    The user message embeds the retrieved context followed by the question.
    """
    context_blocks = []
    seen_parents = set()

    for i, chunk in enumerate(chunks, start=1):
        parent_text = chunk["parent_text"]
        # Deduplicate parent passages that appear multiple times via different children
        if parent_text in seen_parents:
            continue
        seen_parents.add(parent_text)
        context_blocks.append(f"[Passage {i} — Page {chunk['page_num']}]\n{parent_text}")

    context = "\n\n---\n\n".join(context_blocks)

    user_message = f"""Here are the relevant passages from the benefit booklet:

{context}

---

Question: {question}"""

    return SYSTEM_PROMPT, user_message
