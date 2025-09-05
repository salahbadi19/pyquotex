# pyquotex_pro_gui.py
# PyQuotex Live Chart Pro - بدون أخطاء | session.json | تحسينات كاملة
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
import threading
import time
import json
import os
from datetime import datetime
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# --- تثبيت المكتبة ---
# pip install git+https://github.com/cleitonleonel/PyQuotex.git 
try:
    from pyquotex.stable_api import Quotex
    from pyquotex.utils.processor import process_candles
except ImportError:
    messagebox.showerror("Error", "Install PyQuotex:\npip install git+https://github.com/cleitonleonel/PyQuotex.git ")
    exit()

# =================== GLOBAL COLORS ===================
NEON_GREEN = "#39FF14"
NEON_PINK = "#FF1493"
NEON_BLUE = "#00BFFF"
NEON_YELLOW = "#FFFF00"
DARK_BG = "#0a0a0a"
PANEL_BG = "#111"
CANVAS_BG = "#222"
ACTIVE_BTN = "#006699"
TEXT_WHITE = "white"

# =================== CONFIGURATION ===================
DATA_FILE = "pyquotex_data.json"
BOTS_DIR = "bots"
SESSION_FILE = "session.json"
os.makedirs(BOTS_DIR, exist_ok=True)
CANDLE_COUNT = 60
MAX_SIGNALS = 50
DEFAULT_TF = "1M"
TIMEFRAMES = ["5S", "10S", "15S", "30S", "1M", "2M", "3M", "5M", "10M", "15M", "30M", "1H"]
TIMEFRAME_MAP = {
    "5S": 5, "10S": 10, "15S": 15, "30S": 30,
    "1M": 60, "2M": 120, "3M": 180, "5M": 300,
    "10M": 600, "15M": 900, "30M": 1800, "1H": 3600
}
USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"

# 🔐 بيانات الدخول التلقائي
EMAIL = "gecoge9069@mvpmedix.com"
PASSWORD = "gecoge9069@"

# =================== إدارة البوتات ===================
class BotManager:
    def __init__(self):
        self.bots = {}

    def add_bot(self, name, code):
        self.bots[name] = code

    def get_bots(self):
        return list(self.bots.keys())

    def get_code(self, name):
        return self.bots.get(name, "")

    def run_bot(self, name, symbol, current_price):
        code = self.bots.get(name)
        if not code:
            return None

        # ✅ Sandbox مبسط
        safe_globals = {
            "__builtins__": {
                "True": True, "False": False, "None": None,
                "print": print
            }
        }
        safe_locals = {
            "symbol": symbol,
            "current_price": current_price,
            "signal": None,
            "buy": lambda: "call",
            "sell": lambda: "put",
            "price": current_price
        }

        try:
            exec(code, safe_globals, safe_locals)
            sig = safe_locals.get("signal")
            if sig in ["call", "put"]:
                return {
                    "bot": name,
                    "signal": sig.upper(),
                    "price": safe_locals.get("price", current_price),
                    "time": datetime.now().strftime("%H:%M:%S")
                }
        except Exception as e:
            print(f"Bot {name} error: {e}")

        return None

# =================== التطبيق الرئيسي ===================
class PyQuotexProGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ PyQuotex Live Pro")
        self.root.geometry("1600x950")
        self.root.configure(bg=DARK_BG)
        self.bot_manager = BotManager()
        self.signals = []
        self.candles = []
        self.current_price = 0.0
        self.symbol = None
        self.tf_name = DEFAULT_TF
        self.tf_seconds = TIMEFRAME_MAP[self.tf_name]
        self.is_connected = False
        self.show_bots_panel = False
        self.asset_buttons = {}
        self.client = None
        self.loop = asyncio.new_event_loop()

        # بدء الاتصال في thread منفصل
        threading.Thread(target=self._run_async, daemon=True).start()
        self._build_loading_screen()

    def _run_async(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect_and_init())

    def _build_loading_screen(self):
        self.loading_frame = tk.Frame(self.root, bg=DARK_BG)
        self.loading_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.loading_text = tk.StringVar(value="Connecting")
        label = tk.Label(self.loading_frame, textvariable=self.loading_text, font=("Consolas", 20), bg=DARK_BG, fg=NEON_GREEN)
        label.pack()
        self.dot_count = 0
        self._animate_dots()

    def _animate_dots(self):
        if not self.is_connected:
            self.dot_count = (self.dot_count + 1) % 4
            self.loading_text.set("Connecting" + "." * self.dot_count)
            self.root.after(500, self._animate_dots)

    async def _connect_and_init(self):
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, "r") as f:
                    session_data = json.load(f)
                self.client = Quotex(email=EMAIL, password=PASSWORD, user_agent=USER_AGENT)
                self.client.session_data = session_data
                check, reason = await self.client.connect()
                if not check:
                    raise Exception(f"Session failed: {reason}")
            else:
                self.client = Quotex(email=EMAIL, password=PASSWORD, user_agent=USER_AGENT)
                check, reason = await self.client.connect()
                if not check:
                    error_msg = f"Login failed: {reason}"
                    self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", msg))
                    return
                with open(SESSION_FILE, "w") as f:
                    json.dump(self.client.session_data, f)

            self.is_connected = True
            await self.client.change_account("PRACTICE")

            # --- التعديل الأساسي: معالجة آمنة لجلب الأصول ---
            all_assets = self.client.get_all_asset_name()
            self.symbols = []

            # التحقق من أن all_assets ليست None وليست فارغة
            if all_assets:
                for asset in all_assets:
                    # التحقق من أن asset هو tuple أو list وله عنصر أول
                    if isinstance(asset, (list, tuple)) and len(asset) > 0 and isinstance(asset[0], str):
                        if "otc" in asset[0].lower():
                            self.symbols.append(asset[0])

            # إذا لم يتم العثور على أي أصول تحتوي على "otc"، نستخدم قيمة افتراضية
            if not self.symbols:
                self.symbols = ["EURUSD_otc"]
                print("Warning: No OTC assets found. Using default symbol: EURUSD_otc")

            # الآن يمكننا تعيين self.symbol بأمان
            self.symbol = self.symbols[0]
            print(f"Selected symbol: {self.symbol}")
            # --- نهاية التعديل ---

            await self._load_initial_candles()
            self.root.after(0, self._build_main_ui)
            self.root.after(100, lambda: asyncio.run_coroutine_threadsafe(self._start_streaming(), self.loop))

        except Exception as e:
            error_msg = f"فشل في التهيئة: {str(e)}"
            print(f"Critical Error in _connect_and_init: {error_msg}") # طباعة الخطأ في الكونسول
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("خطأ في التهيئة", msg))
            # حتى في حالة الفشل، نبني واجهة المستخدم الأساسية لإظهار الأزرار للمستخدم
            self.root.after(0, self._build_main_ui)

    async def _load_initial_candles(self):
        end_time = time.time()
        raw_candles = await self.client.get_candles(self.symbol, end_time, 3600, self.tf_seconds)
        if not raw_candles:
            return
        processed = process_candles(raw_candles, self.tf_seconds)
        for candle in processed[-20:]:
            if all(k in candle for k in ["open", "high", "low", "close", "time"]):
                self.candles.append({
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "time": candle["time"]
                })

    async def _start_streaming(self):
        while self.is_connected:
            try:
                data = await self.client.get_realtime_price(self.symbol)
                # --- التعديل الأساسي: التحقق من صحة البيانات ---
                if not data or not isinstance(data, list) or len(data) == 0:
                    # إذا كانت البيانات غير صالحة، ننتظر ونعيد المحاولة
                    await asyncio.sleep(0.5)
                    continue

                latest = data[-1]

                # التحقق من أن 'latest' هو قاموس
                if not isinstance(latest, dict):
                    await asyncio.sleep(0.5)
                    continue

                # محاولة استخراج السعر بأمان
                price = None
                for key in ["price", "current_price", "value"]:
                    if key in latest and isinstance(latest[key], (int, float)) and latest[key] > 0:
                        price = latest[key]
                        break

                # إذا لم نستطع استخراج سعر صالح، نتخطى هذه الدورة
                if price is None:
                    await asyncio.sleep(0.5)
                    continue
                # --- نهاية التعديل ---

                self.current_price = price
                timestamp = latest.get("time", time.time())
                self._update_candles(timestamp, self.current_price)

                signals = self.client.get_signal_data()
                if signals:
                    for sig in signals:
                        y = self.current_price * 0.998 if sig.get("action") == "call" else self.current_price * 1.002
                        self.signals.append({
                            "x": len(self.candles) - 0.4,
                            "y": y,
                            "bot": "SignalBot",
                            "signal": sig.get("action", "CALL").upper(),
                            "price": self.current_price,
                            "time": datetime.now().strftime("%H:%M"),
                            "symbol": self.symbol,
                            "tf": self.tf_name
                        })
                        # ✅ تنظيف الإشارات القديمة
                        if len(self.signals) > MAX_SIGNALS:
                            self.signals.pop(0)

                await asyncio.sleep(0.2)
            except Exception as e:
                print(f"Stream error: {e}")
                await asyncio.sleep(2)

    def _update_candles(self, timestamp, price):
        now = time.time()
        if not self.candles or now - self.candles[-1]["time"] >= self.tf_seconds:
            self.candles.append({"open": price, "high": price, "low": price, "close": price, "time": now})
            if len(self.candles) > CANDLE_COUNT:
                self.candles.pop(0)
        else:
            last = self.candles[-1]
            last["close"] = price
            last["high"] = max(last["high"], price)
            last["low"] = min(last["low"], price)

    def _build_main_ui(self):
        style = ttk.Style()
        style.configure("neon.TButton", background=NEON_BLUE, foreground="white", font=("Consolas", 10, "bold"), padding=8)
        style.map("neon.TButton", background=[("active", "#006999")])

        self._build_top_bar()
        self._build_sidebar()
        self._build_chart_area()
        self._build_bot_panel()
        self._start_ui_updater()

    def _build_top_bar(self):
        top = tk.Frame(self.root, bg=PANEL_BG, height=70)
        top.pack(side=tk.TOP, fill=tk.X)
        top.pack_propagate(False)

        title_font = ("Orbitron", 16, "bold") if "Orbitron" in tk.font.families() else ("Arial", 16, "bold")
        title = tk.Label(top, text="⚡ PyQuotex Live Pro", bg=PANEL_BG, fg=NEON_GREEN, font=title_font)
        title.pack(side=tk.LEFT, padx=20)

        self.price_var = tk.StringVar(value="📊 0.00000")
        price_font = ("Digital-7", 14) if "Digital-7" in tk.font.families() else ("Consolas", 14)
        price_lbl = tk.Label(top, textvariable=self.price_var, bg=PANEL_BG, fg=NEON_YELLOW, font=price_font)
        price_lbl.pack(side=tk.RIGHT, padx=20)

    def _build_sidebar(self):
        sidebar = tk.Frame(self.root, bg=PANEL_BG, width=220)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="💱 ASSETS", bg=PANEL_BG, fg=NEON_BLUE, font=("Orbitron", 10, "bold")).pack(pady=(20, 10))

        search_frame = tk.Frame(sidebar, bg=PANEL_BG)
        search_frame.pack(pady=5)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search_change)
        tk.Entry(search_frame, textvariable=self.search_var, width=15, bg=CANVAS_BG, fg=TEXT_WHITE).pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="🔍", bg=NEON_BLUE, fg="white", font=("Arial", 9)).pack(side=tk.LEFT)

        canvas = tk.Canvas(sidebar, bg=PANEL_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=PANEL_BG)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.asset_buttons = {}
        for sym in self.symbols:
            btn = tk.Button(scrollable_frame, text=sym, bg=PANEL_BG, fg=TEXT_WHITE, font=("Arial", 9), width=18, height=1,
                            command=lambda s=sym: self._on_symbol_change(s))
            btn.pack(pady=2, padx=10, fill=tk.X)
            self.asset_buttons[sym] = btn

        # تفعيل الزر للرمز الحالي (إذا كان موجودًا)
        if self.symbol in self.asset_buttons:
            self.asset_buttons[self.symbol].config(bg=ACTIVE_BTN, fg=NEON_GREEN)

        # ✅ ComboBox للفريمات
        tk.Label(sidebar, text="⏱ TIMEFRAMES", bg=PANEL_BG, fg=NEON_GREEN, font=("Orbitron", 10, "bold")).pack(pady=(20, 5))
        self.tf_var = tk.StringVar(value=self.tf_name)
        tf_combo = ttk.Combobox(sidebar, textvariable=self.tf_var, values=TIMEFRAMES, state="readonly", width=12, font=("Arial", 9))
        tf_combo.pack(pady=5)
        tf_combo.bind("<<ComboboxSelected>>", lambda e: self._on_tf_change())

        ttk.Button(sidebar, text="⚙ Manage Bots", style="neon.TButton", command=self._toggle_bot_panel).pack(pady=30, padx=10, fill=tk.X)

    def _on_search_change(self, *args):
        query = self.search_var.get().lower()
        for sym, btn in self.asset_buttons.items():
            btn.config(state="normal")

    def _on_symbol_change(self, symbol):
        for btn in self.asset_buttons.values():
            btn.config(bg=PANEL_BG, fg=TEXT_WHITE)
        self.asset_buttons[symbol].config(bg=ACTIVE_BTN, fg=NEON_GREEN)
        self.symbol = symbol
        self.candles = []
        self.signals = [s for s in self.signals if not (s["symbol"] == self.symbol and s["tf"] == self.tf_name)]

    def _on_tf_change(self):
        self.tf_name = self.tf_var.get()
        self.tf_seconds = TIMEFRAME_MAP[self.tf_name]
        self.candles = []

    def _toggle_bot_panel(self):
        if self.show_bots_panel:
            self.bot_panel.pack_forget()
        else:
            self.bot_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.show_bots_panel = not self.show_bots_panel

    def _build_chart_area(self):
        chart_frame = tk.Frame(self.root, bg=DARK_BG)
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.fig, self.ax = plt.subplots(figsize=(14, 8))
        self.fig.patch.set_facecolor(DARK_BG)
        self.ax.set_facecolor(DARK_BG)

        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _start_ui_updater(self):
        def update():
            if self.current_price:
                precision = 5 if "JPY" not in self.symbol else 3
                self.price_var.set(f"📊 {self.current_price:.{precision}f}")
            self._draw_chart()
            if self.is_connected:
                self.root.after(300, update)
        update()

    def _draw_chart(self):
        try:
            self.ax.clear()
            if not self.candles:
                return

            prices = [c["high"] for c in self.candles] + [c["low"] for c in self.candles] + [self.current_price]
            min_p, max_p = min(prices), max(prices)
            padding = (max_p - min_p) * 0.12
            self.ax.set_ylim(min_p - padding, max_p + padding)
            self.ax.set_xlim(-1, len(self.candles) + 1)

            width = 0.6
            for i, c in enumerate(self.candles):
                o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
                color = NEON_GREEN if cl >= o else NEON_PINK
                self.ax.plot([i, i], [l, h], color=color, linewidth=2.0)
                rect = Rectangle((i - width/2, min(o, cl)), width, abs(cl - o), color=color, alpha=0.8)
                self.ax.add_patch(rect)

            self.ax.axhline(y=self.current_price, color=NEON_YELLOW, linestyle="--", linewidth=1.8)

            for sig in self.signals:
                if sig["symbol"] == self.symbol and sig["tf"] == self.tf_name:
                    x, y = sig["x"], sig["y"]
                    color = "green" if "CALL" in sig["signal"] else "red"
                    va = "top" if "SELL" in sig["signal"] else "bottom"
                    xytext = (x, y + 0.0002 if "SELL" in sig["signal"] else y - 0.0002)
                    # --- تم تعديل هذا السطر لتجنب كسر السطر ---
                    label_text = f"{'↓' if 'SELL' in sig['signal'] else '↑'} {sig['bot']} @ {sig['price']:.{5 if 'JPY' not in self.symbol else 3}f}"
                    self.ax.annotate(
                        label_text,
                        xy=(x, y), xytext=xytext,
                        fontsize=9, color="white", ha="center", va=va,
                        arrowprops=dict(facecolor=color, shrink=0.05),
                        bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.8)
                    )

            self.ax.grid(axis='y', linestyle='--', alpha=0.2)
            self.ax.set_xticks([])
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Draw error: {e}")

    def _build_bot_panel(self):
        self.bot_panel = tk.Frame(self.root, bg=PANEL_BG, width=350)
        self.bot_panel.pack_forget()

        tk.Label(self.bot_panel, text="🤖 BOT STUDIO", bg=PANEL_BG, fg=NEON_PINK, font=("Orbitron", 12, "bold")).pack(pady=15)

        tk.Label(self.bot_panel, text="Bot Name:", bg=PANEL_BG, fg=TEXT_WHITE, font=("Arial", 9)).pack(anchor="w", padx=20)
        self.bot_name_entry = tk.Entry(self.bot_panel, width=25, bg=CANVAS_BG, fg=NEON_GREEN, font=("Arial", 10))
        self.bot_name_entry.pack(pady=5, padx=20)

        tk.Label(self.bot_panel, text="Python Code:", bg=PANEL_BG, fg=TEXT_WHITE, font=("Arial", 9)).pack(anchor="w", padx=20)
        self.bot_code_text = scrolledtext.ScrolledText(self.bot_panel, height=12, width=40, bg=CANVAS_BG, fg=NEON_BLUE, font=("Courier", 10))
        self.bot_code_text.pack(padx=20, pady=5)

        btn_frame = tk.Frame(self.bot_panel, bg=PANEL_BG)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="📁 Load", bg="#FFA500", fg="white", command=self._load_bot).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="💾 Save", bg=NEON_GREEN, fg="black", command=self._save_bot).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="▶ Run", bg=NEON_BLUE, fg="white", command=self._run_bot).pack(side=tk.LEFT, padx=5)

    def _load_bot(self):
        name = self.bot_name_entry.get()
        if name in self.bot_manager.get_bots():
            code = self.bot_manager.get_code(name)
            self.bot_code_text.delete(1.0, tk.END)
            self.bot_code_text.insert(tk.END, code)

    def _save_bot(self):
        name = self.bot_name_entry.get().strip()
        code = self.bot_code_text.get(1.0, tk.END).strip()
        if name and code:
            self.bot_manager.add_bot(name, code)
            messagebox.showinfo("Saved", f"✅ Bot '{name}' saved!")

    def _run_bot(self):
        name = self.bot_name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a bot name!")
            return
        signal = self.bot_manager.run_bot(name, self.symbol, self.current_price)
        if signal:
            y = self.current_price * (0.998 if signal["signal"] == "CALL" else 1.002)
            self.signals.append({
                "x": len(self.candles) - 0.4,
                "y": y,
                "bot": name,
                "signal": signal["signal"],
                "price": signal["price"],
                "time": signal["time"],
                "symbol": self.symbol,
                "tf": self.tf_name
            })
            messagebox.showinfo("Signal", f"🚀 {signal['signal']} signal from {name}!")

    def __del__(self):
        self.is_connected = False
        if self.client:
            try:
                self.loop.run_until_complete(self.client.close())
            except:
                pass
        if self.loop.is_running():
            self.loop.stop()

# =================== التشغيل ===================
if __name__ == "__main__":
    root = tk.Tk()
    app = PyQuotexProGUI(root)

    def on_closing():
        app.is_connected = False
        app.loop.call_soon_threadsafe(app.loop.stop)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
