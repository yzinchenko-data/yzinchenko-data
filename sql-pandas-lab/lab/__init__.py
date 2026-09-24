"""SQL & Pandas Lab — тренажёр на собственных CSV/Excel.

Использование в Jupyter:

    import sys; sys.path.insert(0, r"<путь к sql-pandas-lab>")
    import lab
    lab.tables()                     # что загружено
    orders = lab.load("orders")      # DataFrame по имени таблицы
    lab.sql("SELECT * FROM orders")  # SQL (DuckDB) по всем таблицам каталога
    lab.path("orders")               # абсолютный путь к файлу
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .core import DATA_DIR, add_file, load_catalog, read_table, resolve_path, run_sql

__all__ = ["tables", "load", "load_all", "sql", "path", "add", "DATA_DIR"]


def tables() -> pd.DataFrame:
    """Список таблиц каталога с размерами и путями."""
    rows = [{"table": n, "rows": e["rows"], "cols": e["cols"], "sheet": e.get("sheet"), "path": str(resolve_path(e))}
            for n, e in load_catalog().items()]
    return pd.DataFrame(rows, columns=["table", "rows", "cols", "sheet", "path"])


def load(name: str) -> pd.DataFrame:
    catalog = load_catalog()
    if name not in catalog:
        raise KeyError(f"Нет таблицы «{name}». Есть: {', '.join(catalog) or 'ничего'}")
    return read_table(catalog[name])


def load_all() -> dict[str, pd.DataFrame]:
    return {n: read_table(e) for n, e in load_catalog().items()}


def sql(query: str) -> pd.DataFrame:
    res = run_sql(query, load_all())
    if not res.ok:
        raise RuntimeError(res.error)
    return res.result


def path(name: str) -> Path:
    return resolve_path(load_catalog()[name])


def add(file_path: str, table_name: str | None = None) -> list[str]:
    """Добавить файл с диска в каталог (без копирования)."""
    return [e["name"] for e in add_file(Path(file_path), table_name)]
