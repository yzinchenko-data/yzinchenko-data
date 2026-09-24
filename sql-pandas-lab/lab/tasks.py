"""Сборник задач: готовые задачи на демо-магазине и автогенерация задач под любую загруженную таблицу."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .core import DATA_DIR, add_file, load_catalog, pandas_col, quote_ident, run_pandas, run_sql, slugify

LEVELS = {1: "🟢 База", 2: "🟡 Средне", 3: "🔴 Сложно"}


@dataclass
class Task:
    id: str
    title: str
    text: str
    level: int
    topic: str
    tables: list[str]
    sql: str
    pandas: str
    hint: str = ""
    ordered: bool = False


# ---------------------------------------------------------------- демо-данные

def create_demo_data() -> list[dict]:
    """Генерирует небольшой интернет-магазин: CSV с «;», CSV с «,» и Excel-лист."""
    rng = np.random.default_rng(42)
    cities = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург", "Краснодар"]
    segments = ["new", "regular", "vip"]
    n_customers, n_products, n_orders = 300, 40, 2500

    customers = pd.DataFrame({
        "customer_id": np.arange(1, n_customers + 1),
        "name": [f"Клиент {i}" for i in range(1, n_customers + 1)],
        "city": rng.choice(cities, n_customers, p=[.35, .2, .12, .11, .12, .1]),
        "segment": rng.choice(segments, n_customers, p=[.5, .38, .12]),
        "signup_date": pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 365, n_customers), "D"),
    })
    categories = {"Электроника": (3000, 60000), "Книги": (300, 1500), "Одежда": (800, 7000),
                  "Дом": (500, 12000), "Спорт": (700, 15000)}
    cat_list = list(categories)
    prod_cat = rng.choice(cat_list, n_products)
    products = pd.DataFrame({
        "product_id": np.arange(1, n_products + 1),
        "product_name": [f"{c[:4]}-{i:03d}" for i, c in enumerate(prod_cat, 1)],
        "category": prod_cat,
        "price": [float(round(rng.uniform(*categories[c]), -1)) for c in prod_cat],
    })
    orders = pd.DataFrame({
        "order_id": np.arange(10001, 10001 + n_orders),
        # ~10% клиентов без заказов — для задач на LEFT JOIN
        "customer_id": rng.choice(np.arange(1, int(n_customers * 0.9) + 1), n_orders),
        "product_id": rng.integers(1, n_products + 1, n_orders),
        "order_date": pd.to_datetime("2024-02-01") + pd.to_timedelta(rng.integers(0, 330, n_orders), "D"),
        "quantity": rng.choice([1, 1, 1, 2, 2, 3, 4, 5], n_orders),
        "status": rng.choice(["delivered", "cancelled", "returned"], n_orders, p=[.84, .11, .05]),
    })

    demo = DATA_DIR / "demo"
    demo.mkdir(parents=True, exist_ok=True)
    customers.assign(signup_date=customers.signup_date.dt.strftime("%Y-%m-%d")).to_csv(
        demo / "customers.csv", sep=";", index=False, encoding="utf-8")
    orders.assign(order_date=orders.order_date.dt.strftime("%Y-%m-%d")).to_csv(demo / "orders.csv", index=False)
    products.to_excel(demo / "products.xlsx", sheet_name="products", index=False)

    catalog = load_catalog()
    added = []
    for file in ["customers.csv", "orders.csv", "products.xlsx"]:
        if slugify(file.rsplit(".", 1)[0]) not in catalog:
            added += add_file(demo / file)
    return added


# ---------------------------------------------------------------- готовые задачи

DEMO_TABLES = ["orders", "customers", "products"]

DEMO_TASKS = [
    Task("demo_01", "Сколько всего заказов", "Посчитайте общее число строк в таблице `orders`.",
         1, "Агрегации", ["orders"],
         "SELECT COUNT(*) AS orders_cnt\nFROM orders",
         "len(orders)",
         "COUNT(*) / len(df)"),
    Task("demo_02", "Города клиентов", "Выведите список уникальных городов из `customers`, отсортированный по алфавиту.",
         1, "Фильтрация и сортировка", ["customers"],
         "SELECT DISTINCT city\nFROM customers\nORDER BY city",
         "customers[['city']].drop_duplicates().sort_values('city')",
         "DISTINCT + ORDER BY / drop_duplicates + sort_values", ordered=True),
    Task("demo_03", "Крупные доставленные заказы",
         "Сколько заказов со статусом `delivered` и количеством товара (`quantity`) не меньше 3?",
         1, "Фильтрация и сортировка", ["orders"],
         "SELECT COUNT(*) AS cnt\nFROM orders\nWHERE status = 'delivered' AND quantity >= 3",
         "len(orders[(orders.status == 'delivered') & (orders.quantity >= 3)])",
         "Два условия через AND; в pandas — & и скобки вокруг каждого условия"),
    Task("demo_04", "Клиенты по сегментам",
         "Для каждого сегмента (`segment`) посчитайте число клиентов. Отсортируйте по убыванию числа клиентов.",
         1, "Группировка", ["customers"],
         "SELECT segment, COUNT(*) AS customers_cnt\nFROM customers\nGROUP BY segment\nORDER BY customers_cnt DESC",
         "customers.groupby('segment').size().reset_index(name='customers_cnt')"
         ".sort_values('customers_cnt', ascending=False)",
         "GROUP BY / groupby().size()", ordered=True),
    Task("demo_05", "Выручка по категориям",
         "Посчитайте выручку (`quantity * price`) по категориям товаров только для доставленных заказов. "
         "Отсортируйте по убыванию выручки.",
         2, "JOIN", ["orders", "products"],
         "SELECT p.category, SUM(o.quantity * p.price) AS revenue\nFROM orders o\n"
         "JOIN products p USING (product_id)\nWHERE o.status = 'delivered'\nGROUP BY p.category\nORDER BY revenue DESC",
         "(orders[orders.status == 'delivered']\n .merge(products, on='product_id')\n"
         " .assign(revenue=lambda d: d.quantity * d.price)\n .groupby('category', as_index=False)['revenue'].sum()\n"
         " .sort_values('revenue', ascending=False))",
         "Соедините orders и products по product_id, затем фильтр → группировка", ordered=True),
    Task("demo_06", "Топ-5 клиентов",
         "Найдите 5 клиентов с наибольшей выручкой по доставленным заказам: `customer_id`, `name`, `revenue`. "
         "Сортировка по убыванию выручки.",
         2, "JOIN", ["orders", "products", "customers"],
         "SELECT c.customer_id, c.name, SUM(o.quantity * p.price) AS revenue\nFROM orders o\n"
         "JOIN products p USING (product_id)\nJOIN customers c USING (customer_id)\nWHERE o.status = 'delivered'\n"
         "GROUP BY c.customer_id, c.name\nORDER BY revenue DESC\nLIMIT 5",
         "(orders[orders.status == 'delivered']\n .merge(products, on='product_id')\n .merge(customers, on='customer_id')\n"
         " .assign(revenue=lambda d: d.quantity * d.price)\n .groupby(['customer_id', 'name'], as_index=False)['revenue'].sum()\n"
         " .nlargest(5, 'revenue'))",
         "Два JOIN, GROUP BY по двум полям, ORDER BY + LIMIT / nlargest", ordered=True),
    Task("demo_07", "Заказы по месяцам",
         "Посчитайте число заказов по месяцам. Месяц — строка в формате `YYYY-MM`. Отсортируйте по месяцу.",
         2, "Даты", ["orders"],
         "SELECT strftime(order_date, '%Y-%m') AS month, COUNT(*) AS orders_cnt\nFROM orders\n"
         "GROUP BY month\nORDER BY month",
         "(orders.assign(month=orders.order_date.dt.strftime('%Y-%m'))\n"
         " .groupby('month').size().reset_index(name='orders_cnt'))",
         "strftime / .dt.strftime('%Y-%m')", ordered=True),
    Task("demo_08", "Средний чек по городам",
         "Для каждого города посчитайте средний чек — среднюю сумму `quantity * price` одного доставленного заказа. "
         "Округлите до 2 знаков, сортировка по убыванию среднего чека.",
         2, "JOIN", ["orders", "products", "customers"],
         "SELECT c.city, ROUND(AVG(o.quantity * p.price), 2) AS avg_check\nFROM orders o\n"
         "JOIN products p USING (product_id)\nJOIN customers c USING (customer_id)\nWHERE o.status = 'delivered'\n"
         "GROUP BY c.city\nORDER BY avg_check DESC",
         "(orders[orders.status == 'delivered']\n .merge(products, on='product_id').merge(customers, on='customer_id')\n"
         " .assign(check=lambda d: d.quantity * d.price)\n .groupby('city', as_index=False)['check'].mean().round(2)\n"
         " .sort_values('check', ascending=False))",
         "AVG после JOIN; ROUND(x, 2) / .round(2)", ordered=True),
    Task("demo_09", "Клиенты без заказов",
         "Сколько клиентов не сделали ни одного заказа?",
         2, "JOIN", ["customers", "orders"],
         "SELECT COUNT(*) AS cnt\nFROM customers c\nLEFT JOIN orders o USING (customer_id)\nWHERE o.order_id IS NULL",
         "(~customers.customer_id.isin(orders.customer_id)).sum()",
         "LEFT JOIN + IS NULL, или NOT EXISTS; в pandas — ~isin"),
    Task("demo_10", "Доля отмен",
         "Какой процент заказов имеет статус `cancelled`? Округлите до 2 знаков.",
         2, "Агрегации", ["orders"],
         "SELECT ROUND(100.0 * AVG(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancel_pct\nFROM orders",
         "round((orders.status == 'cancelled').mean() * 100, 2)",
         "Среднее от индикатора 0/1 — это доля"),
    Task("demo_11", "Когорты по первому заказу",
         "Для каждого клиента найдите месяц первого заказа (`YYYY-MM`) и посчитайте, сколько клиентов в каждой когорте. "
         "Сортировка по месяцу.",
         3, "Оконные функции и CTE", ["orders"],
         "WITH first_orders AS (\n    SELECT customer_id, MIN(order_date) AS first_date\n    FROM orders\n"
         "    GROUP BY customer_id\n)\nSELECT strftime(first_date, '%Y-%m') AS cohort, COUNT(*) AS customers_cnt\n"
         "FROM first_orders\nGROUP BY cohort\nORDER BY cohort",
         "(orders.groupby('customer_id')['order_date'].min().dt.strftime('%Y-%m')\n"
         " .value_counts().sort_index().rename_axis('cohort').reset_index(name='customers_cnt'))",
         "Сначала CTE с MIN(order_date) по клиенту, потом группировка по месяцу", ordered=True),
    Task("demo_12", "Лучший товар в каждой категории",
         "Для каждой категории найдите товар с максимальной выручкой по доставленным заказам: "
         "`category`, `product_name`, `revenue`. Сортировка по категории.",
         3, "Оконные функции и CTE", ["orders", "products"],
         "WITH rev AS (\n    SELECT p.category, p.product_name, SUM(o.quantity * p.price) AS revenue,\n"
         "           ROW_NUMBER() OVER (PARTITION BY p.category ORDER BY SUM(o.quantity * p.price) DESC) AS rn\n"
         "    FROM orders o\n    JOIN products p USING (product_id)\n    WHERE o.status = 'delivered'\n"
         "    GROUP BY p.category, p.product_name\n)\nSELECT category, product_name, revenue\nFROM rev\nWHERE rn = 1\n"
         "ORDER BY category",
         "rev = (orders[orders.status == 'delivered']\n       .merge(products, on='product_id')\n"
         "       .assign(revenue=lambda d: d.quantity * d.price)\n"
         "       .groupby(['category', 'product_name'], as_index=False)['revenue'].sum())\n"
         "rev.sort_values('revenue', ascending=False).groupby('category').head(1).sort_values('category')",
         "ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...) / sort_values + groupby().head(1)", ordered=True),
    Task("demo_13", "Накопительная выручка",
         "Посчитайте выручку доставленных заказов по месяцам (`YYYY-MM`) и накопительный итог `cum_revenue`. "
         "Колонки: `month`, `revenue`, `cum_revenue`, сортировка по месяцу.",
         3, "Оконные функции и CTE", ["orders", "products"],
         "WITH m AS (\n    SELECT strftime(o.order_date, '%Y-%m') AS month, SUM(o.quantity * p.price) AS revenue\n"
         "    FROM orders o\n    JOIN products p USING (product_id)\n    WHERE o.status = 'delivered'\n    GROUP BY month\n)\n"
         "SELECT month, revenue, SUM(revenue) OVER (ORDER BY month) AS cum_revenue\nFROM m\nORDER BY month",
         "m = (orders[orders.status == 'delivered']\n     .merge(products, on='product_id')\n"
         "     .assign(month=lambda d: d.order_date.dt.strftime('%Y-%m'), revenue=lambda d: d.quantity * d.price)\n"
         "     .groupby('month', as_index=False)['revenue'].sum())\n"
         "m.assign(cum_revenue=m.revenue.cumsum())",
         "SUM(...) OVER (ORDER BY month) / cumsum()", ordered=True),
    Task("demo_14", "Повторные покупатели по сегментам",
         "Для каждого сегмента посчитайте долю (в %, 2 знака) клиентов, сделавших 2 и более заказов, "
         "среди клиентов сегмента с хотя бы одним заказом. Сортировка по сегменту.",
         3, "Оконные функции и CTE", ["orders", "customers"],
         "WITH per_customer AS (\n    SELECT customer_id, COUNT(*) AS n\n    FROM orders\n    GROUP BY customer_id\n)\n"
         "SELECT c.segment, ROUND(100.0 * AVG(CASE WHEN pc.n >= 2 THEN 1 ELSE 0 END), 2) AS repeat_pct\n"
         "FROM per_customer pc\nJOIN customers c USING (customer_id)\nGROUP BY c.segment\nORDER BY c.segment",
         "per_customer = orders.groupby('customer_id').size().rename('n').reset_index()\n"
         "(per_customer.merge(customers, on='customer_id')\n .assign(rep=lambda d: (d.n >= 2) * 100.0)\n"
         " .groupby('segment', as_index=False)['rep'].mean().round(2))",
         "Сначала число заказов на клиента, потом доля по сегменту", ordered=True),
]


# ---------------------------------------------------------------- автогенерация

def generate_tasks(name: str, df: pd.DataFrame) -> list[Task]:
    """Строит набор типовых задач под структуру любой таблицы."""
    t = quote_ident(name)
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
               and df[c].nunique() > 1 and not str(c).lower().endswith("id")]
    dates = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    cats = sorted(
        [c for c in df.columns if c not in numeric and c not in dates and 2 <= df[c].nunique() <= 50],
        key=lambda c: df[c].nunique(),
    )
    tasks = [Task(f"{name}_rows", "Размер таблицы", f"Сколько строк в таблице `{name}`?", 1, "Агрегации", [name],
                  f"SELECT COUNT(*) AS cnt\nFROM {t}", f"len({name})", "COUNT(*) / len(df)")]

    def q(c):
        return quote_ident(str(c))

    def p(c):
        return f"{name}{pandas_col(c)}"

    if cats:
        c = cats[0]
        tasks.append(Task(f"{name}_distinct_{c}", f"Уникальные значения «{c}»",
                          f"Сколько различных (не пустых) значений в колонке `{c}`?", 1, "Агрегации", [name],
                          f"SELECT COUNT(DISTINCT {q(c)}) AS cnt\nFROM {t}", f"{p(c)}.nunique()",
                          "COUNT(DISTINCT col) / nunique()"))
        tasks.append(Task(f"{name}_group_{c}", f"Распределение по «{c}»",
                          f"Для каждого значения `{c}` посчитайте число строк (пустые значения — отдельная группа).",
                          1, "Группировка", [name],
                          f"SELECT {q(c)}, COUNT(*) AS cnt\nFROM {t}\nGROUP BY {q(c)}\nORDER BY cnt DESC",
                          f"{name}.groupby({c!r}, dropna=False).size().reset_index(name='cnt')"
                          ".sort_values('cnt', ascending=False)",
                          "GROUP BY / groupby(..., dropna=False).size()"))
    if numeric:
        n = numeric[0]
        tasks.append(Task(f"{name}_stats_{n}", f"Статистики «{n}»",
                          f"Найдите минимум, максимум и среднее (2 знака) по колонке `{n}` — три колонки в одной строке.",
                          1, "Агрегации", [name],
                          f"SELECT MIN({q(n)}) AS min_v, MAX({q(n)}) AS max_v, ROUND(AVG({q(n)}), 2) AS avg_v\nFROM {t}",
                          f"pd.DataFrame([[{p(n)}.min(), {p(n)}.max(), round({p(n)}.mean(), 2)]], "
                          "columns=['min_v', 'max_v', 'avg_v'])",
                          "MIN / MAX / AVG в одном SELECT"))
        tasks.append(Task(f"{name}_above_avg_{n}", f"Выше среднего по «{n}»",
                          f"Сколько строк, где `{n}` больше среднего значения по всей таблице?",
                          2, "Подзапросы", [name],
                          f"SELECT COUNT(*) AS cnt\nFROM {t}\nWHERE {q(n)} > (SELECT AVG({q(n)}) FROM {t})",
                          f"({p(n)} > {p(n)}.mean()).sum()",
                          "Подзапрос в WHERE / сравнение с .mean()"))
        if cats:
            c = cats[0]
            tasks.append(Task(f"{name}_agg_{c}_{n}", f"«{n}» в разрезе «{c}»",
                              f"Для каждого значения `{c}` посчитайте сумму и среднее (2 знака) по `{n}`. "
                              f"Учитывайте только строки, где `{n}` заполнено. Сортировка по сумме по убыванию.",
                              2, "Группировка", [name],
                              f"SELECT {q(c)}, SUM({q(n)}) AS total, ROUND(AVG({q(n)}), 2) AS avg_v\nFROM {t}\n"
                              f"WHERE {q(n)} IS NOT NULL\nGROUP BY {q(c)}\nORDER BY total DESC",
                              f"({name}.dropna(subset=[{n!r}])\n .groupby({c!r}, dropna=False)[{n!r}]\n"
                              " .agg(total='sum', avg_v='mean')"
                              ".round({'avg_v': 2})\n .reset_index().sort_values('total', ascending=False))",
                              "SUM + AVG с GROUP BY / groupby().agg()"))
            tasks.append(Task(f"{name}_share_{c}_{n}", f"Доля «{c}» в общей сумме «{n}»",
                              f"Для каждого значения `{c}` посчитайте долю (в %, 2 знака) в общей сумме `{n}`. "
                              f"Учитывайте только строки, где `{n}` заполнено.",
                              3, "Оконные функции и CTE", [name],
                              f"SELECT {q(c)}, ROUND(100.0 * SUM({q(n)}) / SUM(SUM({q(n)})) OVER (), 2) AS share_pct\n"
                              f"FROM {t}\nWHERE {q(n)} IS NOT NULL\nGROUP BY {q(c)}",
                              f"s = {name}.dropna(subset=[{n!r}]).groupby({c!r}, dropna=False)[{n!r}].sum()\n"
                              "(s / s.sum() * 100).round(2).reset_index(name='share_pct')",
                              "Оконная SUM(SUM(x)) OVER () даёт общий итог"))
    if dates:
        d = dates[0]
        tasks.append(Task(f"{name}_month_{d}", f"Динамика по месяцам «{d}»",
                          f"Посчитайте число строк по месяцам колонки `{d}` (месяц строкой `YYYY-MM`), сортировка по месяцу.",
                          2, "Даты", [name],
                          f"SELECT strftime({q(d)}, '%Y-%m') AS month, COUNT(*) AS cnt\nFROM {t}\n"
                          f"WHERE {q(d)} IS NOT NULL\nGROUP BY month\nORDER BY month",
                          f"{p(d)}.dropna().dt.strftime('%Y-%m').value_counts().sort_index()"
                          ".rename_axis('month').reset_index(name='cnt')",
                          "strftime(col, '%Y-%m') / .dt.strftime", ordered=True))
    nulls = df.isna().sum()
    if nulls.max() > 0:
        c = nulls.idxmax()
        tasks.append(Task(f"{name}_nulls_{c}", f"Пропуски в «{c}»",
                          f"Сколько пропущенных (NULL) значений в колонке `{c}`?", 1, "Качество данных", [name],
                          f"SELECT COUNT(*) AS cnt\nFROM {t}\nWHERE {q(c)} IS NULL", f"{p(c)}.isna().sum()",
                          "IS NULL / isna()"))
    tasks.append(Task(f"{name}_dups", "Полные дубликаты", f"Сколько строк в `{name}` являются полными дубликатами "
                      "(повторяют уже встречавшуюся строку целиком)?", 2, "Качество данных", [name],
                      f"SELECT COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {t})) AS dups\nFROM {t}",
                      f"{name}.duplicated().sum()", "COUNT(*) минус число DISTINCT-строк / duplicated()"))
    return tasks


def all_tasks(tables: dict[str, pd.DataFrame]) -> list[Task]:
    demo_loaded = all(t in tables for t in DEMO_TABLES)
    tasks = list(DEMO_TASKS) if demo_loaded else []
    for name, df in tables.items():
        if not (demo_loaded and name in DEMO_TABLES):
            tasks += generate_tasks(name, df)
    return tasks


# ---------------------------------------------------------------- проверка ответа

def _to_frame(obj) -> pd.DataFrame:
    if isinstance(obj, pd.DataFrame):
        df = obj
    elif isinstance(obj, pd.Series):
        df = obj.to_frame()
    elif isinstance(obj, (list, tuple)) and obj and not isinstance(obj[0], (list, tuple)):
        df = pd.DataFrame({"value": list(obj)})
    else:
        df = pd.DataFrame([[obj]])
    # Именованный индекс (после groupby / value_counts) — это данные; безымянный — просто номера строк
    named = isinstance(df.index, pd.MultiIndex) or df.index.name is not None
    df = df.reset_index(drop=not named)
    return df


def _cell(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT or v is pd.NA:
        return None
    if isinstance(v, (np.bool_, bool)):
        return float(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        return round(float(v), 2)
    if isinstance(v, pd.Period):
        v = v.to_timestamp()
    if isinstance(v, pd.Timestamp):
        s = v.strftime("%Y-%m-%d %H:%M:%S")
        return s.removesuffix(" 00:00:00")
    return str(v)


def normalize(obj) -> list[tuple]:
    df = _to_frame(obj)
    return [tuple(_cell(v) for v in row) for row in df.itertuples(index=False, name=None)]


def _close(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= 0.011 + 1e-9 * abs(b)
    return a == b


def compare(user, expected, ordered: bool) -> tuple[bool, str]:
    u, e = normalize(user), normalize(expected)
    u_cols = len(u[0]) if u else len(_to_frame(user).columns)
    e_cols = len(e[0]) if e else len(_to_frame(expected).columns)
    if u_cols != e_cols:
        return False, f"Ожидается колонок: {e_cols}, у вас: {u_cols}."
    if len(u) != len(e):
        return False, f"Ожидается строк: {len(e)}, у вас: {len(u)}."
    if not ordered:
        key = lambda row: tuple((x is None, str(x)) for x in row)  # noqa: E731
        u, e = sorted(u, key=key), sorted(e, key=key)
    for i, (ru, re_) in enumerate(zip(u, e)):
        if not all(_close(a, b) for a, b in zip(ru, re_)):
            where = f"строке {i + 1}" if ordered else "одной из строк"
            return False, f"Значения не совпадают в {where}: у вас {ru}, ожидалось {re_}."
    return True, "Верно! 🎉"


def check(task: Task, mode: str, code: str, tables: dict[str, pd.DataFrame]):
    """Возвращает (ok, сообщение, RunResult пользователя, эталонный результат)."""
    reference = run_sql(task.sql, tables)
    if not reference.ok:
        return False, f"Не удалось посчитать эталон: {reference.error}", None, None
    user = run_sql(code, tables) if mode == "sql" else run_pandas(code, tables)
    if not user.ok:
        return False, "Код завершился с ошибкой.", user, reference.result
    if user.result is None:
        return False, "Код ничего не вернул: последняя строка должна быть выражением или задайте переменную result.", \
            user, reference.result
    ok, message = compare(user.result, reference.result, task.ordered)
    return ok, message, user, reference.result
