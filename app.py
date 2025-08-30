import os
import asyncio
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from pyquotex.stable_api import Quotex
from pyquotex.config import credentials as orig_credentials

# --- استخدم بياناتك مباشرة بدل الطلب اليدوي ---
def credentials():
    return "weboka1465@skateru.com", "weboka1465@"

# --- التسجيل ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- تعديل مؤقت على المكتبة لمنع الخروج المفاجئ ---
import sys
from types import ModuleType

# نحتال قليلًا: نعطل sys.exit
class NoExit:
    def exit(self, code=0):
        logger.warning(f"تم منع الإغلاق: sys.exit({code})")
        raise RuntimeError("تم منع sys.exit")

sys.exit = NoExit().exit

# --- إدارة الدورة الحياتية ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 بدء التشغيل...")
    email, password = credentials()  # نفس الطريقة الأصلية
    app.state.client = Quotex(email=email, password=password, lang="pt")
    app.state.client.user_agent = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"

    try:
        check, reason = await app.state.client.connect()
        if check:
            logger.info(f"✅ تم الاتصال: {reason}")
        else:
            logger.error(f"❌ فشل الاتصال: {reason}")
    except SystemExit:
        logger.error("❌ تم منع الخروج بسبب فشل تسجيل الدخول")
    except Exception as e:
        logger.error(f"❌ خطأ في الاتصال: {e}")

    yield

    if hasattr(app.state, 'client') and app.state.client:
        await app.state.client.close()
        logger.info("👋 تم الإغلاق")

# --- التطبيق ---
app = FastAPI(lifespan=lifespan)

# --- Endpoints ---
@app.get("/")
def root():
    return {"status": "running", "api": "PyQuotex API", "version": "1.0", "author": "Cleiton"}

@app.get("/balance")
async def get_balance():
    try:
        await app.state.client.change_account("PRACTICE")
        balance = await app.state.client.get_balance()
        return {"balance": round(balance, 2)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/profile")
async def get_profile():
    try:
        profile = await app.state.client.get_profile()
        return {
            "nick_name": profile.nick_name,
            "demo_balance": round(profile.demo_balance, 2),
            "live_balance": round(profile.live_balance, 2),
            "country": profile.country_name
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/assets")
async def get_assets():
    try:
        assets = app.state.client.get_all_asset_name()
        result = []
        for asset in assets:
            symbol = asset[0]
            name = asset[1]
            _, data = await app.state.client.check_asset_open(symbol)
            is_open = data[2] if data and len(data) > 2 else False
            result.append({"symbol": symbol, "name": name, "is_open": is_open})
        return {"assets": result}
    except Exception as e:
        return {"error": str(e)}
