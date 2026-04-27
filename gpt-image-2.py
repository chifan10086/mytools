#!/usr/bin/env python3
import requests
import base64
from datetime import datetime

API_KEY = "sk-aBxtJaf3e5J2BtglBJPnchL1E6KJ6WL98BDeOjjNiN543v5U"
URL = "https://aimodelshub.net/v1/images/generations"

prompt = "一只可爱的猪坐在窗台上晒太阳"

response = requests.post(URL,
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={"model": "gpt-image-2", "prompt": prompt, "n": 1, "size": "1024x1024", "quality": "low"}
)

result = response.json()
print(result)

for i, img in enumerate(result.get("data", [])):
    filename = f"generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i+1}.png"
    if "b64_json" in img:
        with open(filename, "wb") as f:
            f.write(base64.b64decode(img["b64_json"]))
    elif "url" in img:
        with open(filename, "wb") as f:
            f.write(requests.get(img["url"], timeout=60).content)
    print(f"已保存: {filename}")
