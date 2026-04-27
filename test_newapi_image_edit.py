#!/usr/bin/env python3
import os
import sys
import requests

NEWAPI_API_KEY = os.getenv("NEWAPI_API_KEY", "sk-aBxtJaf3e5J2BtglBJPnchL1E6KJ6WL98BDeOjjNiN543v5U")
NEWAPI_URL = "https://aimodelshub.net/v1/images/edits"

# 支持命令行传入图片路径，否则使用默认列表
if len(sys.argv) > 1:
    image_paths = sys.argv[1:]
else:
    image_paths = [
        "body-lotion.png",
        "bath-bomb.png",
        "incense-kit.png",
        "soap.png",
    ]

# 检查所有文件是否存在
missing = [p for p in image_paths if not os.path.exists(p)]
if missing:
    print(f"错误：以下图片文件不存在：")
    for p in missing:
        print(f"  {p}")
    sys.exit(1)

file_handles = []
files = []
for path in image_paths:
    f = open(path, "rb")
    file_handles.append(f)
    filename = os.path.basename(path)
    files.append(("image[]", (filename, f, "image/png")))

data = {
    "model": "gpt-image-1",
    "prompt": "创建一个包含这四个物品的精美礼品篮",
    "quality": "high"
}

headers = {
    "Authorization": f"Bearer {NEWAPI_API_KEY}"
}

print(f"正在上传 {len(files)} 张图片并请求生成...")
response = requests.post(NEWAPI_URL, headers=headers, data=data, files=files)

for f in file_handles:
    f.close()

print(f"状态码: {response.status_code}")
try:
    print(f"响应: {response.json()}")
except Exception:
    print(f"响应内容: {response.text}")
