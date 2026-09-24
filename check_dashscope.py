import os
import json
from pathlib import Path

from dotenv import load_dotenv
import dashscope


def main() -> None:
    load_dotenv(".env")
    config_path = Path("config.json")
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    model = os.getenv("MODEL", "").strip() or str(config.get("model") or "qwen-plus")
    print("DASHSCOPE_API_KEY configured:", bool(api_key))
    print("DASHSCOPE_API_KEY prefix:", f"{api_key[:8]}..." if api_key else "")
    print("MODEL:", model)

    response = dashscope.Generation.call(
        api_key=api_key,
        model=model,
        messages=[{"role": "user", "content": "hello"}],
        result_format="message",
    )
    print("status_code:", getattr(response, "status_code", None))
    print("code:", getattr(response, "code", None))
    print("message:", getattr(response, "message", None))
    print("request_id:", getattr(response, "request_id", None))
    print("output:", getattr(response, "output", None))


if __name__ == "__main__":
    main()
