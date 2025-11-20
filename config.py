import os

# --- إعدادات البوت الأساسية ---

# يجب استبدال هذا التوكن بتوكن البوت الخاص بك
BOT_TOKEN = "8557086177:AAE90O1ai95ba4l6YRdrNaumXH9us-i88S8"

# يجب استبدال هذا بمعرف المستخدم الخاص بك (المالك/الأدمن)
ADMIN_ID = 6664075645 # تم التحديث بناءً على طلب المستخدم

# رابط قناة التحديثات
UPDATES_CHANNEL_URL = "https://t.me/nSEIF"

# --- إعدادات نظام الملفات والاستضافة ---

# المسار الأساسي لتخزين ملفات المستخدمين
USER_FILES_DIR = os.path.join(os.getcwd(), "user_files")

# أنواع الملفات المسموح بها
ALLOWED_FILE_TYPES = [".py", ".js", ".zip"]

# الحد الأقصى لحجم الملف (بالبايت) - يمكن تعديله
MAX_FILE_SIZE = 50 * 1024 * 1024 # 50 ميجابايت

# --- إعدادات التشغيل ---

# الأمر المستخدم لتشغيل ملفات بايثون
PYTHON_COMMAND = "python3"

# الأمر المستخدم لتشغيل ملفات جافاسكريبت (باستخدام Node.js)
NODE_COMMAND = "node"

# التأكد من إنشاء مجلد الملفات إذا لم يكن موجودًا
if not os.path.exists(USER_FILES_DIR):
    os.makedirs(USER_FILES_DIR)

