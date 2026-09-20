import os
import asyncpg
import numpy as np
from datetime import datetime, timedelta, timezone
import config

DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgres@db:5432/warehouse_db")
SEED_ORDERS_START_ID = 100000
SEED_ORDERS_END_ID = 110000
TARGET_ORDERS_COUNT = SEED_ORDERS_END_ID - SEED_ORDERS_START_ID
SHIFT_LOAD_MEAN = 35
SHIFT_LOAD_STD = 6
SHIFT_LOAD_MIN = 5
SHIFT_LOAD_MAX = 60
_pool = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(
        DB_URL,
        min_size=5,
        max_size=20,
        command_timeout=10.0
    )

    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                worker_id SERIAL PRIMARY KEY,
                name TEXT,
                orders_per_shift INTEGER DEFAULT 0
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                store_id TEXT,
                item_name TEXT,
                status TEXT,
                item_price INTEGER,
                worker_id INTEGER REFERENCES workers(worker_id),
                created_at TIMESTAMP WITH TIME ZONE
            );
        """)

        workers_count = await conn.fetchval("SELECT COUNT(*) FROM workers;")
        if workers_count == 0:
            rng_workers = np.random.default_rng(seed=7)
            worker_names = ["Максим", "Алексей", "Иван", "Мария"]
            workers_data = []

            for idx, name in enumerate(worker_names, start=1):
                shift_load = int(rng_workers.normal(loc=SHIFT_LOAD_MEAN, scale=SHIFT_LOAD_STD))
                shift_load = max(SHIFT_LOAD_MIN, min(SHIFT_LOAD_MAX, shift_load))
                workers_data.append((idx, name, shift_load))

            await conn.executemany("INSERT INTO workers(worker_id, name, orders_per_shift) VALUES ($1, $2, $3)",
                                   workers_data)

        count = await conn.fetchval("SELECT COUNT(*) FROM orders;")
        if count < TARGET_ORDERS_COUNT:
            await conn.execute("TRUNCATE TABLE orders;")

            workers_rows = await conn.fetch("SELECT worker_id FROM workers;")
            worker_ids = [r["worker_id"] for r in workers_rows]

            rng = np.random.default_rng(seed=42)
            base_time = datetime.now(timezone.utc) - timedelta(days=14)
            available_stores = list(config.STORES_TOPOLOGIES.keys())

            chunk_size = 5000
            current_chunk = []

            for i in range(SEED_ORDERS_START_ID, SEED_ORDERS_END_ID):
                w_id = worker_ids[i % len(worker_ids)]
                item = config.SEED_PRODUCTS[i % len(config.SEED_PRODUCTS)]

                rand_val = rng.random()
                if rand_val < 0.25:
                    status_val = "Отменен"
                else:
                    status_val = "Доставлен"

                price = int(rng.integers(50, 500))
                random_hours = int(rng.integers(0, 24))
                random_days = int(rng.integers(0, 14))
                order_time = base_time + timedelta(days=random_days, hours=random_hours)
                store_val = available_stores[i % len(available_stores)]

                current_chunk.append((i, store_val, item, status_val, price, w_id, order_time))

                if len(current_chunk) == chunk_size:
                    await conn.copy_records_to_table(
                        'orders',
                        records=current_chunk,
                        columns=['order_id', 'store_id', 'item_name', 'status', 'item_price', 'worker_id', 'created_at']
                    )
                    current_chunk = []

            if current_chunk:
                await conn.copy_records_to_table(
                    'orders',
                    records=current_chunk,
                    columns=['order_id', 'store_id', 'item_name', 'status', 'item_price', 'worker_id', 'created_at']
                )


async def get_db():
    global _pool
    async with _pool.acquire() as conn:
        yield conn