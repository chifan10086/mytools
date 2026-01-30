#!/bin/bash
# 停止所有 mailbot 进程

echo "正在查找 mailbot 进程..."
PROCESSES=$(ps aux | grep -E "mailbot\.py|python.*mailbot" | grep -v grep)

if [ -z "$PROCESSES" ]; then
    echo "没有找到运行中的 mailbot 进程"
else
    echo "找到以下进程："
    echo "$PROCESSES"
    echo ""
    echo "正在停止所有 mailbot 进程..."
    pkill -f mailbot.py
    sleep 2
    
    # 检查是否还有进程
    REMAINING=$(ps aux | grep -E "mailbot\.py|python.*mailbot" | grep -v grep)
    if [ -z "$REMAINING" ]; then
        echo "✅ 所有 mailbot 进程已停止"
    else
        echo "⚠️  仍有进程在运行，尝试强制停止..."
        pkill -9 -f mailbot.py
        sleep 1
        echo "✅ 强制停止完成"
    fi
fi
