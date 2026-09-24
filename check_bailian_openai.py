import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv(".env")
    config_path = Path("config.json")
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    model = os.getenv("MODEL", "").strip() or str(config.get("model") or "qwen3.7-plus")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "").strip() or "https://dashscope.aliyuncs.com/compatible-mode/v1"

    print("DASHSCOPE_API_KEY configured:", bool(api_key))
    print("DASHSCOPE_API_KEY prefix:", f"{api_key[:8]}..." if api_key else "")
    print("MODEL:", model)
    print("BASE_URL:", base_url)

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "hello"}],
    )
    print("id:", response.id)
    print("model:", response.model)
    print("content:", response.choices[0].message.content)


if __name__ == "__main__":
    main()
