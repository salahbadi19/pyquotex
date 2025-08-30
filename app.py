import os
import sys
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pyquotex.stable_api import Quotex
from pyquotex.expiration import timestamp_to_date, get_timestamp_days_ago
from pyquotex.utils.processor import process_candles, get_color, aggregate_candle

# --- إعداد التسجيل ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pyquotex.log')
    ]
)
logger = logging.getLogger(__name__)

# --- بيانات الدخول (يمكنك تغييرها لاحقًا عبر متغيرات البيئة) ---
EMAIL = os.getenv("QUOTEX_EMAIL", "weboka1465@skateru.com")
PASSWORD = os.getenv("QUOTEX_PASSWORD", "weboka1465@")

# --- FastAPI ---
app = FastAPI(title="PyQuotex Full API", version="1.0.3", description="Complete API with all original features")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- العميل الرئيسي ---
class PyQuotexAPI:
    def __init__(self):
        self.client: Optional[Quotex] = None
        self.is_connected = False

    async def connect(self):
        if self.is_connected and self.client and await self.client.check_connect():
            return True

        # تنظيف الجلسة القديمة
        session_file = Path("session.json")
        if session_file.exists():
            session_file.unlink()

        self.client = Quotex(email=EMAIL, password=PASSWORD, lang="pt")
        self.client.user_agent = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"

        for attempt in range(5):
            try:
                logger.info(f"محاولة الاتصال بـ Quotex (المحاولة {attempt + 1})...")
                check, reason = await self.client.connect()
                if check:
                    logger.info(f"✅ الاتصال ناجح: {reason}")
                    self.is_connected = True
                    return True
            except Exception as e:
                logger.error(f"فشل في المحاولة {attempt + 1}: {e}")
            await asyncio.sleep(3)

        raise Exception("فشل الاتصال بعد 5 محاولات")

    async def ensure_connection(self):
        if not self.is_connected or not (self.client and await self.client.check_connect()):
            logger.info("إعادة الاتصال...")
            await self.connect()

    async def get_balance(self):
        await self.ensure_connection()
        await self.client.change_account("PRACTICE")
        balance = await self.client.get_balance()
        return {"balance": round(balance, 2)}

    async def get_profile(self):
        await self.ensure_connection()
        profile = await self.client.get_profile()
        return {
            "nick_name": profile.nick_name,
            "demo_balance": round(profile.demo_balance, 2),
            "live_balance": round(profile.live_balance, 2),
            "profile_id": profile.profile_id,
            "avatar": profile.avatar,
            "country": profile.country_name,
            "time_offset": profile.offset
        }

    async def get_assets(self):
        await self.ensure_connection()
        assets = self.client.get_all_asset_name()
        result = []
        for asset in assets[:50]:  # أول 50
            symbol = asset[0]
            name = asset[1]
            _, data = await self.client.check_asset_open(symbol)
            is_open = data[2] if data and len(data) > 2 else False
            result.append({"symbol": symbol, "name": name, "is_open": is_open})
        return {"assets": result}

    async def get_candles(self, asset: str = "EURUSD_otc", period: int = 60, count: int = 10):
        await self.ensure_connection()
        end_time = time.time()
        offset = period * count
        raw_candles = await self.client.get_candles(asset, end_time, offset, period)
        if not raw_candles:
            return {"candles": [], "message": "لا توجد شموع"}
        if not raw_candles[0].get("open"):
            processed = process_candles(raw_candles, period)
        else:
            processed = raw_candles
        return {"candles": processed[-count:]}

    async def get_payment_info(self):
        await self.ensure_connection()
        data = self.client.get_payment()
        return {"payment": dict(list(data.items())[:20])}

    async def get_signals(self):
        await self.ensure_connection()
        self.client.start_signals_data()
        await asyncio.sleep(2)
        signals = self.client.get_signal_data()
        return {"signals": signals or "لا توجد إشارات"}

    async def get_realtime_price(self, asset: str = "EURUSD_otc"):
        await self.ensure_connection()
        asset_name, asset_data = await self.client.get_available_asset(asset, force_open=True)
        if not asset_data or len(asset_data) < 3 or not asset_data[2]:
            raise Exception("العملة غير متاحة")
        await self.client.start_realtime_price(asset, 60)
        await asyncio.sleep(1)
        data = await self.client.get_realtime_price(asset_name)
        await self.client.stop_realtime_price(asset_name)
        return {"realtime": data[-1] if data else "لا توجد بيانات"}

    async def close(self):
        if self.client and self.is_connected:
            await self.client.close()
            self.is_connected = False
            logger.info("تم إغلاق الاتصال")

# --- إنشاء العميل ---
api = PyQuotexAPI()

# --- Endpoints ---
@app.on_event("startup")
async def startup():
    logger.info("🚀 بدء تشغيل PyQuotex API...")
    try:
        await api.connect()
    except Exception as e:
        logger.error(f"❌ فشل الاتصال عند البدء: {e}")

@app.get("/")
def root():
    return {
        "status": "running",
        "api": "PyQuotex Full API",
        "version": "1.0.3",
        "author": "Cleiton Leonel Creton",
        "endpoints": [
            "/balance",
            "/profile",
            "/assets",
            "/candles?asset=EURUSD_otc&period=60",
            "/payment-info",
            "/signals",
            "/realtime"
        ],
        "telegram": "https://t.me/pyquotex/852"
    }

@app.get("/balance")
async def balance():
    try:
        return await api.get_balance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile")
async def profile():
    try:
        return await api.get_profile()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/assets")
async def assets():
    try:
        return await api.get_assets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/candles")
async def candles(asset: str = "EURUSD_otc", period: int = 60, count: int = 10):
    try:
        return await api.get_candles(asset, period, count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/payment-info")
async def payment():
    try:
        return await api.get_payment_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/signals")
async def signals():
    try:
        return await api.get_signals()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/realtime")
async def realtime(asset: str = "EURUSD_otc"):
    try:
        return await api.get_realtime_price(asset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown():
    await api.close()
