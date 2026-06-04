"""
Pipeline entry point called by index.js via child_process.
Reads JSON from stdin: { plan_id, question }
Streams answer tokens to stdout, one per line prefixed with "TOKEN:"
On error writes "ERROR:<message>" and exits with code 1.

Usage:
  echo '{"plan_id":"UC280509","question":"What is my deductible?"}' | python generation.py
"""

import sys
import json
import anthropic

from generate_query_embed import embed_query
from retrieval import retrieve
from prepare_prompt import build_messages

MODEL   = "claude-sonnet-4-6"
TOP_K   = 5
MAX_TOKENS = 1024


def main():
    raw = sys.stdin.read().strip()
    try:
        payload  = json.loads(raw)
        plan_id  = payload["plan_id"]
        question = payload["question"]
    except Exception as e:
        sys.stdout.write(f"ERROR:Invalid input — {e}\n")
        sys.stdout.flush()
        sys.exit(1)

    # 1. Embed the query
    try:
        query_embedding = embed_query(question)
    except Exception as e:
        sys.stdout.write(f"ERROR:Embedding failed — {e}\n")
        sys.stdout.flush()
        sys.exit(1)

    # 2. Retrieve top-k parent chunks from the plan's vector DB
    try:
        chunks = retrieve(plan_id, query_embedding, top_k=TOP_K)
    except ValueError as e:
        sys.stdout.write(f"ERROR:{e}\n")
        sys.stdout.flush()
        sys.exit(1)

    # 3. Build prompt
    system_prompt, user_message = build_messages(question, chunks)

    # 4. Stream from Claude
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                sys.stdout.write(f"TOKEN:{text}\n")
                sys.stdout.flush()
    except Exception as e:
        sys.stdout.write(f"ERROR:Claude API error — {e}\n")
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
