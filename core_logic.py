
import requests
import json
from datetime import datetime, timedelta
import pandas as pd

# --- Конфигурация 1С OData --- #
# Замените эти значения на актуальные для вашей установки 1С:Розница 3.0
BASE_URL = "https://wap01.scloud.ru/27/sc1242779_d7376c93-01e2-4589-ab4b-f9dca9e53388/odata/standard.odata/"
USERNAME = "dop1246198"
PASSWORD = "dTOJFDt2N2"

# --- Конфигурация ChadGPT API --- #
CHADGPT_API_KEY = "chad-bcecc94e3995c5539e33d602601d2c35a0ec54b9b08c53204211d3909cf0d9e4"
CHADGPT_ENDPOINT = "https://ask.chadgpt.ru/api/public/gpt-5" # Пример, выберите подходящую модель

# --- Функции для работы с OData --- #
def get_odata_data(entity_name, filters=None, select_fields=None, expand_fields=None):
    """Получает данные из 1С через OData API."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (USERNAME, PASSWORD)

    query_params = []
    if filters:
        query_params.append(f"$filter={filters}")
    if select_fields:
        query_params.append(f"$select={','.join(select_fields)}")
    if expand_fields:
        query_params.append(f"$expand={','.join(expand_fields)}")

    full_url = f"{BASE_URL}{entity_name}"
    if query_params:
        full_url += "?" + "&".join(query_params)

    print(f"Запрос к OData: {full_url}")
    try:
        response = requests.get(full_url, headers=headers, auth=auth, verify=False) # verify=False для тестовых серверов с самоподписанными сертификатами
        response.raise_for_status()  # Вызывает исключение для HTTP ошибок (4xx или 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к OData: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Статус код: {e.response.status_code}")
            print(f"Ответ сервера: {e.response.text}")
        return None

# --- Функции для работы с ChadGPT API --- #
def get_chadgpt_response(prompt, history=None):
    """Отправляет запрос к ChadGPT API и возвращает ответ."""
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "message": prompt,
        "api_key": CHADGPT_API_KEY
    }
    if history:
        payload["history"] = history

    try:
        response = requests.post(CHADGPT_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к ChadGPT API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Статус код: {e.response.status_code}")
            print(f"Ответ сервера: {e.response.text}")
        return None

# --- Анализ продаж и формирование отчета --- #
def analyze_sales_and_predict_purchase(start_date_str, end_date_str):
    """Анализирует данные о продажах и предлагает рекомендации по закупкам на 7 дней."""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    print(f"\nАнализ продаж за период с {start_date_str} по {end_date_str} и прогнозирование закупок...")

    # 1. Получение данных о продажах
    sales_filters = f"Период ge datetime'{start_date.isoformat()}' and Период le datetime'{end_date.isoformat()}'"
    sales_data_json = get_odata_data(
        "AccumulationRegister_Продажи",
        filters=sales_filters,
        select_fields=["Номенклатура_Key", "Количество", "Период", "Номенклатура"]
    )

    if not sales_data_json or not sales_data_json.get('value'):
        return "Данные о продажах не получены или отсутствуют.", None

    sales_df = pd.DataFrame(sales_data_json["value"])
    sales_df["Период"] = pd.to_datetime(sales_df["Период"])

    # Агрегация продаж по номенклатуре
    aggregated_sales = sales_df.groupby(["Номенклатура_Key", "Номенклатура"])["Количество"].sum().reset_index()
    aggregated_sales.rename(columns={
        "Номенклатура_Key": "ID Товара",
        "Номенклатура": "Наименование Товара",
        "Количество": "Продано за период"
    }, inplace=True)

    # 2. Получение текущих остатков
    stock_data_json = get_odata_data(
        "AccumulationRegister_ЗапасыНаСкладах",
        select_fields=["Номенклатура_Key", "ВНаличии", "Номенклатура"]
    )

    current_stock_df = pd.DataFrame()
    if stock_data_json and stock_data_json.get('value'):
        current_stock_df = pd.DataFrame(stock_data_json["value"])
        current_stock_df.rename(columns={
            "Номенклатура_Key": "ID Товара",
            "Номенклатура": "Наименование Товара",
            "ВНаличии": "Текущий остаток"
        }, inplace=True)

    # Объединение данных
    merged_data = pd.merge(aggregated_sales, current_stock_df, on="ID Товара", how="left")
    merged_data["Текущий остаток"] = merged_data["Текущий остаток"].fillna(0).astype(int)

    # Формирование промпта для ChadGPT
    prompt_data = merged_data.to_string(index=False)
    prompt = f"""Проанализируй следующие данные о продажах и текущих остатках товаров за период с {start_date_str} по {end_date_str}. 
    Предложи рекомендации по закупке на ближайшие 7 дней, учитывая, что цель - минимизировать упущенные продажи и избежать излишков. 
    Представь рекомендации в виде JSON-массива объектов, где каждый объект соответствует строке таблицы и содержит поля: 'ID Товара', 'Рекомендуемое количество к закупке'.

    Данные:
    {prompt_data}
    """

    chadgpt_response = get_chadgpt_response(prompt)

    if chadgpt_response and chadgpt_response.get("is_success"):
        ai_recommendations_text = chadgpt_response["response"]
        try:
            ai_data = json.loads(ai_recommendations_text)
            if isinstance(ai_data, list):
                ai_df = pd.DataFrame(ai_data)
                # Объединяем AI-рекомендации с исходными данными
                final_df = pd.merge(merged_data, ai_df, on="ID Товара", how="left")
                return "Успешно получены рекомендации от AI.", final_df
            else:
                return "Ответ AI не является JSON-массивом.", merged_data
        except json.JSONDecodeError:
            print("Не удалось распарсить JSON из ответа AI. Возвращаем исходные данные и текст AI.")
            return ai_recommendations_text, merged_data
    else:
        return "Не удалось получить рекомендации от AI.", merged_data

def analyze_underperforming_products(start_date_str, end_date_str):
    """Анализирует данные о продажах и выявляет плохо продающиеся товары."""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    print(f"\nАнализ плохо продающихся товаров за период с {start_date_str} по {end_date_str}...")

    # 1. Получение данных о продажах
    sales_filters = f"Период ge datetime'{start_date.isoformat()}' and Период le datetime'{end_date.isoformat()}'"
    sales_data_json = get_odata_data(
        "AccumulationRegister_Продажи",
        filters=sales_filters,
        select_fields=["Номенклатура_Key", "Количество", "Период", "Номенклатура"]
    )

    if not sales_data_json or not sales_data_json.get('value'):
        return "Данные о продажах не получены или отсутствуют.", None

    sales_df = pd.DataFrame(sales_data_json["value"])
    sales_df["Период"] = pd.to_datetime(sales_df["Период"])

    # Агрегация продаж по номенклатуре
    aggregated_sales = sales_df.groupby(["Номенклатура_Key", "Номенклатура"])["Количество"].sum().reset_index()
    aggregated_sales.rename(columns={
        "Номенклатура_Key": "ID Товара",
        "Номенклатура": "Наименование Товара",
        "Количество": "Продано за период"
    }, inplace=True)

    # Формирование промпта для ChadGPT
    prompt_data = aggregated_sales.to_string(index=False)
    prompt = f"""Проанализируй следующие данные о продажах товаров за период с {start_date_str} по {end_date_str}. 
    Выяви товары, которые продаются плохо (например, имеют низкие объемы продаж по сравнению с другими или нулевые продажи). 
    Представь результаты в виде JSON-массива объектов, где каждый объект соответствует строке таблицы и содержит поля: 'ID Товара', 'Комментарий AI (почему товар плохо продается и что можно сделать)'.

    Данные:
    {prompt_data}
    """

    chadgpt_response = get_chadgpt_response(prompt)

    if chadgpt_response and chadgpt_response.get("is_success"):
        ai_analysis_text = chadgpt_response["response"]
        try:
            ai_data = json.loads(ai_analysis_text)
            if isinstance(ai_data, list):
                ai_df = pd.DataFrame(ai_data)
                # Объединяем AI-анализ с исходными данными
                final_df = pd.merge(aggregated_sales, ai_df, on="ID Товара", how="left")
                return "Успешно получен анализ от AI.", final_df
            else:
                return "Ответ AI не является JSON-массивом.", aggregated_sales
        except json.JSONDecodeError:
            print("Не удалось распарсить JSON из ответа AI. Возвращаем исходные данные и текст AI.")
            return ai_analysis_text, aggregated_sales
    else:
        return "Не удалось получить анализ от AI.", aggregated_sales

def generate_excel_report(data_df, ai_text, filename="report.xlsx"):
    """Генерирует Excel отчет из DataFrame и добавляет текст AI."""
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            data_df.to_excel(writer, sheet_name='Данные', index=False)
            
            # Добавление текста AI на отдельный лист
            ai_sheet = writer.book.create_sheet('Анализ AI')
            # Разбиваем текст на строки и записываем в ячейки
            for i, line in enumerate(ai_text.splitlines()):
                ai_sheet.cell(row=i+1, column=1, value=line)

        return filename
    except Exception as e:
        print(f"Ошибка при создании Excel файла: {e}")
        return None

# Пример использования (для тестирования)
if __name__ == "__main__":
    # Замените на реальные даты для тестирования
    test_start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    test_end_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Тест 1: Прогноз закупки
    ai_text_purchase, purchase_data_df = analyze_sales_and_predict_purchase(test_start_date, test_end_date)
    if purchase_data_df is not None:
        excel_file_purchase = generate_excel_report(purchase_data_df, ai_text_purchase, "purchase_prediction_report.xlsx")
        if excel_file_purchase:
            print(f"Отчет по прогнозу закупки сохранен в: {excel_file_purchase}")
    else:
        print(ai_text_purchase)

    print("\n" + "-"*50 + "\n")

    # Тест 2: Анализ плохо продающихся товаров
    ai_text_underperforming, underperforming_data_df = analyze_underperforming_products(test_start_date, test_end_date)
    if underperforming_data_df is not None:
        excel_file_underperforming = generate_excel_report(underperforming_data_df, ai_text_underperforming, "underperforming_products_report.xlsx")
        if excel_file_underperforming:
            print(f"Отчет по плохо продающимся товарам сохранен в: {excel_file_underperforming}")
    else:
        print(ai_text_underperforming)

    print("\n\nВНИМАНИЕ: Этот код является демонстрационным. Для реального использования необходимо:")
    print("1. Заменить BASE_URL, USERNAME, PASSWORD на актуальные данные вашей 1С:Розница 3.0.")
    print("2. Заменить CHADGPT_API_KEY и CHADGPT_ENDPOINT на актуальные данные ChadGPT API.")
    print("3. Уточнить точные имена сущностей и полей в вашей конфигурации 1С.")
    print("4. **ВАЖНО**: Для корректного формирования таблиц в Excel, ChadGPT должен возвращать ответ в формате JSON, как указано в промпте. Если он возвращает обычный текст, то этот текст будет помещен на отдельный лист 'Анализ AI'. Для автоматического парсинга и включения в основную таблицу, ответ AI должен быть строго структурирован (например, JSON с массивом объектов, где каждый объект - строка таблицы).")
    print("5. Обеспечить безопасное хранение учетных данных и обработку ошибок.")
