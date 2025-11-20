# -*- coding: utf-8 -*-
import telebot
from telebot import types
import config
import database as db
import signal
import utils
import logging
import time
import os
import subprocess
import threading
import shutil
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات
db.init_db()

# التأكد من أن المالك هو مسؤول في قاعدة البيانات
if db.get_user(config.ADMIN_ID) is None:
    db.add_user(config.ADMIN_ID, "Owner", "Owner")
    db.set_admin(config.ADMIN_ID, True)
elif not db.is_admin(config.ADMIN_ID):
    db.set_admin(config.ADMIN_ID, True)

# تهيئة البوت
bot = telebot.TeleBot(config.BOT_TOKEN)


# --- وظائف مساعدة ---

def get_user_status(user_id):
    if user_id == config.ADMIN_ID:
        return "👑 Owner"
    user_data = db.get_user(user_id)
    if user_data and user_data[4] == 1:
        return "🚫 Banned"
    if db.is_admin(user_id):
        return "✨ Admin"
    return "👤 User"

def get_user_info_text(user_id, username, first_name):
    db.add_user(user_id, username, first_name)
    status = get_user_status(user_id)
    files_count = len(db.get_user_files(user_id))
    text = (
        f"👋 Welcome, **{first_name}**!\n\n"
        f"🆔 Your User ID: `{user_id}`\n"
        f"✨ Your Status: {status}\n"
        f"📂 Files Uploaded: {files_count} / Unlimited\n\n"
        f"🤖 Host & run Python (`.py`) or JS (`.js`) scripts.\n"
        f"Upload single scripts or `.zip` archives.\n\n"
        f"⚡️ Use buttons or type commands."
    )
    return text

def send_main_menu(chat_id, user_id, username, first_name, message_id=None):
    text = get_user_info_text(user_id, username, first_name)
    markup = utils.generate_main_menu(user_id)

    photo_file_id = None
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos.photos:
            photo_file_id = photos.photos[0][-1].file_id
    except Exception as e:
        logger.warning(f"Could not get user profile photo for {user_id}: {e}")

    # إذا كان هناك message_id، نحاول تعديل الرسالة الحالية
    if message_id:
        try:
            # محاولة تعديل التعليق (إذا كانت الرسالة تحتوي على صورة)
            bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=markup, parse_mode="Markdown")
            return
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                return # لا يوجد تغيير، لا تفعل شيئًا
            
            # إذا فشل تعديل التعليق، نحاول تعديل النص
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode="Markdown")
                return
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" in str(e):
                    return # لا يوجد تغيير، لا تفعل شيئًا
                
                # إذا فشل تعديل النص (لأنها رسالة صورة لا يمكن تعديلها كنص)، نرسل رسالة جديدة
                logger.warning(f"Failed to edit message {message_id}. Sending new message instead. Error: {e}")
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception:
                    pass
    
    # إذا لم يكن هناك message_id، أو فشل التعديل، نرسل رسالة جديدة
    # يجب أن نعود هنا لكي يتم إرسال الرسالة الجديدة بالصورة إذا كان هناك photo_file_id
    # وإلا سيتم إرسال رسالة نصية بسيطة بدون صورة
    if message_id and (photo_file_id or bot.get_chat_member(chat_id, message_id).user.photo):
        # إذا كانت الرسالة الأصلية تحتوي على صورة، نرسل رسالة جديدة بالصورة
        pass # نتركها تمر إلى الجزء التالي
    else:
        # إذا لم يكن هناك message_id، أو كانت الرسالة الأصلية نصية، نرسل رسالة جديدة
        pass
    if photo_file_id:
        try:
            bot.send_photo(chat_id, photo_file_id, caption=text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error sending photo with caption: {e}. Falling back to text message.")
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")


# --- معالجات الأوامر والرسائل ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    db.add_user(user_id, username, first_name)

    if db.is_bot_locked() and not db.is_admin(user_id):
        bot.send_message(user_id, "🔒 The bot is currently locked for maintenance. Please try again later.")
        return

    if db.is_banned(user_id):
        bot.send_message(user_id, "🚫 You are banned from using this bot.")
        return

    send_main_menu(user_id, user_id, username, first_name)

@bot.message_handler(content_types=['document'])
def handle_document_upload(message):
    user_id = message.from_user.id
    if db.is_banned(user_id):
        bot.send_message(user_id, "🚫 You are banned from using this bot.")
        return

    if db.is_bot_locked() and not db.is_admin(user_id):
        bot.send_message(user_id, "🔒 The bot is currently locked for maintenance.")
        return

    file_name = message.document.file_name
    file_size = message.document.file_size

    if file_size > config.MAX_FILE_SIZE:
        bot.send_message(user_id, f"❌ File size exceeds the limit of {config.MAX_FILE_SIZE / (1024*1024):.0f}MB.")
        return

    file_ext = os.path.splitext(file_name)[1].lower()

    if file_ext not in config.ALLOWED_FILE_TYPES:
        bot.send_message(user_id, f"❌ Unsupported file type: `{file_ext}`. Only {', '.join(config.ALLOWED_FILE_TYPES)} are allowed.")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        user_dir = utils.get_user_dir(user_id)
        save_path = os.path.join(user_dir, file_name)

        with open(save_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        final_path = save_path
        file_type = file_ext.strip('.')

        if file_ext == '.zip':
            folder_name = os.path.splitext(file_name)[0]
            extract_to_dir = os.path.join(user_dir, folder_name)
            if utils.handle_zip_file(save_path, extract_to_dir):
                final_path = extract_to_dir
                file_type = 'zip_folder'
                # لا نرسل رسالة هنا، بل نتركها للأسفل مع الأزرار
                # bot.send_message(user_id, f"✅ Zip file `{file_name}` extracted successfully to folder `{folder_name}`.")
            else:
                bot.send_message(user_id, "❌ Failed to process the zip file. It might be corrupted or in an unsupported format.")
                if os.path.exists(save_path): os.remove(save_path)
                return

        file_id = db.add_file(user_id, file_name, final_path, file_type)
        
        # إظهار رسالة النجاح مع أزرار التحكم بالملف لجميع الأنواع
        if file_ext == '.zip':
            text = f"✅ Zip file `{file_name}` extracted successfully to folder `{folder_name}`."
        else:
            text = f"✅ File `{file_name}` uploaded and ready to run."
            
        markup = utils.generate_file_management_buttons(file_id, 'stopped')
        # إضافة زر العودة إلى قائمة الملف        markup.add(types.InlineKeyboardButton("⬅️ Back to Files", callback_data="check_files"))
        bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error handling file upload for user {user_id}: {e}")
        bot.send_message(user_id, "❌ An error occurred during file upload or processing.")

def show_user_files(chat_id, user_id, message_id):
    files = db.get_user_files(user_id)
    if not files:
        text = "📂 You have not uploaded any files yet."
        markup = utils.generate_back_button("main_menu")
    else:
        text = "📂 **Your Uploaded Files**\n\n"
        markup = types.InlineKeyboardMarkup()
        for file_id, file_name, file_type, status, process_id in files:
            status_emoji = "▶️" if status == 'running' else "⏹"
            text += f"{status_emoji} `{file_name}` ({file_type.upper()})\n"
            # إضافة سطر فارغ للفصل بين الملفات
            text += "\n" 
            file_markup = utils.generate_file_management_buttons(file_id, status)
            # إضافة أزرار التحكم لكل ملف في صف منفصل
            markup.add(*file_markup.keyboard[0])
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="main_menu"))

    # محاولة تعديل الرسالة الحالية
    if message_id:
        try:
            # محاولة تعديل التعليق إذا كانت الرسالة تحتوي على صورة/ملف
            bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=markup, parse_mode="Markdown")
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                # الرسالة لم تتغير، لا بأس
                pass
            elif "message can't be edited" in str(e) or "message to edit not found" in str(e):
                # الرسالة لا يمكن تعديلها (ربما رسالة نصية قديمة)
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode="Markdown")
                except telebot.apihelper.ApiTelegramException as e:
                    if "message is not modified" in str(e):
                        pass
                    elif "message can't be edited" in str(e) or "message to edit not found" in str(e):
                        # إذا فشل التعديل، أرسل رسالة جديدة
                        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
                    else:
                        raise e
            else:
                raise e
    else:
        # إذا لم يكن هناك message_id، أرسل رسالة جديدة
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def get_log_file_path(file_path):
    return file_path + ".log"

def run_script(file_id):
    file_data = db.get_file_details(file_id)
    if not file_data:
        return False, "File not found."

    file_path = file_data[3]
    file_type = file_data[4]

    if file_type == 'py':
        command = [config.PYTHON_COMMAND, file_path]
    elif file_type == 'js':
        command = [config.NODE_COMMAND, file_path]
    elif file_type == 'zip_folder':
        main_file = None
        for root, _, files in os.walk(file_path):
            for f in files:
                if f == 'main.py':
                    main_file = os.path.join(root, f)
                    command = [config.PYTHON_COMMAND, main_file]
                    break
                elif f == 'index.js':
                    main_file = os.path.join(root, f)
                    command = [config.NODE_COMMAND, main_file]
                    break
            if main_file:
                break
        if not main_file:
            return False, "No main file (main.py or index.js) found in the zip folder."
    else:
        return False, f"Unsupported file type for running: {file_type}"

    try:
        log_path = get_log_file_path(file_path)
        
        # التأكد من أن المسار الحالي (cwd) هو مجلد الملف
        script_dir = os.path.dirname(file_path) if file_type != 'zip_folder' else file_path
        
        # التأكد من وجود المجلد
        if not os.path.exists(script_dir):
             return False, f"Script directory not found: {script_dir}"
             
        # التأكد من أن الملف الرئيسي موجود وقابل للتنفيذ
        if not os.path.exists(command[-1]):
             return False, f"Main script file not found: {command[-1]}"

        with open(log_path, 'w') as log_file:
            # استخدام preexec_fn=os.setsid لضمان أن العملية تعمل في مجموعة عمليات منفصلة
            # مما يسمح بإيقافها بشكل صحيح لاحقًا باستخدام os.killpg
            process = subprocess.Popen(command, cwd=script_dir, preexec_fn=os.setsid, stdout=log_file, stderr=subprocess.STDOUT)
            
        # الانتظار قليلاً للتأكد من بدء العملية
        time.sleep(0.5) 
        
        db.update_file_status(file_id, 'running', process.pid)
        return True, f"Script `{file_data[2]}` started successfully (PID: {process.pid})."
    except Exception as e:
        logger.error(f"Error running script {file_id}: {e}")
        db.update_file_status(file_id, 'error')
        return False, f"An error occurred while starting the script: {e}"

def stop_script(file_id):
    file_data = db.get_file_details(file_id)
    if not file_data or file_data[6] is None:
        return False, "Script is not running or PID not found."

    pid = file_data[6]
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        db.update_file_status(file_id, 'stopped', None)
        return True, f"Script `{file_data[2]}` stopped successfully."
    except ProcessLookupError:
        db.update_file_status(file_id, 'stopped', None)
        return True, "Script was not running, status updated."
    except Exception as e:
        logger.error(f"Error stopping script {file_id} with PID {pid}: {e}")
        return False, f"An error occurred while stopping the script: {e}"


# --- معالج الاستدعاءات المضمنة (Callback Queries) ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    user_id = call.from_user.id
    username = call.from_user.username
    first_name = call.from_user.first_name
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    if db.is_bot_locked() and not db.is_admin(user_id):
        bot.answer_callback_query(call.id, "🔒 Bot is locked for maintenance.")
        return

    if db.is_banned(user_id):
        bot.answer_callback_query(call.id, "🚫 You are banned from using this bot.")
        return

    try:
        if data == "main_menu":
            send_main_menu(chat_id, user_id, username, first_name, message_id)

        elif data == "upload_file":
            text = "⬆️ Please send your Python (`.py`), JavaScript (`.js`), or Zip (`.zip`) file now."
            # نستخدم تعديل الرسالة لزر Back
            try:
                # محاولة تعديل التعليق (إذا كانت الرسالة صورة)
                bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")
            except telebot.apihelper.ApiTelegramException as e:
                # إذا فشل تعديل التعليق، نحاول تعديل النص
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")
                except telebot.apihelper.ApiTelegramException as e:
                    # إذا فشل التعديل، نرسل رسالة جديدة
                    if "message is not modified" in str(e):
                        pass
                    else:
                        bot.send_message(chat_id, text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")

        elif data == "check_files":
            # نستخدم تعديل الرسالة لعرض الملفات
            show_user_files(chat_id, user_id, message_id)

        elif data == "bot_speed":
            start_time = time.time()
            end_time = time.time()
            speed = round((end_time - start_time) * 1000, 2)
            text = f"⚡️ Bot Speed: `{speed} ms`"
            # نستخدم تعديل الرسالة لسرعة البوت
            try:
                # محاولة تعديل التعليق (إذا كانت الرسالة صورة)
                bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")
            except telebot.apihelper.ApiTelegramException as e:
                # إذا فشل تعديل التعليق، نحاول تعديل النص
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")
                except telebot.apihelper.ApiTelegramException as e:
                    # إذا فشل التعديل، نرسل رسالة جديدة
                    if "message is not modified" in str(e):
                        pass
                    else:
                        bot.send_message(chat_id, text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")

        elif data == "help":
            help_text = (
                "❓ **Help & Instructions**\n\n"
                "1. **Upload File:** Send your `.py`, `.js`, or `.zip` file directly to the bot.\n"
                "2. **Check Files:** View your uploaded scripts, check their status (Running/Stopped), and manage them (Run, Stop, Delete).\n"
                "3. **Bot Speed:** Measures the bot's response time.\n"
                "4. **Admin Panel:** Special features for the bot owner/admins.\n\n"
                "The bot runs your scripts in an isolated environment."
            )
            # نستخدم تعديل الرسالة للمساعدة
            try:
                # محاولة تعديل التعليق (إذا كانت الرسالة صورة)
                bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=help_text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")
            except telebot.apihelper.ApiTelegramException as e:
                # إذا فشل تعديل التعليق، نحاول تعديل النص
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=help_text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")
                except telebot.apihelper.ApiTelegramException as e:
                    # إذا فشل التعديل، نرسل رسالة جديدة
                    if "message is not modified" in str(e):
                        pass
                    else:
                        bot.send_message(chat_id, help_text, reply_markup=utils.generate_back_button("main_menu"), parse_mode="Markdown")

        elif data.startswith("file_run_"):
            handle_file_action(call, "run")

        elif data.startswith("file_stop_"):
            handle_file_action(call, "stop")

        elif data.startswith("file_delete_"):
            handle_file_action(call, "delete")

        elif data.startswith("log_"):
            handle_file_action(call, "log")

        elif data.startswith("admin_"):
            handle_admin_callback(call)

        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Error in callback query handler: {e}")
        bot.answer_callback_query(call.id, "An error occurred.")


def handle_file_action(call, action):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    file_id = int(call.data.split('_')[-1])
    file_data = db.get_file_details(file_id)

    if not file_data or (file_data[1] != user_id and not db.is_admin(user_id)):
        bot.answer_callback_query(call.id, "🚫 File not found or access denied.")
        return

    if action == "run":
        success, message = run_script(file_id)
        bot.answer_callback_query(call.id, message)
    elif action == "stop":
        success, message = stop_script(file_id)
        bot.answer_callback_query(call.id, message)
    elif action == "delete":
        stop_script(file_id) # Ensure the script is stopped before deleting
        try:
            os.remove(file_data[3])
            if file_data[4] == 'zip_folder':
                shutil.rmtree(file_data[3])
        except OSError as e:
            logger.error(f"Error deleting file from filesystem: {e}")
        db.delete_file_from_db(file_id)
        bot.answer_callback_query(call.id, f"File `{file_data[2]}` deleted.")
    elif action == "log":
        log_path = get_log_file_path(file_data[3])
        if not os.path.exists(log_path):
            log_content = "Log file not found. Run the script first."
        else:
            with open(log_path, 'r') as f:
                log_content = f.read()
        log_text = f"📜 **Log for `{file_data[2]}`**\n\n"
        log_text += "```\n" + (log_content[:3500] + "...\n(Truncated)" if len(log_content) > 3500 else log_content) + "\n```"
        
        # نستخدم edit_message_text هنا لأن رسالة الملفات هي رسالة نصية
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=log_text, reply_markup=utils.generate_back_button("check_files"), parse_mode="Markdown")
        return # لا نريد تحديث قائمة الملفات بعد عرض السجل

    # تحديث قائمة الملفات بعد كل إجراء (تشغيل، إيقاف، حذف)
    show_user_files(chat_id, user_id, message_id)


def handle_admin_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    if not db.is_admin(user_id):
        bot.answer_callback_query(call.id, "🚫 Access Denied.")
        return

    if data == "admin_panel":
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="👑 **Admin Panel**\n\nChoose an action:", reply_markup=utils.generate_admin_panel_menu(), parse_mode="Markdown")

    elif data == "admin_stats":
        stats = db.get_statistics()
        stats_text = (
            "📊 **Bot Statistics**\n\n"
            f"👥 Total Users: `{stats['total_users']}`\n"
            f"🗂️ Total Files: `{stats['total_files']}`\n"
            f"▶️ Running Scripts: `{stats['running_files']}`\n"
            f"🚫 Banned Users: `{stats['banned_users']}`"
        )
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=stats_text, reply_markup=utils.generate_back_button("admin_panel"), parse_mode="Markdown")

    elif data == "admin_broadcast_all":
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📢 **Broadcast to All Users**\n\nPlease send the message you want to broadcast now.", reply_markup=utils.generate_back_button("admin_panel"))
        bot.register_next_step_handler(call.message, send_broadcast_message)

    elif data == "admin_lock_bot":
        db.set_setting('bot_locked', '1')
        bot.answer_callback_query(call.id, "🔒 Bot has been locked.")
        send_main_menu(chat_id, user_id, call.from_user.username, call.from_user.first_name, message_id)

    elif data == "admin_unlock_bot":
        db.set_setting('bot_locked', '0')
        bot.answer_callback_query(call.id, "🔓 Bot has been unlocked.")
        send_main_menu(chat_id, user_id, call.from_user.username, call.from_user.first_name, message_id)

    elif data == "admin_run_all":
        all_files = db.get_all_files()
        count = 0
        for file_data in all_files:
            if file_data[5] == 'stopped':
                success, message = run_script(file_data[0])
                if success:
                    count += 1
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"▶️ **Run All Scripts**\n\nSuccessfully started `{count}` stopped scripts.", reply_markup=utils.generate_back_button("admin_panel"))

# --- وظائف المشرفين الإضافية (Next Step Handlers) ---

def send_broadcast_message(message):
    user_id = message.from_user.id
    if not db.is_admin(user_id): return

    all_users = db.get_all_users()
    success_count = 0
    fail_count = 0
    for user in all_users:
        try:
            bot.send_message(user[0], message.text, parse_mode="Markdown")
            success_count += 1
        except Exception:
            fail_count += 1

    bot.send_message(user_id, f"📢 Broadcast finished.\n\n✅ Sent to: {success_count}\n❌ Failed to send: {fail_count}")
    send_main_menu(user_id, user_id, message.from_user.username, message.from_user.first_name)


if __name__ == '__main__':
    logger.info("Bot is starting...")
    try:
        # إيقاف جميع العمليات القديمة عند بدء التشغيل
        for file_id, user_id, file_path, process_id in db.get_all_running_files():
            logger.info(f"Stopping old process {process_id} for file {file_id}")
            stop_script(file_id)
        bot.polling(none_stop=True)
    except Exception as e:
        logger.critical(f"Bot polling failed: {e}")

