#!/usr/bin/env python3

domains = []

with open('domains.txt', 'r', encoding='utf-8') as file:
    # 逐行读取文件，并去除末尾的空行
    for line in file:
        line = line.rstrip()  # 去除行末尾的空白字符，包括换行符
        if line:  # 仅处理非空行
            domains.append(line)

def getzoneid(domain):
    params = {
    "Filters": [
        {
            "Name": "zone-name",
            "Values": [
                domain
            ],
            "Fuzzy": "false"
        }
    ]
    }
    print(params)


for domain in domains:
    #rint(domain)
    getzoneid(domain)
