import json
import os
import random
import urllib.parse
import urllib.request
import urllib.error

import config

BASE_URL = "http://localhost:8001"

AVAILABLE_STORES = list(config.STORES_TOPOLOGIES.keys())
SELECTED_STORE = os.getenv("TEST_STORE", random.choice(AVAILABLE_STORES))

PASSED = 0
FAILED = 0

print(f"ЗАПУСК ИНТЕГРАЦИОННЫХ ТЕСТОВ ДЛЯ СЕТИ: {SELECTED_STORE.upper()}")


def run_test(name, path, method="GET", data=None,
             expected_status=200, required_keys=None, allow_excel=False):
    global PASSED, FAILED
    print(f"→ {name}", end=" ")

    url = f"{BASE_URL}{path}"
    parsed = urllib.parse.urlparse(url)
    encoded_query = urllib.parse.quote(parsed.query, safe="=&")
    url = urllib.parse.urlunparse(parsed._replace(query=encoded_query))

    req_data = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if data else {}

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            body = response.read()

            if allow_excel and status == 200:
                if len(body) > 0:
                    print("УСПЕШНО (Excel получен)")
                    PASSED += 1
                    return True
                print("ОШИБКА (пустой Excel)")
                FAILED += 1
                return False

            try:
                res_json = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                print(f"ОШИБКА (не JSON, статус {status})")
                FAILED += 1
                return False

            if status != expected_status:
                print(f"ОШИБКА (ожидался {expected_status}, получен {status})")
                print(json.dumps(res_json, indent=4, ensure_ascii=False))
                FAILED += 1
                return False

            if isinstance(res_json, dict) and res_json.get("status") == "error":
                print(f"ОШИБКА (status=error): {res_json.get('message')}")
                FAILED += 1
                return False

            if required_keys:
                for key in required_keys:
                    if key not in res_json:
                        print(f"ОШИБКА (нет ключа '{key}')")
                        FAILED += 1
                        return False

            print("УСПЕШНО")
            print(json.dumps(res_json, indent=4, ensure_ascii=False))
            PASSED += 1
            return True

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        if e.code == expected_status:
            print(f"УСПЕШНО (ожидаемая ошибка {e.code})")
            try:
                print(json.dumps(json.loads(error_body), indent=4, ensure_ascii=False))
            except Exception:
                print(error_body)
            PASSED += 1
            return True
        print(f"ОШИБКА HTTP {e.code}: {error_body}")
        FAILED += 1
        return False

    except Exception as e:
        print(f"СБОЙ ПОДКЛЮЧЕНИЯ: {e}")
        FAILED += 1
        return False


run_test(
    "Корневой эндпоинт",
    "/",
    required_keys=["project", "status"]
)

run_test(
    "Проверка зоны /zone/1",
    "/zone/1",
    required_keys=["current_zone", "status"]
)

run_test(
    "Аналитика: лучший сборщик",
    "/analytics/top-workers",
    required_keys=["status", "лучший_сборщик", "максимум_заказов"]
)

run_test(
    "Аналитика: общая статистика отмен",
    "/analytics/canceled-stats",
    required_keys=["status", "отмены_по_сборщикам", "общий_ущерб_рублей"]
)

run_test(
    "Аналитика: отмены по конкретному сборщику (Максим)",
    "/analytics/canceled-stats?worker_name=Максим",
    required_keys=["status", "сборщик", "количество_отмен", "личный_ущерб_рублей"]
)

run_test(
    "Аналитика: несуществующий сборщик → 404",
    "/analytics/canceled-stats?worker_name=Несуществующий",
    expected_status=404
)

run_test(
    "Простая оптимизация: /orders/optimize",
    "/orders/optimize",
    "POST",
    [
        {"name": "Молоко 3.2%", "zone": "Молочный отдел"},
        {"name": "Хлеб Бородинский", "zone": "Хлебный отдел"}
    ],
    required_keys=["status", "route"]
)

run_test(
    "Построение маршрута по зонам (без ML)",
    "/api/v1/orders/build-zone-route",
    "POST",
    {
        "store_id": SELECTED_STORE,
        "items": ["Молоко 3.2%", "Хлеб Бородинский", "Бананы Эквадор"]
    },
    required_keys=["status", "active_store", "total_items_in_order", "optimized_picking_route"]
)

run_test(
    "Маршрут: пустой список товаров → 422",
    "/api/v1/orders/build-zone-route",
    "POST",
    {"store_id": SELECTED_STORE, "items": []},
    expected_status=422
)

run_test(
    "Маршрут: несуществующий магазин → 404",
    "/api/v1/orders/build-zone-route",
    "POST",
    {"store_id": "не_существует", "items": ["Молоко 3.2%"]},
    expected_status=404
)

run_test(
    "Расчёт предиктивной нагрузки магазина",
    f"/api/v1/analytics/predict-load?store_id={SELECTED_STORE}",
    required_keys=["status", "store_id", "kpi_time_modifier", "verdict"]
)

run_test(
    "Расчёт предиктивной нагрузки: несуществующий магазин → 404",
    "/api/v1/analytics/predict-load?store_id=не_существует",
    expected_status=404
)

run_test(
    "Оптимизация маршрута с ML и congestion",
    "/api/v1/orders/build-optimized-route",
    "POST",
    {
        "store_id": SELECTED_STORE,
        "items": ["Молоко 3.2%", "Хлеб Бородинский", "Бананы Эквадор", "Куриное филе 1кг"]
    },
    required_keys=[
        "status", "store_id", "total_unique_zones_to_visit", "total_items",
        "current_human_weekday", "detected_peak_days_by_statistics",
        "is_today_stat_peak", "external_hour_kick_modifier",
        "estimated_total_picking_time_minutes", "optimized_route_steps"
    ]
)

run_test(
    "Мульти-маршрут для двух клиентов",
    "/api/v1/orders/build-multi-optimized-route",
    "POST",
    {
        "store_id": SELECTED_STORE,
        "orders": [
            ["Молоко 3.2%", "Хлеб Бородинский"],
            ["Бананы Эквадор", "Вода 5л", "Сыр Российский"]
        ]
    },
    required_keys=[
        "status", "store_id", "total_combined_orders", "total_items_to_pick",
        "optimized_combined_route_steps"
    ]
)

run_test(
    "Мульти-маршрут: пустой список заказов → 422",
    "/api/v1/orders/build-multi-optimized-route",
    "POST",
    {"store_id": SELECTED_STORE, "orders": []},
    expected_status=422
)

run_test(
    "ML авто-замена: Молоко 3.2%",
    "/api/v1/orders/suggest-substitution",
    "POST",
    {"missing_item": "Молоко 3.2%"},
    required_keys=[
        "status", "requested_item", "detected_zone",
        "total_substitutions_found", "predictive_availability_rating",
        "recommended_substitutions"
    ]
)

run_test(
    "ML авто-замена: товар без зоны (Без зоны)",
    "/api/v1/orders/suggest-substitution",
    "POST",
    {"missing_item": "Несуществующий товар"},
    required_keys=["status", "detected_zone", "total_substitutions_found"]
)

run_test(
    "ML авто-замена: пустая строка → 422",
    "/api/v1/orders/suggest-substitution",
    "POST",
    {"missing_item": ""},
    expected_status=422
)

run_test(
    "Создание и назначение заказа",
    "/api/v1/orders/assign",
    "POST",
    {
        "store_id": SELECTED_STORE,
        "item_name": "Молоко 3.2%",
        "item_price": 89
    },
    required_keys=["status", "order_id", "assigned_worker"]
)

run_test(
    "Создание заказа: отрицательная цена → 422",
    "/api/v1/orders/assign",
    "POST",
    {
        "store_id": SELECTED_STORE,
        "item_name": "Молоко 3.2%",
        "item_price": -100
    },
    expected_status=422
)

run_test(
    "Создание заказа: пустое имя → 422",
    "/api/v1/orders/assign",
    "POST",
    {
        "store_id": SELECTED_STORE,
        "item_name": "",
        "item_price": 100
    },
    expected_status=422
)

run_test(
    "Отчёт по эффективности (все магазины)",
    "/api/v1/admin/workers-efficiency",
    required_keys=["status", "filter_by_store", "total_workers_tracked", "report"]
)

run_test(
    f"Отчёт по эффективности ({SELECTED_STORE})",
    f"/api/v1/admin/workers-efficiency?store_id={SELECTED_STORE}",
    required_keys=["status", "filter_by_store", "report"]
)

run_test(
    "Excel-отчёт (все магазины)",
    "/api/v1/admin/workers-efficiency/excel",
    allow_excel=True
)

run_test(
    f"Excel-отчёт ({SELECTED_STORE})",
    f"/api/v1/admin/workers-efficiency/excel?store_id={SELECTED_STORE}",
    allow_excel=True
)

print(f"ИТОГ: успешно {PASSED}, провалено {FAILED}, всего {PASSED + FAILED}")

if FAILED > 0:
    exit(1)