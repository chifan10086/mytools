import json

import requests

# ============ 配置 ============
BASE_URL = "https://deepseeknow.ai"
API_KEY = "sk-e5WTZdvsc6m6OF6D7F39wZHaQWBfrKCxoxeal9UI8UZDuliS"
# 用于校验的模型 id（/v1/models 返回里应包含此项）
TARGET_MODEL = "gpt-5.2-my"
# ==============================

url = f"{BASE_URL.rstrip('/')}/v1/models"

response = requests.get(
    url,
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30,
)

print(f"GET {url}")
print(f"HTTP {response.status_code}\n")

try:
    payload = response.json()
except ValueError:
    print(response.text)
    raise SystemExit(1)

models = payload.get("data", []) if isinstance(payload, dict) else []

if models:
    ids = sorted(
        (m.get("id", "") for m in models if isinstance(m, dict)),
        key=str.lower,
    )
    width = max(len(i) for i in ids)
    print(f"共 {len(ids)} 个模型：\n")
    for idx, mid in enumerate(ids, 1):
        print(f"  {idx:>3}. {mid:<{width}}")

    print()
    want = TARGET_MODEL.lower()
    actual = next((i for i in ids if i.lower() == want), None)
    if actual:
        print(f"[OK] 目标模型在列表中：{actual!r}（期望 {TARGET_MODEL!r}）")
    else:
        print(f"[FAIL] 目标模型 `{TARGET_MODEL}` 不在列表中。")
        raise SystemExit(1)
else:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
