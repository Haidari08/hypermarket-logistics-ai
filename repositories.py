import asyncpg

PEAK_DAYS_LIMIT = 3


class OrderRepository:
    @staticmethod
    async def get_active_workers_congestion(db: asyncpg.Connection, store_id: str):
        return await db.fetch(
            "SELECT item_name, COUNT(*) as active_count FROM orders WHERE store_id = $1 AND status = 'В сборке' GROUP BY item_name",
            store_id
        )

    @staticmethod
    async def get_peak_days_statistics(db: asyncpg.Connection, store_id: str):
        return await db.fetch(f"""
            SELECT 
                EXTRACT(DOW FROM created_at)::int + 1 as day_of_week, 
                COUNT(*) as order_count 
            FROM orders 
            WHERE store_id = $1 
            GROUP BY day_of_week 
            ORDER BY order_count DESC 
            LIMIT {PEAK_DAYS_LIMIT}
        """, store_id)

    @staticmethod
    async def find_least_loaded_worker(db: asyncpg.Connection):
        return await db.fetchrow(
            "SELECT worker_id, name, orders_per_shift FROM workers ORDER BY orders_per_shift ASC LIMIT 1"
        )

    @staticmethod
    async def create_and_assign_order(db: asyncpg.Connection, order_id: int, store_id: str, item_name: str,
                                      item_price: int, worker_id: int):
        await db.execute(
            "INSERT INTO orders(order_id, store_id, item_name, status, item_price, worker_id, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())",
            order_id, store_id, item_name, 'В сборке', item_price, worker_id
        )
        await db.execute("UPDATE workers SET orders_per_shift = orders_per_shift + 1 WHERE worker_id = $1", worker_id)

    @staticmethod
    async def get_max_order_id(db: asyncpg.Connection):
        return await db.fetchval("SELECT MAX(order_id) FROM orders")


class AnalyticsRepository:
    @staticmethod
    async def get_top_worker(db: asyncpg.Connection):
        return await db.fetchrow("SELECT name, orders_per_shift FROM workers ORDER BY orders_per_shift DESC LIMIT 1")

    @staticmethod
    async def get_canceled_stats_by_worker(db: asyncpg.Connection, worker_name: str):
        return await db.fetchrow("""
            SELECT 
                workers.worker_id,
                COUNT(CASE WHEN orders.status = 'Отменен' THEN 1 END) as cnt,
                SUM(CASE WHEN orders.status = 'Отменен' THEN orders.item_price END) as total 
            FROM workers
            LEFT JOIN orders ON workers.worker_id = orders.worker_id
            WHERE workers.name = $1
            GROUP BY workers.worker_id
        """, worker_name)

    @staticmethod
    async def get_all_workers_canceled_counts(db: asyncpg.Connection):
        return await db.fetch("""
            SELECT workers.name, COUNT(CASE WHEN orders.status = 'Отменен' THEN 1 END) as cnt
            FROM workers LEFT JOIN orders ON workers.worker_id = orders.worker_id GROUP BY workers.name
        """)

    @staticmethod
    async def get_total_lost_money(db: asyncpg.Connection):
        val = await db.fetchval("SELECT SUM(item_price) FROM orders WHERE status = 'Отменен'")
        return val if val else 0

    @staticmethod
    async def get_all_workers_base_info(db: asyncpg.Connection):
        return await db.fetch("SELECT worker_id, name FROM workers")

    @staticmethod
    async def get_aggregated_efficiency_report(db: asyncpg.Connection, store_id: str = None):
        if store_id:
            return await db.fetch("""
                SELECT 
                    w.worker_id,
                    w.name,
                    COUNT(CASE WHEN o.status = 'Доставлен' THEN 1 END) as success_cnt,
                    COUNT(CASE WHEN o.status = 'Отменен' THEN 1 END) as canceled_cnt
                FROM workers w
                LEFT JOIN orders o ON w.worker_id = o.worker_id AND o.store_id = $1
                GROUP BY w.worker_id, w.name
                ORDER BY w.worker_id
            """, store_id)

        return await db.fetch("""
            SELECT 
                w.worker_id,
                w.name,
                COUNT(CASE WHEN o.status = 'Доставлен' THEN 1 END) as success_cnt,
                COUNT(CASE WHEN o.status = 'Отменен' THEN 1 END) as canceled_cnt
            FROM workers w
            LEFT JOIN orders o ON w.worker_id = o.worker_id
            GROUP BY w.worker_id, w.name
            ORDER BY w.worker_id
        """)