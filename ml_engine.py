import asyncio
import logging
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
import asyncpg

ML_MODELS_CACHE = {
    "load_models": {},
    "availability_models": {}
}

MIN_STORE_ROWS_FOR_LOAD_MODEL = 10
MIN_ITEM_ROWS_FOR_AVAILABILITY_MODEL = 5


def _train_load_model_sync(df: pd.DataFrame) -> LinearRegression | None:
    if len(df) < MIN_STORE_ROWS_FOR_LOAD_MODEL:
        return None

    df_target = df.groupby(['day_of_week', 'hour']).size().reset_index(name='orders_count')
    x_train = df_target[['day_of_week', 'hour']]
    y = df_target['orders_count']

    model = LinearRegression()
    model.fit(x_train, y)
    return model


def _train_availability_model_sync(df_item: pd.DataFrame) -> LogisticRegression | None:
    if len(df_item) < MIN_ITEM_ROWS_FOR_AVAILABILITY_MODEL:
        return None
    if len(df_item['is_canceled'].unique()) != 2:
        return None

    x_train = df_item[['day_of_week', 'hour']]
    y = df_item['is_canceled']

    clf = LogisticRegression()
    clf.fit(x_train, y)
    return clf


async def train_all_models_async(db: asyncpg.Connection):
    logging.info("Инициализация и запуск обучения ML-моделей")

    stores = await db.fetch("SELECT DISTINCT store_id FROM orders")

    for store in stores:
        s_id = store["store_id"]
        rows = await db.fetch("SELECT created_at FROM orders WHERE store_id = $1", s_id)

        if len(rows) >= MIN_STORE_ROWS_FOR_LOAD_MODEL:
            df = pd.DataFrame([{"created_at": r["created_at"]} for r in rows])
            df['hour'] = df['created_at'].dt.hour
            df['day_of_week'] = df['created_at'].dt.weekday + 1

            model = await asyncio.to_thread(_train_load_model_sync, df)
            if model is not None:
                ML_MODELS_CACHE["load_models"][s_id] = model

    rows = await db.fetch("SELECT item_name, status, created_at FROM orders")

    if rows:
        df = pd.DataFrame([{
            "item_name": r["item_name"],
            "status": r["status"],
            "created_at": r["created_at"]
        } for r in rows])

        df['hour'] = df['created_at'].dt.hour
        df['day_of_week'] = df['created_at'].dt.weekday + 1
        df['is_canceled'] = (df['status'] == 'Отменен').astype(int)

        for item in df['item_name'].unique():
            df_item = df[df['item_name'] == item]
            clf = await asyncio.to_thread(_train_availability_model_sync, df_item)
            if clf is not None:
                ML_MODELS_CACHE["availability_models"][item] = clf

    logging.info("Обучение ML-моделей успешно завершено")