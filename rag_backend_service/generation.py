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
import os
import openai

from generate_query_embed import embed_query
from retrieval import retrieve
from prepare_prompt import build_messages

FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
MODEL   = "accounts/fireworks/models/gpt-oss-120b"
TOP_K   = 10
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

    # 4. Stream from Fireworks
    client = openai.OpenAI(
        base_url=FIREWORKS_BASE_URL,
        api_key=os.environ["FIREWORKS_API_KEY"],
    )

    try:
        stream = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
        )
        for chunk in stream:
            text = chunk.choices[0].delta.content
            if text:
                sys.stdout.write(f"TOKEN:{text}\n")
                sys.stdout.flush()
    except Exception as e:
        sys.stdout.write(f"ERROR:Fireworks API error — {e}\n")
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
