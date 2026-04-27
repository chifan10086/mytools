import json
import sys
from typing import Any

import requests

# ============ 配置（在此填写） ============

BASE_URL = "https://deepseeknow.ai"
API_KEY = "sk-e5WTZdvsc6m6OF6D7F39wZHaQWBfrKCxoxeal9UI8UZDuliS"
# 默认只测该模型；MODELS 非空则只用列表；二者都空则从 /v1/models 拉全量
CHAT_MODEL = "deployllm"
MODELS: list[str] = []

USER_PROMPT = "只回复一个字：ok"
# 留空则不插入系统类消息；非空则作为首条消息
SYSTEM_PROMPT = ""
# system 或 developer
SYSTEM_ROLE = "system"
# ========================================


def _explicit_model_ids() -> list[str]:
    if MODELS:
        return MODELS
    return [CHAT_MODEL] if CHAT_MODEL.strip() else []


def get_models(base_url: str, api_key: str, explicit: list[str]) -> list[str]:
    if explicit:
        return explicit
    r = requests.get(
        f"{base_url.rstrip('/')}/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json().get("data", [])
    return sorted(
        {m.get("id", "") for m in data if isinstance(m, dict) and m.get("id")},
        key=str.lower,
    )


def build_messages() -> list[dict[str, str]]:
    role = (SYSTEM_ROLE or "system").strip().lower() or "system"
    if role not in ("system", "developer"):
        role = "system"
    messages: list[dict[str, str]] = []
    sys_text = (SYSTEM_PROMPT or "").strip()
    if sys_text:
        messages.append({"role": role, "content": sys_text})
    messages.append({"role": "user", "content": USER_PROMPT})
    return messages


def try_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[bool, str]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "stream": False,
            },
            timeout=60,
        )
    except requests.RequestException as e:
        return False, f"请求异常: {e}"

    try:
        data: Any = r.json()
    except ValueError:
        return False, f"HTTP {r.status_code} 非JSON: {r.text[:200]}"

    if r.ok and isinstance(data, dict) and data.get("choices"):
        content = (data["choices"][0].get("message") or {}).get("content", "")
        return True, (content or "").strip().replace("\n", " ")[:80]

    err = data.get("error") if isinstance(data, dict) else None
    msg = (err or {}).get("message") if isinstance(err, dict) else None
    return False, f"HTTP {r.status_code} {msg or json.dumps(data, ensure_ascii=False)[:200]}"


def main() -> int:
    base = BASE_URL.strip().rstrip("/")
    key = API_KEY.strip()
    if not base or "your-gateway" in base:
        print("请在脚本顶部填写 BASE_URL。", file=sys.stderr)
        return 2
    if not key:
        print("请在脚本顶部填写 API_KEY。", file=sys.stderr)
        return 2

    explicit = _explicit_model_ids()
    messages = build_messages()

    try:
        models = get_models(base, key, explicit)
    except requests.RequestException as e:
        print(f"获取模型列表失败: {e}", file=sys.stderr)
        return 1

    if not models:
        print("没有获取到任何模型。")
        return 1

    print(f"共 {len(models)} 个模型，POST /v1/chat/completions ...\n")

    name_width = max(len(m) for m in models)
    ok_list: list[str] = []
    fail_list: list[tuple[str, str]] = []

    for idx, model in enumerate(models, 1):
        ok, info = try_chat(base, key, model, messages)
        status = "✅ OK " if ok else "❌ FAIL"
        print(f"[{idx:>2}/{len(models)}] {status} {model:<{name_width}}  {info}")
        if ok:
            ok_list.append(model)
        else:
            fail_list.append((model, info))

    print("\n================ 汇总 ================")
    print(f"可用模型 ({len(ok_list)}):")
    for m in ok_list:
        print(f"  - {m}")

    print(f"\n不可用模型 ({len(fail_list)}):")
    for m, info in fail_list:
        print(f"  - {m}  ->  {info}")

    return 0 if ok_list else 2


if __name__ == "__main__":
    raise SystemExit(main())
