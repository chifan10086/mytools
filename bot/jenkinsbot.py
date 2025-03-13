#!/usr/bin/env python3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from config import API_TOKEN, ALLOWED_GROUP_ID
import logging
import re
import jenkins
import requests
from k import deploypro,deployeks
# 设置日志记录
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.WARNING)
logger = logging.getLogger(__name__)

USAGE_INSTRUCTIONS = ""

# 定义对话的不同步骤
DEPLOYVIEW, TAGS = range(2)

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
#            InlineKeyboardButton("PP-Soa-Web", callback_data='deploy_soa_web'),
            InlineKeyboardButton("BW-Sob-Web", callback_data='deploy_sob_web'),
            InlineKeyboardButton("BW-Nsa-Web", callback_data='deploy_nsa_web')
        ],
       [
#            InlineKeyboardButton("PP-Soa-Eks", callback_data='deploy_soa_eks'),
            InlineKeyboardButton("BW-Sob-Eks", callback_data='deploy_sob_eks'),
            InlineKeyboardButton("BW-Nsa-Eks", callback_data='deploy_nsa_eks')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('请选要发布的环境:', reply_markup=reply_markup)
    return DEPLOYVIEW


# 定义按钮回调处理函数
async def task_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # 根据用户选择的任务做出不同的响应
    if query.data == 'deploy_soa_web':
        await query.edit_message_text(text="你选择了soa_web。请输入相关标签:")
        context.user_data['task'] = 'PP-Soa-Web'
        return TAGS
    elif query.data == 'deploy_sob_web':
        await query.edit_message_text(text="<b>你选择了sob_web。请输入标签:</b>",parse_mode='HTML')
        context.user_data['task'] = 'BW-Sob-Web'
        return TAGS
    elif query.data == 'deploy_nsa_web':
        await query.edit_message_text(text="<b>你选择了nsa_web。请输入标签:</b>")
        context.user_data['task'] = 'BW-Nsa-Web'
        return TAGS
    elif query.data == 'deploy_soa_eks':
        await query.edit_message_text(text="<b>你选择了soa-eks。请输入标签:</b>")
        context.user_data['task'] = 'PP-Soa-Eks'
        return TAGS
    elif query.data == 'deploy_sob_eks':
        await query.edit_message_text(text="<b>你选择了sob-eks。请输入标签:</b>")
        context.user_data['task'] = 'BW-Sob-Eks'
        return TAGS
    elif query.data == 'deploy_nsa_eks':
        await query.edit_message_text(text="<b>你选择了nsa_eks。请输入标签:</b>")
        context.user_data['task'] = 'BW-Nsa-Eks'
        return TAGS
    else:
        await query.edit_message_text(text="已取消操作。")
        return ConversationHandler.END

# 接收用户输入数据
async def input_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    task = context.user_data.get('task', '未知任务')
    lines = user_input.replace(" ", "\n").splitlines()
    logger.error(f"用户输入的内容: {lines}")

#    test(task,lines)
#    deploypro(task,user_input)
    if 'web' in task.lower():
        status, message, result = deploypro(task,lines)
    elif 'eks' in task.lower():
        status, message, result = deployeks(task,lines)
    else:
        await update.message.reply_text(f"不存在的任务")
        return ConversationHandler.END
    ts = '\n'.join(lines)
    if status == 0:
         await update.message.reply_text(f"你选择了{task}，\n 并输入了标签:\n<code>{ts}</code> \n 已匹配到{message}个任务\n 请注意查看发布群消息",parse_mode='HTML')
    elif status == 1:
        await update.message.reply_text(f"你选择了{task}，\n 并输入了标签: \n {ts} \n {message}")
    elif status == 2:
        await update.message.reply_text(f"你选择了{task}，\n 并输入了标签: \n {ts} \n {message}")
    else:
        print(f"发生了未知错误: {message}")

    # 完成后返回结束状态
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
        entry_points=[CommandHandler('jenkins', start)],
        states={
            DEPLOYVIEW: [CallbackQueryHandler(task_choice)],
            TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_data)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # 注册对话处理器
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
