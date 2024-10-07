#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#导出aws ec2实例清单到csv

import boto3
import csv
import time

ec2 = boto3.client(
    'ec2',
    aws_access_key_id="",    # access key id,控制台申请
    aws_secret_access_key="",
    region_name='ap-southeast-1',
)

res = ec2.describe_instances()   # 返回字典类型
filename = "/root/aws_" + time.strftime("%Y-%m-%d", time.localtime()) + ".csv"  
with open(filename, 'w', encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    csv_head = ["InstanceId", "InstanceType", "Tags", "PrivateIpAddress", "PublicIpAddress", "Platform", "VCpuInfo","MemoryInfo"]  # 自己想要得到的实例属性
    writer.writerow(csv_head)
    num_of_keys = len(res['Reservations'])  # 列表 'Reservations' 包含的元素数量（不一定就是实例数量）
    for num in range(0, num_of_keys):
        num_of_ins = len(res['Reservations'][num]['Instances'])  # 每个'Instances' 列表包含的元素数量，即实例数，不一定只有一个实例，可能多个
        for i in range(0, num_of_ins):
            InstanceId = res['Reservations'][num]['Instances'][i]['InstanceId']   #根据返回的字典取出对应属性值，返回的字典可到json解析网站解析方便查看结构，列表元素取值要加下标，即num和i
            InstanceType = res['Reservations'][num]['Instances'][i]['InstanceType']
            Tags = res['Reservations'][num]['Instances'][i]['Tags'][0]['Value']
            #CoreCount = res['Reservations'][num]['Instances'][i]['CpuOptions']['CoreCount']
            Platform = res['Reservations'][num]['Instances'][i]['Platform'] if 'Platform' in \
                                                                               res['Reservations'][num]['Instances'][
                                                                                   i] else "linux"   
            PrivateIpAddress = res['Reservations'][num]['Instances'][i]['PrivateIpAddress']
            PublicIpAddress = res['Reservations'][num]['Instances'][i]['PublicIpAddress']
            InstanceTypes = ec2.describe_instance_types(InstanceTypes=[InstanceType])    #调用另一个api获取实例类型的详细信息以取得cpu个数和内存大小的值
            MemoryInfo = InstanceTypes['InstanceTypes'][0]['MemoryInfo']['SizeInMiB']
            VCpuInfo = InstanceTypes['InstanceTypes'][0]['VCpuInfo']['DefaultVCpus']
            row_csv = [InstanceId, InstanceType, Tags, PrivateIpAddress, PublicIpAddress, Platform, VCpuInfo, MemoryInfo]
            writer.writerow(row_csv)  # 写入csv
            print(InstanceId, InstanceType, Tags, PrivateIpAddress, PublicIpAddress, Platform, VCpuInfo, MemoryInfo)
