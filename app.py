# =============================
# PyQuotex - Clean & API-Ready Version
# =============================

import os
import sys
import json
import time
import random
import asyncio
import logging
import argparse
import pyfiglet
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, Callable
from functools import wraps
import locale

from pyquotex.expiration import (
    timestamp_to_date,
    get_timestamp_days_ago
)
from pyquotex.utils.processor import (
    process_candles,
    get_color,
    aggregate_candle
)
from pyquotex.stable_api import Quotex

__author__ = "Cleiton Leonel Creton"
__version__ = "1.0.3"

USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"

# --- إعداد التسجيل بدون إخراج غير ضروري ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pyquotex.log')
    ]
)
logger = logging.getLogger(__name__)

# --- إزالة الإعلانات تمامًا ---
# تم حذف LANGUAGE_MESSAGES و detect_user_language و display_banner

# --- بيانات الدخول التلقائية ---
def credentials() -> Tuple[str, str]:
    return "gecoge9069@mvpmedix.com", "gecoge9069@"

# --- تعديل decorator ليبقى متصلاً دائمًا ---
def ensure_connection(max_attempts: int = 5):
    """Decorator to ensure connection before executing function, but do NOT close after."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not self.client:
                logger.error("Quotex API client not initialized.")
                raise RuntimeError("Quotex API client not initialized.")

            if not await self.client.check_connect():
                logger.info("Establishing connection...")
                check, reason = await self._connect_with_retry(max_attempts)
                if not check:
                    logger.error(f"Failed to connect: {reason}")
                    raise ConnectionError(f"Failed to connect: {reason}")

            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


class PyQuotexCLI:
    """PyQuotex CLI application for trading operations."""

    def __init__(self):
        self.client: Optional[Quotex] = None
        self.setup_client()

    def setup_client(self):
        """Initializes the Quotex API client with credentials."""
        try:
            email, password = credentials()
            self.client = Quotex(
                email=email,
                password=password,
                lang="pt"
            )
            logger.info("Quotex client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Quotex client: {e}")
            raise

    async def _connect_with_retry(self, attempts: int = 5) -> Tuple[bool, str]:
        """Internal method to attempt connection with retry logic."""
        logger.info("Attempting to connect to Quotex API...")
        check, reason = await self.client.connect()

        if not check:
            for attempt_num in range(1, attempts + 1):
                logger.warning(f"Connection failed. Attempt {attempt_num} of {attempts}.")

                session_file = Path("session.json")
                if session_file.exists():
                    session_file.unlink()
                    logger.debug("Obsolete session file removed.")

                await asyncio.sleep(2)
                check, reason = await self.client.connect()

                if check:
                    logger.info("Reconnected successfully!")
                    break

            if not check:
                logger.error(f"Failed to connect after {attempts} attempts: {reason}")
                return False, reason

        logger.info(f"Connected successfully: {reason}")
        return check, reason

    # --- تم إزالة display_banner تمامًا ---

    @ensure_connection()
    async def test_connection(self) -> None:
        is_connected = await self.client.check_connect()
        if is_connected:
            print("✅ Connection successful!")
        else:
            print("❌ Connection failed!")

    @ensure_connection()
    async def get_balance(self) -> Dict[str, float]:
        await self.client.change_account("PRACTICE")
        balance = await self.client.get_balance()
        result = {"balance": round(balance, 2), "currency": "BRL", "type": "balance"}
        print(json.dumps(result))
        return result

    @ensure_connection()
    async def get_profile(self) -> Dict[str, Any]:
        profile = await self.client.get_profile()
        data = {
            "type": "profile",
            "nick_name": profile.nick_name,
            "demo_balance": round(profile.demo_balance, 2),
            "live_balance": round(profile.live_balance, 2),
            "profile_id": profile.profile_id,
            "avatar": profile.avatar,
            "country": profile.country_name,
            "time_offset": profile.offset
        }
        print(json.dumps(data))
        return data

    @ensure_connection()
    async def get_candles(self, asset: str = "EURUSD_otc", period: int = 60, count: int = 10) -> List[Dict]:
        end_from_time = time.time()
        offset = count * period
        candles = await self.client.get_candles(asset, end_from_time, offset, period)

        if not candles or len(candles) == 0:
            return []

        if not candles[0].get("open"):
            candles = process_candles(candles, period)

        recent_candles = candles[-count:]
        result = []
        for candle in recent_candles:
            result.append({
                "type": "candle",
                "asset": asset,
                "time": candle.get("time"),
                "open": round(candle.get("open"), 5),
                "close": round(candle.get("close"), 5),
                "high": round(candle.get("max"), 5),
                "low": round(candle.get("min"), 5),
                "color": "green" if candle.get("open") < candle.get("close") else "red"
            })
        print(json.dumps(result))
        return result

    @ensure_connection()
    async def get_realtime_price(self, asset: str = "EURUSD_otc") -> Dict[str, Any]:
        asset_name, asset_data = await self.client.get_available_asset(asset, force_open=True)
        if not asset_data or not asset_data[2]:
            return {"error": "Asset closed", "status": "failed"}

        await self.client.start_realtime_price(asset, 60)
        await asyncio.sleep(1)

        data = await self.client.get_realtime_price(asset_name)
        await self.client.stop_realtime_price(asset_name)

        if data:
            latest = data[-1]
            result = {
                "type": "price",
                "asset": asset,
                "price": round(latest["price"], 5),
                "timestamp": latest["time"],
                "status": "success"
            }
            print(json.dumps(result))
            return result
        else:
            result = {"type": "price", "error": "No data", "status": "failed"}
            print(json.dumps(result))
            return result

    @ensure_connection()
    async def get_signal_data(self) -> None:
        self.client.start_signals_data()
        try:
            while True:
                signals = self.client.get_signal_data()
                if signals:
                    result = {
                        "type": "signal",
                        "data": signals,
                        "timestamp": int(time.time())
                    }
                    print(json.dumps(result))
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

    # --- يمكنك إضافة باقي الوظائف بنفس الطريقة ---

# =============================
# دالة جلب البيانات الحية (جاهزة للـ API)
# =============================

async def get_live_data_stream():
    cli = PyQuotexCLI()
    await cli.test_connection()
    while True:
        try:
            await cli.get_balance()
            await cli.get_realtime_price("EURUSD_otc")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in stream: {e}")
            await asyncio.sleep(5)

# =============================
# التشغيل من الترمنال
# =============================

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="stream", help="Command to run")
    args = parser.parse_args()

    if args.command == "stream":
        await get_live_data_stream()
    elif args.command == "balance":
        cli = PyQuotexCLI()
        await cli.get_balance()
    elif args.command == "candles":
        cli = PyQuotexCLI()
        await cli.get_candles("EURUSD_otc", 60, 5)
    else:
        print("Commands: stream, balance, candles")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Stream stopped.")
