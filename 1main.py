# main.py
"""
الملف الرئيسي لتشغيل quotex_api.py و app.py معًا
"""
import subprocess
import threading
import time
import sys
import os

# =============================
# التأكد من وجود الملفات
# =============================
if not os.path.exists("quotex_api.py"):
    print("❌ خطأ: ملف quotex_api.py غير موجود في نفس المجلد!")
    sys.exit(1)

if not os.path.exists("app.py"):
    print("❌ خطأ: ملف app.py غير موجود في نفس المجلد!")
    sys.exit(1)

# =============================
# دالة تشغيل ملف بايثون
# =============================
def run_script(script_name: str):
    """شغّل ملف بايثون كعملية منفصلة"""
    try:
        process = subprocess.Popen(
            [sys.executable, script_name],
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=os.environ
        )
        return process
    except Exception as e:
        print(f"❌ خطأ في تشغيل {script_name}: {e}")
        sys.exit(1)

# =============================
# تشغيل الملفات
# =============================
def start_services():
    print("🚀 بدء تشغيل خدمة Quotex API...")
    process1 = run_script("quotex_api.py")  # يعمل في الخلفية

    print("🌐 بدء تشغيل واجهة الـ API (app.py)...")
    process2 = run_script("app.py")  # يفتح السيرفر

    try:
        # انتظر أن تنتهي العمليات (لن يحدث إلا إذا توقفت)
        process1.wait()
        process2.wait()
    except KeyboardInterrupt:
        print("\n🛑 إيقاف الخدمتين...")
        process1.terminate()
        process2.terminate()
        process1.wait()
        process2.wait()
        print("✅ تم إيقاف الخدمتين بنجاح.")

# =============================
# التشغيل التلقائي
# =============================
if __name__ == "__main__":
    print("🔄 جاري تشغيل النظام...")
    start_services()
