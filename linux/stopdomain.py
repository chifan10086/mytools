
#!/usr/bin/env python3
# -*- coding: utf-8 -*oimport sys-
import sys
import json
import subprocess
import hashlib, hmac, json, os, sys, time
from datetime import datetime

# 密钥参数
# 需要设置环境变量 TENCENTCLOUD_SECRET_ID，值为示例的 AKIDz8krbsJ5yKBZQpn74WFkmLPx3*******
#secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID")
# 需要设置环境变量 TENCENTCLOUD_SECRET_KEY，值为示例的 Gu5t9xGARNpq86cd98joQYCN3*******
#secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY")

secret_id = 
secret_key  = 

service = "teo"
host = "teo.tencentcloudapi.com"
endpoint = "https://" + host
version = "2022-09-01"
algorithm = "TC3-HMAC-SHA256"
timestamp = int(time.time())
date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

# ************* 步骤 1：拼接规范请求串 *************

http_request_method = "POST"
canonical_uri = "/"
canonical_querystring = ""
ct = "application/json; charset=utf-8"
signed_headers = "content-type;host;x-tc-action"






# ************* 步骤 3：计算签名 *************
# 计算签名摘要函数
def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


domains = []

with open('domains.txt', 'r', encoding='utf-8') as file:
    # 逐行读取文件，并去除末尾的空行
    for line in file:
        line = line.rstrip()  # 去除行末尾的空白字符，包括换行符
        if line:  # 仅处理非空行
            domains.append(line)

def getcomand(action,params):
    canonical_headers = "content-type:%s\nhost:%s\nx-tc-action:%s\n" % (ct, host, action.lower())
    payload = json.dumps(params)
    hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (http_request_method + "\n" +
                        canonical_uri + "\n" +
                        canonical_querystring + "\n" +
                        canonical_headers + "\n" +
                        signed_headers + "\n" +
                        hashed_request_payload)
    credential_scope = date + "/" + service + "/" + "tc3_request"
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = (algorithm + "\n" +
                    str(timestamp) + "\n" +
                    credential_scope + "\n" +
                    hashed_canonical_request)
    secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = sign(secret_date, service)
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    print(signature)

    # ************* 步骤 4：拼接 Authorization *************
    authorization = (algorithm + " " +
                    "Credential=" + secret_id + "/" + credential_scope + ", " +
                    "SignedHeaders=" + signed_headers + ", " +
                    "Signature=" + signature)
#    print(authorization)
    command1 = 'curl -X POST ' + endpoint + ' -H "Authorization: ' + authorization + '"'+ ' -H "Content-Type: application/json; charset=utf-8"'+ ' -H "Host: ' + host + '"'+ ' -H "X-TC-Action: ' + action + '"'+ ' -H "X-TC-Timestamp: ' + str(timestamp) + '"'+ ' -H "X-TC-Version: ' + version + '"'+ " -d '" + payload + "'"
    print(params)
    print(command1)
    return command1

def getzoneid(domain):
    action = "DescribeZones"
    params = {
    "Filters": [
        {
            "Name": "zone-name",
            "Values": [
                domain
            ]
           # "Fuzzy": "false"
        }
    ]
    }
    command1 = getcomand(action,params)
    pipe = subprocess.Popen(command1, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print('命令返回结果')
    result = pipe.stdout.read().decode()
    data = json.loads(result)
    zoneid = data['Response']['Zones'][0]['ZoneId']
    return zoneid

def gohttps(zoneid):
    action = "ModifyZoneSetting"
    params = {
            "ZoneId": zoneid,
           "ForceRedirect" : {
                                'RedirectStatusCode': 302,
                                'Switch': 'on'
                        }

            #"Https":{
            #"Switch": "on"
   #  }
     }
    command1 = getcomand(action,params)
    pipe = subprocess.Popen(command1, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print('命令返回结果')
    result = pipe.stdout.read().decode()
    data = json.loads(result)
    print(data)

def stop(zoneid):
    action = "ModifyZoneStatus"
    params = {
            "ZoneId": zoneid,
            "Paused": True
       }
    command1 = getcomand(action,params)
    pipe = subprocess.Popen(command1, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print('命令返回结果')
    result = pipe.stdout.read().decode()
    data = json.loads(result)
    print(data)

for domain in domains:
    zoneid = getzoneid(domain)
    stop(zoneid)
