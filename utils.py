import os
import shutil
import zipfile
import logging
from telebot import types
import database as db
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_user_dir(user_id):
    user_dir = os.path.join(config.USER_FILES_DIR, str(user_id))
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

def generate_main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الصف الأول: قناة التحديثات (زر واحد)
    btn_updates = types.InlineKeyboardButton("📣 Updates Channel", url=config.UPDATES_CHANNEL_URL)
    markup.add(btn_updates)

    # الصف الثاني: رفع الملفات والتحقق منها
    btn_upload = types.InlineKeyboardButton("⬆️ Upload File", callback_data="upload_file")
    btn_check_files = types.InlineKeyboardButton("📂 Check Files", callback_data="check_files")
    markup.add(btn_upload, btn_check_files)

    # الصف الثالث: سرعة البوت والمساعدة
    btn_bot_speed = types.InlineKeyboardButton("⚡️ Bot Speed", callback_data="bot_speed")
    btn_help = types.InlineKeyboardButton("❓ Help", callback_data="help")
    markup.add(btn_bot_speed, btn_help)

    # الصف الرابع: الإحصائيات والإذاعة (تظهر للجميع لكن وظائفها للمشرف فقط)
    btn_stats = types.InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")
    btn_broadcast = types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast_all") # تم تصحيح callback_data
    markup.add(btn_stats, btn_broadcast)

    # الصف الخامس: قفل/فتح البوت وتشغيل السكربتات (تظهر للجميع لكن وظائفها للمشرف فقط)
    lock_status = "🔓 Unlock Bot" if db.is_bot_locked() else "🔒 Lock Bot"
    lock_callback = "admin_unlock_bot" if db.is_bot_locked() else "admin_lock_bot"
    
    btn_lock_bot = types.InlineKeyboardButton(lock_status, callback_data=lock_callback)
    btn_run_all = types.InlineKeyboardButton("🟢 Run All Scripts", callback_data="admin_run_all") # تم تغيير الأيقونة
    markup.add(btn_lock_bot, btn_run_all)

    # الصف الأخير: لوحة المشرف (تظهر للمشرف فقط)
    if db.is_admin(user_id):
        btn_admin_panel = types.InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")
        markup.add(btn_admin_panel)

    return markup

def generate_admin_panel_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_stats = types.InlineKeyboardButton("📊 Show Statistics", callback_data="admin_stats")
    btn_broadcast_all = types.InlineKeyboardButton("📢 Broadcast All", callback_data="admin_broadcast_all")
    btn_broadcast_user = types.InlineKeyboardButton("👤 Broadcast to User", callback_data="admin_broadcast_user")
    btn_manage_users = types.InlineKeyboardButton("👥 Manage Users (Ban/Unban)", callback_data="admin_manage_users_list")
    btn_manage_files = types.InlineKeyboardButton("🗂️ Manage All Files", callback_data="admin_manage_all_files")
    btn_get_files = types.InlineKeyboardButton("📥 Get All Files", callback_data="admin_get_all_files")
    btn_back = types.InlineKeyboardButton("⬅️ Back to Main", callback_data="main_menu")

    markup.add(btn_stats, btn_manage_users)
    markup.add(btn_broadcast_all, btn_broadcast_user)
    markup.add(btn_manage_files, btn_get_files)
    markup.add(btn_back)
    return markup

def generate_back_button(callback_data="main_menu", text="⬅️ Back"):
    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Back", callback_data=callback_data)
    markup.add(btn_back)
    return markup

def generate_file_management_buttons(file_id, status):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    if status == 'running':
        btn_action = types.InlineKeyboardButton("⏹ Stop", callback_data=f"file_stop_{file_id}")
    else:
        btn_action = types.InlineKeyboardButton("▶️ Run", callback_data=f"file_run_{file_id}")
        
    btn_log = types.InlineKeyboardButton("📜 Log", callback_data=f"log_{file_id}")
    btn_delete = types.InlineKeyboardButton("🗑️ Delete", callback_data=f"file_delete_{file_id}")
    
    markup.add(btn_action, btn_log, btn_delete)
    return markup

def handle_zip_file(file_path, extract_to_dir):
    try:
        # التأكد من أن المجلد المستهدف موجود
        if not os.path.exists(extract_to_dir):
            os.makedirs(extract_to_dir)
            
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            # التحقق من عدم وجود مسارات خبيثة (Zip Slip)
            for member in zip_ref.namelist():
                member_path = os.path.join(extract_to_dir, member)
                if not member_path.startswith(extract_to_dir):
                    raise Exception("Zip Slip detected!")
            
            zip_ref.extractall(extract_to_dir)
            
        os.remove(file_path) 
        logger.info(f"Extracted and removed zip file: {file_path} to {extract_to_dir}")
        return True
    except zipfile.BadZipFile:
        logger.error(f"Bad zip file: {file_path}")
        return False
    except Exception as e:
        logger.error(f"Error handling zip file {file_path}: {e}")
        return False

def delete_user_file_system(file_path):
    try:
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
        logger.info(f"Deleted file/folder from filesystem: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error deleting file {file_path}: {e}")
        return False

def delete_file_full(file_id):
    file_data = db.get_file_details(file_id)
    if not file_data:
        return False
    
    file_path = file_data[3]
    
    # 1. إيقاف العملية (سيتم تنفيذها في main.py)
    # 2. حذف من نظام الملفات
    delete_user_file_system(file_path)
    
    # 3. حذف من قاعدة البيانات
    db.delete_file_from_db(file_id)
    
    return True

