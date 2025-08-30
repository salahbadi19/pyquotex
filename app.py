import logging
import sys
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from pyquotex.stable_api import Quotex

# ---------- بيانات الحساب (ضع بياناتك هنا) ----------
def credentials():
    return "weboka1465@skateru.com", "weboka1465@"

# ---------- إعداد اللوج ----------
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PyQuotexAPI")

# منع الإغلاق المفاجئ
class NoExit:
    def exit(self, code=0):
        logger.warning(f"تم منع الإغلاق: sys.exit({code})")
        raise RuntimeError("تم منع sys.exit")
sys.exit = NoExit().exit

# ---------- إعدادات البروكسي ----------
# إذا ما بدك بروكسي خليه None
# أمثلة:
# proxy = "http://user:pass@host:port"
# proxy = "socks5://user:pass@host:port"
proxy = None

# ---------- دورة حياة التطبيق ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 بدء التشغيل...")
    email, password = credentials()
    app.state.client = Quotex(email=email, password=password, lang="pt")

    # تعيين User-Agent يشبه متصفح حقيقي
    app.state.client.user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.6367.91 Safari/537.36"
    )

    # تعيين البروكسي إذا موجود
    if proxy:
        app.state.client.proxies = {"https": proxy, "http": proxy}
        logger.info(f"🌐 تم تفعيل البروكسي: {proxy}")

    try:
        logger.debug("📧 محاولة تسجيل الدخول...")
        check, reason = await app.state.client.connect()
        if check:
            logger.info(f"✅ تسجيل الدخول ناجح: {reason}")
            app.state.login_status = True
        else:
            logger.error(f"❌ فشل تسجيل الدخول: {reason}")
            app.state.login_status = False
    except Exception as e:
        logger.error(f"❌ خطأ أثناء الاتصال: {e}")
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
    return {"logged_in": getattr(app.state, "login_status", False)}

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
