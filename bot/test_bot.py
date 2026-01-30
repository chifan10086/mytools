#!/usr/bin/env python3
"""
测试机器人连接和群组消息发送
"""
from telegram import Bot
from config import API_TOKEN, ALLOWED_GROUP_ID
import asyncio

async def test_bot():
    """测试机器人发送消息到群组"""
    try:
        # 创建机器人实例
        bot = Bot(token=API_TOKEN)
        
        # 获取机器人信息
        bot_info = await bot.get_me()
        print(f"✅ 机器人连接成功！")
        print(f"   机器人名称: {bot_info.first_name}")
        print(f"   机器人用户名: @{bot_info.username}")
        print(f"   机器人ID: {bot_info.id}")
        print()
        
        # 发送测试消息到群组
        print(f"📤 正在发送测试消息到群组 {ALLOWED_GROUP_ID}...")
        message = await bot.send_message(
            chat_id=ALLOWED_GROUP_ID,
            text="🤖 机器人测试消息\n\n如果你看到这条消息，说明机器人配置成功！"
        )
        
        print(f"✅ 消息发送成功！")
        print(f"   消息ID: {message.message_id}")
        print(f"   发送时间: {message.date}")
        print()
        print("🎉 测试完成！机器人可以正常工作了。")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        print("可能的原因：")
        print("1. API_TOKEN 不正确")
        print("2. ALLOWED_GROUP_ID 不正确")
        print("3. 机器人未添加到群组")
        print("4. 机器人没有在群组中发送消息的权限")
        print("5. 网络连接问题")

if __name__ == '__main__':
    print("=" * 50)
    print("Telegram 机器人测试程序")
    print("=" * 50)
    print()
    print(f"API_TOKEN: {API_TOKEN[:20]}..." if API_TOKEN else "API_TOKEN: 未设置")
    print(f"ALLOWED_GROUP_ID: {ALLOWED_GROUP_ID}")
    print()
    
    # 运行异步函数
    asyncio.run(test_bot())
