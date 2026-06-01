
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart, Command
from datetime import datetime, timedelta
import os

from core_logic import analyze_sales_and_predict_purchase, analyze_underperforming_products, generate_excel_report

# --- Конфигурация Telegram Bot --- #
TELEGRAM_BOT_TOKEN = "8489523431:AAHs0WQvKcpg9HTzIK4fFkN6732Az0XG6Tk" # Замените на токен вашего бота

# --- Конфигурация Прокси (опционально) --- #
# Если вы столкнулись с ошибками подключения к Telegram API (например, "Превышен таймаут семафора"),
# возможно, вам потребуется использовать прокси. Замените на адрес вашего прокси-сервера.
# Пример: "http://user:password@host:port" или "socks5://user:password@host:port"
PROXY_URL = None # "http://your_proxy_address:port"

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def main():
    session = None
    if PROXY_URL:
        session = AiohttpSession(proxy=PROXY_URL)
        bot = Bot(token=TELEGRAM_BOT_TOKEN, session=session)
    else:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

    dp = Dispatcher()

    @dp.message(CommandStart())
    async def command_start_handler(message: types.Message):
        """Обрабатывает команду /start."""
        await message.answer(
            f"Привет, {message.from_user.full_name}! \n\n" \
            "Я бот для анализа продаж 1С:Розница 3.0 и прогнозирования закупок. \n\n" \
            "Доступные команды:\n" \
            "/predict_purchase <ГГГГ-ММ-ДД_начало> <ГГГГ-ММ-ДД_конец> - Спрогнозировать закупку на ближайшие 7 дней.\n" \
            "/analyze_underperforming <ГГГГ-ММ-ДД_начало> <ГГГГ-ММ-ДД_конец> - Проанализировать плохо продающиеся товары.\n\n" \
            "Пример: /predict_purchase 2023-01-01 2023-01-31"
        )

    @dp.message(Command("predict_purchase"))
    async def predict_purchase_handler(message: types.Message):
        """Обрабатывает команду /predict_purchase."""
        args = message.text.split()
        if len(args) != 3:
            await message.answer("Неверный формат команды. Используйте: /predict_purchase <ГГГГ-ММ-ДД_начало> <ГГГГ-ММ-ДД_конец>")
            return

        start_date_str = args[1]
        end_date_str = args[2]

        try:
            datetime.strptime(start_date_str, "%Y-%m-%d")
            datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError:
            await message.answer("Неверный формат даты. Используйте ГГГГ-ММ-ДД.")
            return

        await message.answer("Начинаю прогнозирование закупки. Это может занять некоторое время...")

        ai_text, data_df = analyze_sales_and_predict_purchase(start_date_str, end_date_str)

        if data_df is not None and not data_df.empty:
            excel_filename = f"purchase_prediction_{start_date_str}_{end_date_str}.xlsx"
            excel_path = generate_excel_report(data_df, ai_text, excel_filename)

            if excel_path and os.path.exists(excel_path):
                await message.answer_document(types.FSInputFile(excel_path), caption="Отчет по прогнозу закупки:")
                os.remove(excel_path) # Удаляем файл после отправки
            else:
                await message.answer(f"Ошибка при создании или отправке Excel файла: {ai_text}")
        else:
            await message.answer(f"Не удалось получить данные для прогноза закупки: {ai_text}")

    @dp.message(Command("analyze_underperforming"))
    async def analyze_underperforming_handler(message: types.Message):
        """Обрабатывает команду /analyze_underperforming."""
        args = message.text.split()
        if len(args) != 3:
            await message.answer("Неверный формат команды. Используйте: /analyze_underperforming <ГГГГ-ММ-ДД_начало> <ГГГГ-ММ-ДД_конец>")
            return

        start_date_str = args[1]
        end_date_str = args[2]

        try:
            datetime.strptime(start_date_str, "%Y-%m-%d")
            datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError:
            await message.answer("Неверный формат даты. Используйте ГГГГ-ММ-ДД.")
            return

        await message.answer("Начинаю анализ плохо продающихся товаров. Это может занять некоторое время...")

        ai_text, data_df = analyze_underperforming_products(start_date_str, end_date_str)

        if data_df is not None and not data_df.empty:
            excel_filename = f"underperforming_products_{start_date_str}_{end_date_str}.xlsx"
            excel_path = generate_excel_report(data_df, ai_text, excel_filename)

            if excel_path and os.path.exists(excel_path):
                await message.answer_document(types.FSInputFile(excel_path), caption="Отчет по плохо продающимся товарам:")
                os.remove(excel_path) # Удаляем файл после отправки
            else:
                await message.answer(f"Ошибка при создании или отправке Excel файла: {ai_text}")
        else:
            await message.answer(f"Не удалось получить данные для анализа: {ai_text}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
