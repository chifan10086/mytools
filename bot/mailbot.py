#!/usr/bin/env python3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from config import ALLOWED_GROUP_ID, API_TOKEN
import logging
import subprocess
import os
import re
import random
import string
import signal
import sys
from datetime import datetime

# 设置日志记录
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.WARNING)
logger = logging.getLogger(__name__)

# 定义对话的不同状态
CHOOSING, DOMAIN_SELECT, EMAIL_INPUT, PASSWORD_INPUT = range(4)

# 邮箱账号密码记录文件
EMAIL_RECORD_FILE = 'x.txt'

# 默认域名
DEFAULT_DOMAIN = 'cloudvip8.com'

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
        [InlineKeyboardButton("增加邮箱单个", callback_data='add_email_single')],
        [InlineKeyboardButton("增加邮箱随机5个", callback_data='add_email_random')],
        [InlineKeyboardButton("修改密码", callback_data='change_password')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('请选择操作:', reply_markup=reply_markup)
    return CHOOSING


# 处理操作选择
async def operation_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    operation = query.data
    context.user_data['operation'] = operation
    
    if operation == 'add_email_single':
        # 直接接收完整邮箱地址和密码
        reply_markup = create_cancel_back_keyboard(show_back=True)
        await query.edit_message_text('请输入完整邮箱地址（格式：username@domain）:', reply_markup=reply_markup)
        return EMAIL_INPUT
    elif operation == 'add_email_random':
        # 显示域名选择按钮
        keyboard = [
            [InlineKeyboardButton("cloudvip8.com", callback_data='domain_cloudvip8.com')],
            [InlineKeyboardButton("🔙 返回", callback_data='back')],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('请选择域名:', reply_markup=reply_markup)
        return DOMAIN_SELECT
    elif operation == 'change_password':
        reply_markup = create_cancel_back_keyboard(show_back=True)
        await query.edit_message_text('请输入要修改密码的邮箱地址（格式：username@domain）:', reply_markup=reply_markup)
        return EMAIL_INPUT
    
    return EMAIL_INPUT


# 处理域名选择
async def domain_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理域名选择"""
    query = update.callback_query
    await query.answer()
    
    # 从回调数据中提取域名（格式：domain_cloudvip8.com）
    domain = query.data.replace('domain_', '')
    context.user_data['domain'] = domain
    
    operation = context.user_data.get('operation')
    
    if operation == 'add_email_random':
        # 随机生成5个邮箱
        await query.edit_message_text(f'已选择域名: {domain}\n正在生成5个随机邮箱，请稍候...')
        result_message = await generate_random_emails(domain)
        await query.edit_message_text(result_message)
        return ConversationHandler.END
    
    return EMAIL_INPUT


# 处理邮箱地址输入
async def received_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return
    
    operation = context.user_data.get('operation')
    
    if operation == 'add_email_single':
        # 单个添加邮箱，输入的是完整邮箱地址
        email = update.message.text.strip()
        
        # 验证邮箱格式
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            reply_markup = create_cancel_back_keyboard(show_back=True)
            await update.message.reply_text('❌ 邮箱格式不正确，请重新输入（格式：username@domain）:', reply_markup=reply_markup)
            return EMAIL_INPUT
        
        # 检查邮箱是否已存在
        if await email_exists(email):
            reply_markup = create_cancel_back_keyboard(show_back=True)
            await update.message.reply_text(f'❌ 邮箱 {email} 已存在，请使用其他邮箱地址:', reply_markup=reply_markup)
            return EMAIL_INPUT
        
        context.user_data['email'] = email
        reply_markup = create_cancel_back_keyboard(show_back=True)
        await update.message.reply_text('请输入密码:', reply_markup=reply_markup)
        return PASSWORD_INPUT
    elif operation == 'change_password':
        # 修改密码，输入的是完整邮箱地址
        email = update.message.text.strip()
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            reply_markup = create_cancel_back_keyboard(show_back=True)
            await update.message.reply_text('邮箱格式不正确，请重新输入（格式：username@domain）:', reply_markup=reply_markup)
            return EMAIL_INPUT
        context.user_data['email'] = email
        reply_markup = create_cancel_back_keyboard(show_back=True)
        await update.message.reply_text('请输入新密码:', reply_markup=reply_markup)
        return PASSWORD_INPUT
    
    return EMAIL_INPUT


# 处理密码输入并执行操作
async def received_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return
    
    password = update.message.text.strip()
    email = context.user_data.get('email')
    operation = context.user_data.get('operation')
    
    if not email or not operation:
        await update.message.reply_text('操作失败：缺少必要信息。')
        return ConversationHandler.END
    
    try:
        if operation == 'add_email_single':
            # 再次检查邮箱是否已存在（防止并发）
            if await email_exists(email):
                await update.message.reply_text(f'❌ 邮箱 {email} 已存在，无法添加！')
                return ConversationHandler.END
            
            # 添加邮箱前，先写入 x.txt（只写入邮箱地址）
            await write_email_to_file(email, password)
            
            # 执行 docker 命令添加邮箱（仅打印，不实际执行）
            result = await execute_docker_command('add', email, password)
            
            if result['success']:
                await update.message.reply_text(f"账号 {email}\n密码: {password}")
            else:
                await update.message.reply_text(f"❌ 邮箱添加失败！\n{result['message']}")
        
        elif operation == 'change_password':
            # 执行 docker 命令修改密码
            result = await execute_docker_command('update', email, password)
            
            if result['success']:
                await update.message.reply_text(f"账号 {email}\n密码已修改")
            else:
                await update.message.reply_text(f"❌ 密码修改失败！\n{result['message']}")
    
    except Exception as e:
        logger.error(f"执行操作时出错: {e}")
        await update.message.reply_text(f"❌ 操作失败：{str(e)}")
    
    return ConversationHandler.END


# 检查邮箱是否已存在
async def email_exists(email: str) -> bool:
    """检查邮箱是否已存在于 x.txt 文件中"""
    try:
        if not os.path.exists(EMAIL_RECORD_FILE):
            return False
        
        with open(EMAIL_RECORD_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                # 只检查邮箱地址（去除空白字符）
                existing_email = line.strip()
                if existing_email == email:
                    return True
        return False
    except Exception as e:
        logger.error(f"检查邮箱是否存在时出错: {e}")
        return False


# 写入邮箱账号到文件（只写入邮箱地址）
async def write_email_to_file(email: str, password: str = None):
    """将邮箱账号写入 x.txt 文件（只写入邮箱地址）"""
    try:
        # 只写入邮箱地址
        with open(EMAIL_RECORD_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{email}\n")
        
        logger.info(f"邮箱已写入文件: {email}")
    except Exception as e:
        logger.error(f"写入文件失败: {e}")
        raise


# 生成随机邮箱和密码
async def generate_random_emails(domain: str = None) -> str:
    """随机生成5个邮箱和密码"""
    if domain is None:
        domain = DEFAULT_DOMAIN
    results = []
    max_attempts = 20  # 最多尝试20次，确保生成5个不重复的邮箱
    attempts = 0
    
    while len(results) < 5 and attempts < max_attempts:
        attempts += 1
        
        # 生成随机用户名（1-5位字母数字组合）
        username_length = random.randint(1, 5)
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=username_length))
        email = f"{username}@{domain}"
        
        # 检查邮箱是否已存在
        if await email_exists(email):
            continue  # 如果已存在，跳过，继续生成下一个
        
        # 生成随机密码（12位，包含大小写字母、数字和特殊字符）
        password_length = 12
        password_chars = string.ascii_letters + string.digits + '!@#$%^&*'
        password = ''.join(random.choices(password_chars, k=password_length))
        
        # 写入文件（只写入邮箱地址）
        await write_email_to_file(email, password)
        
        # 执行 docker 命令（仅打印）
        result = await execute_docker_command('add', email, password)
        
        results.append({
            'email': email,
            'password': password,
            'success': result['success'],
            'message': result['message']
        })
    
    # 格式化返回消息
    success_count = sum(1 for r in results if r['success'])
    message_lines = [f"已生成 {len(results)}/5 个账号（成功: {success_count}）：\n"]
    
    for i, r in enumerate(results, 1):
        status = "账号" if r['success'] else "❌"
        message_lines.append(f"{i}. {status} {r['email']}")
        message_lines.append(f"   密码: {r['password']}")
        if not r['success']:
            message_lines.append(f"   错误: {r['message']}")
        message_lines.append("")
    
    if len(results) < 5:
        message_lines.append(f"⚠️ 注意：由于邮箱已存在，只生成了 {len(results)} 个新邮箱")
    
    return "\n".join(message_lines)


# 执行 docker 命令
async def execute_docker_command(operation: str, email: str, password: str) -> dict:
    """
    执行 docker 命令
    operation: 'add' 或 'update'
    email: 邮箱地址
    password: 密码
    """
    try:
        if operation == 'add':
            # docker exec -i mailserver setup email add username@domain password
            cmd = ['docker', 'exec', '-i', 'mailserver', 'setup', 'email', 'add', email, password]
        elif operation == 'update':
            # docker exec -i mailserver setup email update username@domain password
            cmd = ['docker', 'exec', '-i', 'mailserver', 'setup', 'email', 'update', email, password]
        else:
            return {'success': False, 'message': '未知的操作类型'}
        
        # 执行 docker 命令
        cmd_str = ' '.join(cmd)
        logger.info(f"执行Docker命令: {cmd_str}")
        
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if process.returncode == 0:
            output = process.stdout.strip()
            logger.info(f"Docker命令执行成功: {output if output else '无输出'}")
            return {'success': True, 'message': output if output else '操作成功'}
        else:
            error = process.stderr.strip()
            logger.error(f"Docker命令执行失败: {error if error else '未知错误'}")
            return {'success': False, 'message': error if error else '命令执行失败'}
    
    except subprocess.TimeoutExpired:
        logger.error("Docker命令执行超时")
        return {'success': False, 'message': '命令执行超时'}
    except Exception as e:
        logger.error(f"Docker 命令执行失败: {e}")
        return {'success': False, 'message': f'执行失败: {str(e)}'}


# 创建取消/返回按钮
def create_cancel_back_keyboard(show_back: bool = True):
    """创建取消和返回按钮"""
    keyboard = []
    if show_back:
        keyboard.append([InlineKeyboardButton("🔙 返回", callback_data='back')])
    keyboard.append([InlineKeyboardButton("❌ 取消", callback_data='cancel')])
    return InlineKeyboardMarkup(keyboard)


# 返回上一步
async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理返回操作"""
    query = update.callback_query
    await query.answer()
    
    operation = context.user_data.get('operation')
    
    # 根据当前状态决定返回到哪一步
    # 如果是在 PASSWORD_INPUT 状态，返回到 EMAIL_INPUT
    # 如果是在 EMAIL_INPUT 或 DOMAIN_SELECT 状态，返回到 CHOOSING
    
    if operation == 'add_email_single' or operation == 'change_password':
        # 返回到邮箱输入界面
        if operation == 'add_email_single':
            text = '请输入完整邮箱地址（格式：username@domain）:'
        else:
            text = '请输入要修改密码的邮箱地址（格式：username@domain）:'
        reply_markup = create_cancel_back_keyboard(show_back=True)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return EMAIL_INPUT
    elif operation == 'add_email_random':
        # 返回到域名选择界面
        keyboard = [
            [InlineKeyboardButton("cloudvip8.com", callback_data='domain_cloudvip8.com')],
            [InlineKeyboardButton("🔙 返回", callback_data='back')],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('请选择域名:', reply_markup=reply_markup)
        return DOMAIN_SELECT
    else:
        # 默认返回到操作选择界面
        keyboard = [
            [InlineKeyboardButton("增加邮箱单个", callback_data='add_email_single')],
            [InlineKeyboardButton("增加邮箱随机5个", callback_data='add_email_random')],
            [InlineKeyboardButton("修改密码", callback_data='change_password')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('请选择操作:', reply_markup=reply_markup)
        return CHOOSING


# 取消对话
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理取消操作"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ 操作已取消。")
    elif update.message:
        await update.message.reply_text("❌ 操作已取消。")
    return ConversationHandler.END


# 信号处理函数
def signal_handler(signum, frame):
    """处理退出信号"""
    logger.info("收到退出信号，正在关闭机器人...")
    sys.exit(0)


# 主函数
def main():
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 从 config.py 读取 API_TOKEN
        application = ApplicationBuilder().token(API_TOKEN).build()

        # 创建对话处理器
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('mail', start)],
            states={
                CHOOSING: [
                    CallbackQueryHandler(operation_choice, pattern='^(add_email_single|add_email_random|change_password)$'),
                    CallbackQueryHandler(back_handler, pattern='^back$'),
                    CallbackQueryHandler(cancel_handler, pattern='^cancel$')
                ],
                DOMAIN_SELECT: [
                    CallbackQueryHandler(domain_selected, pattern='^domain_'),
                    CallbackQueryHandler(back_handler, pattern='^back$'),
                    CallbackQueryHandler(cancel_handler, pattern='^cancel$')
                ],
                EMAIL_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, received_email),
                    CallbackQueryHandler(back_handler, pattern='^back$'),
                    CallbackQueryHandler(cancel_handler, pattern='^cancel$')
                ],
                PASSWORD_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, received_password),
                    CallbackQueryHandler(back_handler, pattern='^back$'),
                    CallbackQueryHandler(cancel_handler, pattern='^cancel$')
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel_handler)]
        )

        # 注册对话处理器
        application.add_handler(conv_handler)
        
        # 添加错误处理
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            """处理错误"""
            logger.error(f"更新处理时发生错误: {context.error}")
            if isinstance(context.error, Exception):
                logger.exception(context.error)
        
        application.add_error_handler(error_handler)
        
        logger.info("邮件管理机器人已启动...")
        # 使用 drop_pending_updates=True 来清理旧的更新，避免冲突
        application.run_polling(drop_pending_updates=True)
    
    except KeyboardInterrupt:
        logger.info("收到键盘中断，正在关闭机器人...")
    except Exception as e:
        logger.error(f"启动机器人时发生错误: {e}")
        logger.exception(e)
        sys.exit(1)


if __name__ == '__main__':
    main()

