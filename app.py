import logging
import sys
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from pyquotex.stable_api import Quotex

# ---------- بيانات الحساب ----------
def credentials():
    return "weboka1465@skateru.com", "weboka1465@"

# ---------- إعداد اللوج ----------
logging.basicConfig(level=logging.DEBUG,  # خليه DEBUG بدل INFO
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PyQuotexAPI")

# منع الإغلاق المفاجئ
class NoExit:
    def exit(self, code=0):
        logger.warning(f"تم منع الإغلاق: sys.exit({code})")
        raise RuntimeError("تم منع sys.exit")
sys.exit = NoExit().exit

# ---------- دورة حياة التطبيق ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 بدء التشغيل...")
    email, password = credentials()
    logger.debug(f"📧 محاولة تسجيل الدخول بـ Email={email}, Password={len(password)*'*'}")

    app.state.client = Quotex(email=email, password=password, lang="pt")
    app.state.client.user_agent = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) "
        "Gecko/20100101 Firefox/119.0"
    )

    # جرب تعطيل SSL (ممكن Render يمنع بعض الشهادات)
    try:
        app.state.client.ssl = False
    except Exception:
        logger.warning("⚠️ تعذر تعطيل SSL، سيتم الاستمرار بالوضع العادي")

    try:
        logger.debug("🔌 محاولة الاتصال بالسيرفر...")
        check, reason = await app.state.client.connect()
        logger.debug(f"📡 نتيجة الاتصال: check={check}, reason={reason}")

        if check:
            logger.info(f"✅ تسجيل الدخول ناجح: {reason}")
            app.state.login_status = True
        else:
            logger.error(f"❌ فشل تسجيل الدخول: {reason}")
            app.state.login_status = False
    except Exception as e:
        logger.exception("❌ خطأ أثناء الاتصال")  # يعطي Trace كامل
        app.state.login_status = False

    yield

    if hasattr(app.state, 'client') and app.state.client:
        await app.state.client.close()
        logger.info("👋 تم تسجيل الخروج")

# ---------- تطبيق FastAPI ----------
app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"status": "running", "api": "PyQuotex API", "version": "1.0"}

@app.get("/login-status")
def login_status():
    """Endpoint يرجع إذا الدخول ناجح أو لا"""
    return {"logged_in": getattr(app.state, "login_status", False)}

@app.get("/balance")
async def get_balance():
    try:
        await app.state.client.change_account("PRACTICE")
        balance = await app.state.client.get_balance()
        return {"balance": round(balance, 2)}
    except Exception as e:
        logger.exception("❌ خطأ عند جلب الرصيد")
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
        logger.exception("❌ خطأ عند جلب البروفايل")
        return {"error": str(e)}
