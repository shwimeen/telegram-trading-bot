import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from signals import find_trade_setup

logging.basicConfig(level=logging.INFO)

# --- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не задана переменная окружения BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Множество ID пользователей, активировавших бота
active_users = set()

# Список отслеживаемых монет
WATCH_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# --- ВЕБ-СЕРВЕР ДЛЯ KEEP-ALIVE (ОБХОД СНА В RENDER) ---
async def healthcheck(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Healthcheck HTTP server started on port {port}")

# --- ПАНЕЛЬ УПРАВЛЕНИЯ В ЛИЧНОМ ЧАТЕ ---
def get_control_panel(user_id: int):
    is_active = user_id in active_users
    status_text = "🟢 АКТИВЕН" if is_active else "🔴 НЕ АКТИВЕН"
    
    toggle_button = (
        InlineKeyboardButton(text="⛔ Деактивировать бота", callback_data="deactivate_bot")
        if is_active else
        InlineKeyboardButton(text="🚀 Активировать бота", callback_data="activate_bot")
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle_button],
            [InlineKeyboardButton(text="🔍 Проверить рынок сейчас", callback_data="check_now")],
            [InlineKeyboardButton(text="⭐ Моя подписка", callback_data="subscription_info")]
        ]
    )
    return status_text, keyboard

# --- ФОНОВЫЙ СКАНИРОВЩИК ФОРМАЦИЙ ---
async def market_scanner_task(check_interval_seconds: int = 300):
    """Раз в 5 минут проверяет монеты и присылает сигнал активным пользователям в ЛС."""
    await asyncio.sleep(5)
    while True:
        if active_users:
            for symbol in WATCH_PAIRS:
                setup = find_trade_setup(symbol)
                if setup:
                    text = (
                        f"⚡ **ОБНАРУЖЕНА СИГНАЛЬНАЯ ФОРМАЦИЯ!**\n\n"
                        f"🪙 **Монета:** `{setup['symbol']}`\n"
                        f"📈 **Направление:** **{setup['action']}**\n"
                        f"💵 **Текущая цена:** `{setup['price']} $` \n\n"
                        f"🎯 **Формация:** {setup['formation']}\n"
                        f"📊 **RSI:** `{setup['rsi']}`\n\n"
                        f"🛑 **Stop Loss:** `{setup['stop_loss']} $`\n"
                        f"🎯 **Take Profit:** `{setup['take_profit']} $`\n\n"
                        f"⚠️ _Соблюдайте риск-менеджмент!_"
                    )
                    
                    # Отправляем каждому активному пользователю в личный чат
                    for user_id in list(active_users):
                        try:
                            await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
                        except Exception as e:
                            logging.error(f"Не удалось отправить сигнал пользователю {user_id}: {e}")
                            
        await asyncio.sleep(check_interval_seconds)

# --- ОБРАБОТЧИКИ ТЕЛЕГРАМ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    status, keyboard = get_control_panel(message.from_user.id)
    await message.answer(
        f"👋 **Добро пожаловать в Панель Управления Трейдинг-Ботом!**\n\n"
        f"📌 **Твой статус:** {status}\n\n"
        f"Активируй бота, чтобы он автоматически отслеживал рынок (BTC, ETH, SOL) "
        f"и присылал тебе в личные сообщения уведомления при появлении сигналов.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "activate_bot")
async def activate_bot(callback: types.CallbackQuery):
    active_users.add(callback.from_user.id)
    status, keyboard = get_control_panel(callback.from_user.id)
    await callback.answer("Бот активирован!")
    await callback.message.edit_text(
        f"👋 **Панель Управления Трейдинг-Ботом**\n\n"
        f"📌 **Твой статус:** {status}\n\n"
        f"✅ Бот отслеживает рынок в фоновом режиме. Как только появится подходящий сетап, он сразу напишет тебе в этот чат.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "deactivate_bot")
async def deactivate_bot(callback: types.CallbackQuery):
    active_users.discard(callback.from_user.id)
    status, keyboard = get_control_panel(callback.from_user.id)
    await callback.answer("Бот деактивирован.")
    await callback.message.edit_text(
        f"👋 **Панель Управления Трейдинг-Ботом**\n\n"
        f"📌 **Твой статус:** {status}\n\n"
        f"⏸️ Автоматическое сканирование для тебя приостановлено.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "check_now")
async def check_now(callback: types.CallbackQuery):
    await callback.answer("Сканируем рынок...")
    found_any = False
    
    for symbol in WATCH_PAIRS:
        setup = find_trade_setup(symbol)
        if setup:
            found_any = True
            text = (
                f"🎯 **НАЙДЕН СЕТАП (`{setup['symbol']}`)**\n\n"
                f"⚡ **Рекомендация:** **{setup['action']}**\n"
                f"💵 **Цена:** `{setup['price']} $`\n"
                f"💡 **Формация:** {setup['formation']}\n\n"
                f"🛑 **SL:** `{setup['stop_loss']} $` | 🎯 **TP:** `{setup['take_profit']} $`"
            )
            await callback.message.answer(text, parse_mode="Markdown")
            
    if not found_any:
        await callback.message.answer(
            "📊 **Результат проверки:** В данный момент четких формаций для входа нет. Рынок отдыхает.",
            parse_mode="Markdown"
        )

@dp.callback_query(lambda c: c.data == "subscription_info")
async def sub_info(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "⭐ **Управление подпиской**\n\n"
        "Текущий тариф: **Бесплатный (Тестовый)**\n"
        "Здесь появится функционал выбора тарифных планов после подключения платежного модуля.",
        parse_mode="Markdown"
    )

async def main():
    await start_web_server()
    asyncio.create_task(market_scanner_task(300))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())