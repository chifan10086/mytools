#!/usr/bin/env python3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from config import  ALLOWED_GROUP_ID
import logging
import re
import jenkins
import requests
#from option import delete_bwjx,delete_ppjx
from option import *
# 设置日志记录
#logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
#logger = logging.getLogger(__name__)

USAGE_INSTRUCTIONS = ""
# 定义对话的不同状态
CHOOSING,DOMAINS = range(2)

# 开始命令处理函数
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return

    chat_id = update.message.chat_id
    print(chat_id)

    # 检查是否在允许的群组中
    if chat_id != ALLOWED_GROUP_ID:
        await update.message.reply_text("此机器人仅在指定群组中运行。")
        return ConversationHandler.END
    keyboard = [
        [
#            InlineKeyboardButton("极星", callback_data='ppjx'),
            InlineKeyboardButton("极星", callback_data='bwjx'),
        ],
       [
#           InlineKeyboardButton("PP-CF", callback_data='ppcf'),
           InlineKeyboardButton("BW-CF", callback_data='bwcf'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('请选择CDN厂商:', reply_markup=reply_markup)
    return CHOOSING


# 定义按钮回调处理函数
async def cdn_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice == 'ppjx':
        keyboard = [
                [InlineKeyboardButton("增加域名", callback_data=f'add:ppjx')],
            [InlineKeyboardButton("删除域名", callback_data=f'delete:ppjx')],
                 ]
        await query.edit_message_text(f"你选择PP极星，接下来选择操作：",reply_markup=InlineKeyboardMarkup(keyboard))
    if choice == 'bwjx':
        keyboard = [
            [InlineKeyboardButton("增加域名", callback_data=f'add:bwjx')],
            [InlineKeyboardButton("删除域名", callback_data=f'delete:bwjx')],
                 ]
        await query.edit_message_text(f"你选择BW极星，接下来选择操作：",reply_markup=InlineKeyboardMarkup(keyboard))
    if choice == 'ppcf':
        keyboard = [
            [InlineKeyboardButton("增加域名", callback_data=f'add:ppcf')],
            [InlineKeyboardButton("删除域名", callback_data=f'delete:ppcf')],
                 ]
        await query.edit_message_text(f"你选择BW极星，接下来选择操作：",reply_markup=InlineKeyboardMarkup(keyboard))
    if choice == 'bwcf':
        keyboard = [
            [InlineKeyboardButton("增加域名", callback_data=f'add:bwcf')],
            [InlineKeyboardButton("删除域名", callback_data=f'delete:bwcf')],
                 ]
        await query.edit_message_text(f"你选择BW极星，接下来选择操作：",reply_markup=InlineKeyboardMarkup(keyboard))


    return CHOOSING



# 处理用户操作选择，提示用户输入文字
async def operation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    
    # 解析用户选择的操作
    operation, choice = query.data.split(":")[0], query.data.split(":")[1]

    # 动态反馈用户选择，提示输入
    await query.edit_message_text(f"你选择了操作 {choice}，请输入要{operation} 的域名：")

    # 保存选择的操作和选项到上下文中，以便后续处理
    context.user_data['operation'] = operation
    context.user_data['choice'] = choice

    print(query.data)

    # 进入文字输入阶段
    return DOMAINS


# 处理用户文本输入
async def received_domains(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    operation = context.user_data.get('operation')
    choice = context.user_data.get('choice')
    domains = user_input.replace(" ", "\n").splitlines()
    caozuo = operation+'_'+choice
    output = findfunc(caozuo,domains)
    print(output)
    for result, message in output:
        print(f"Result: {result}, Message: {message}")
        await update.message.reply_text(f"'{result}'，操作 {operation} {message}")
    return ConversationHandler.END

# 取消对话
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("对话已取消。")
    return ConversationHandler.END



# 主函数
def main():
    application = ApplicationBuilder().token('').build()

    # 创建对话处理器
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('cdn', start)],
        states={
            CHOOSING: [CallbackQueryHandler(cdn_choice, pattern='^(pp|bw)'),
                       CallbackQueryHandler(operation_handler, pattern='^(add|delete):')],
            DOMAINS: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_domains)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # 注册对话处理器
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()

# config.py
# Telegram 机器人 API Token

# 允许操作的Telegram群组ID
#ALLOWED_GROUP_ID = 
