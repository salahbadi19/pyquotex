from fastapi import FastAPI
import asyncio
import threading
import uvicorn

# =============================
# إنشاء تطبيق FastAPI
# =============================
app = FastAPI(
    title="Quotex Live Data",
    description="Realtime trading data API",
    version="1.0"
)

# =============================
# تخزين البيانات الحية
# =============================
latest_data = {
    "balance": None,
    "price": None,
    "candles": [],
    "signal": None,
    "timestamp": None,
    "connected": False,
    "asset": "EURUSD_otc"
}

# =============================
# دالة البث (يجب أن تكون معرفة مسبقًا)
# =============================
async def get_live_data_stream():
    # ⚠️ تأكد أن لديك:
    # - cli = PyQuotexCLI() تم تعريفه
    # - وظائف مثل cli.get_balance(), cli.get_realtime_price()
    
    global latest_data

    # استبدل هذا بربطك الفعلي بالكلاس
    from your_main_module import cli  # ← غير الاسم حسب ملفك

    await cli.test_connection()

    while True:
        try:
            # مثال: جلب الرصيد
            balance = await cli.get_balance()
            latest_data["balance"] = round(balance, 2)

            # مثال: جلب السعر
            price_data = await cli.get_realtime_price("EURUSD_otc")
            if price_data:
                latest_data["price"] = price_data.get("price")

            latest_data["timestamp"] = asyncio.get_event_loop().time()
            latest_data["connected"] = True

            await asyncio.sleep(1)  # تحديث كل ثانية

        except Exception as e:
            latest_data["error"] = str(e)
            latest_data["connected"] = False
            print(f"Error in stream: {e}")
            await asyncio.sleep(5)

# =============================
# تشغيل البث في خلفية
# =============================
def start_stream():
    asyncio.run(get_live_data_stream())

# تشغيل البث عند بدء التطبيق
threading.Thread(target=start_stream, daemon=True).start()

# =============================
# نقطة الوصول للبيانات
# =============================
@app.get("/data")
async def get_data():
    return {
        "success": True,
        "data": latest_data
    }

# نقطة وصول بسيطة للتحقق
@app.get("/")
async def home():
    return {
        "message": "Quotex API is running",
        "endpoint": "/data",
        "connected": latest_data["connected"]
    }

# =============================
# نقطة الدخول الرئيسية (لـ Render)
# =============================
if __name__ == "__main__":
    # هذا الجزء يعمل فقط عند التشغيل المحلي
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
