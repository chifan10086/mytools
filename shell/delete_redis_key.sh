#!/bin/bash

pattern="Plane*"  # 替换为你要查找的键模式
total_keys=0
hosts=""
mport=1860
# 获取所有主节点
for node in $(redis-cli -h $hosts -c -p $mport cluster nodes | grep master | awk '{print $2}' | sed 's/@.*//'); do
    host=$(echo $node | cut -d: -f1)
    port=$(echo $node | cut -d: -f2)
    echo $host:$port   
    # 在每个主节点上执行 SCAN 命令查找匹配的键
    keys=$(redis-cli -h $host -p $port --scan --pattern "$pattern")
    echo $keys   
    redis-cli -h $host -p $port DEL $keys
    # 统计找到的键数量
    count=$(echo "$keys" | wc -l)
    total_keys=$((total_keys + count))
done

echo "Total keys matching pattern '$pattern' in cluster: $total_keys"
