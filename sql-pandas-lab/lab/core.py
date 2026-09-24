"""Ядро лаборатории: каталог файлов, загрузка таблиц, выполнение SQL и pandas-кода."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import keyword
import re
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

LAB_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = LAB_DIR / "data"
CATALOG_FILE = DATA_DIR / "catalog.json"
HISTORY_FILE = DATA_DIR / "history.json"
PROGRESS_FILE = DATA_DIR / "progress.json"

CSV_EXT = {".csv", ".tsv", ".txt"}
EXCEL_EXT = {".xlsx", ".xlsm", ".xls"}
SUPPORTED_EXT = CSV_EXT | EXCEL_EXT
RESERVED_NAMES = {"pd", "np", "dfs", "result", "sql", "duckdb"}
ENCODINGS = ("utf-8", "utf-8-sig", "cp1251", "latin-1")

_TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p",
     "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"],
))


# ---------------------------------------------------------------- имена и пути

def slugify(text: str) -> str:
    """Превращает имя файла/листа в имя таблицы, валидное и для SQL, и для Python."""
    text = "".join(_TRANSLIT.get(ch, ch) for ch in str(text).lower())
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text) or "table"
    if text[0].isdigit():
        text = "t_" + text
    if keyword.iskeyword(text) or text in RESERVED_NAMES:
        text += "_tbl"
    return text


def quote_ident(name: str) -> str:
    """Кавычки для SQL-идентификатора, только если они нужны."""
    if re.fullmatch(r"[a-z_][a-z0-9_]*", name):
        return name
    return '"' + name.replace('"', '""') + '"'


def pandas_col(name: str) -> str:
    return f"[{name!r}]"


def resolve_path(entry: dict) -> Path:
    path = Path(entry["file"])
    return path if path.is_absolute() else DATA_DIR / path


# ---------------------------------------------------------------- каталог

def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def load_catalog() -> dict[str, dict]:
    return _read_json(CATALOG_FILE, {})


def save_catalog(catalog: dict[str, dict]) -> None:
    _write_json(CATALOG_FILE, catalog)


def unique_name(base: str, catalog: dict) -> str:
    name, i = base, 2
    while name in catalog:
        name, i = f"{base}_{i}", i + 1
    return name


# ---------------------------------------------------------------- чтение файлов

def _looks_like_date(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(200)
    if sample.empty or not sample.str.contains(r"\d{1,4}[-./]\d{1,2}[-./]\d{1,4}").mean() > 0.9:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed", dayfirst=sample.str.match(r"\d{2}\.").any())
    return parsed.notna().mean() >= 0.95


def detect_csv_options(path: Path, sep: str | None = None, encoding: str | None = None) -> dict:
    """Подбирает кодировку и разделитель, чтобы сгенерированный код читал файл без сюрпризов."""
    raw = path.read_bytes()[:200_000]
    if encoding is None:
        for enc in ENCODINGS:
            try:
                raw.decode(enc)
                encoding = enc
                break
            except UnicodeDecodeError:
                continue
        if encoding == "utf-8" and raw.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
    if sep is None:
        head = raw.decode(encoding, errors="ignore").splitlines()[:20]
        counts = {s: min((line.count(s) for line in head if line), default=0) for s in [",", ";", "\t", "|"]}
        sep = max(counts, key=counts.get) if max(counts.values()) > 0 else ","
    return {"sep": sep, "encoding": encoding}


def read_table(entry: dict) -> pd.DataFrame:
    path = resolve_path(entry)
    opts = entry.get("options", {})
    if entry["kind"] == "excel":
        df = pd.read_excel(path, sheet_name=entry["sheet"])
    else:
        df = pd.read_csv(path, sep=opts.get("sep", ","), encoding=opts.get("encoding", "utf-8"))
    for col in entry.get("parse_dates", []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed", dayfirst=opts.get("dayfirst", False))
    return df


def _register(catalog: dict, name: str, entry: dict) -> dict:
    df = read_table(entry)
    date_cols = [c for c in df.columns if df[c].dtype == object or pd.api.types.is_string_dtype(df[c])]
    entry["parse_dates"] = [c for c in date_cols if _looks_like_date(df[c])]
    if entry["parse_dates"]:
        first = df[entry["parse_dates"][0]].dropna().astype(str)
        entry.setdefault("options", {})["dayfirst"] = bool(first.str.match(r"\d{2}\.\d{2}\.\d{4}").any())
        df = read_table(entry)
    entry.update(
        name=name,
        rows=int(len(df)),
        cols=int(df.shape[1]),
        columns=[str(c) for c in df.columns],
        added=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    catalog[name] = entry
    return entry


def add_file(path: Path, table_name: str | None = None, sep: str | None = None,
             encoding: str | None = None) -> list[dict]:
    """Регистрирует файл в каталоге. Excel — по таблице на каждый непустой лист."""
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise ValueError(f"Формат {ext} не поддерживается. Нужны: {', '.join(sorted(SUPPORTED_EXT))}")

    stored = str(path.relative_to(DATA_DIR)) if path.is_relative_to(DATA_DIR) else str(path)
    catalog = load_catalog()
    added = []
    if ext in EXCEL_EXT:
        sheets = pd.ExcelFile(path).sheet_names
        for sheet in sheets:
            base = slugify(table_name or path.stem)
            if len(sheets) > 1:
                base = f"{base}_{slugify(sheet)}"
            entry = {"file": stored, "kind": "excel", "sheet": sheet, "options": {}}
            if read_table(entry).empty:
                continue
            added.append(_register(catalog, unique_name(base, catalog), entry))
    else:
        opts = detect_csv_options(path, sep, encoding)
        entry = {"file": stored, "kind": "csv", "options": opts}
        added.append(_register(catalog, unique_name(slugify(table_name or path.stem), catalog), entry))
    save_catalog(catalog)
    return added


def save_upload(filename: str, content: bytes, **kwargs) -> list[dict]:
    """Сохраняет загруженный файл в data/ и регистрирует его."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / Path(filename).name
    if target.exists() and target.read_bytes() != content:
        stem, i = target.stem, 2
        while target.exists():
            target = DATA_DIR / f"{stem}_{i}{target.suffix}"
            i += 1
    target.write_bytes(content)
    return add_file(target, **kwargs)


def remove_table(name: str, delete_file: bool = False) -> None:
    catalog = load_catalog()
    entry = catalog.pop(name, None)
    save_catalog(catalog)
    if entry and delete_file:
        path = resolve_path(entry)
        still_used = any(resolve_path(e) == path for e in catalog.values())
        if not still_used and path.is_relative_to(DATA_DIR) and path.exists():
            path.unlink()


def rename_table(old: str, new: str) -> str:
    catalog = load_catalog()
    new = slugify(new)
    if new in catalog and new != old:
        raise ValueError(f"Таблица «{new}» уже есть")
    entry = catalog.pop(old)
    entry["name"] = new
    catalog[new] = entry
    save_catalog(catalog)
    return new


# ---------------------------------------------------------------- код загрузки

def _kwargs_repr(entry: dict) -> str:
    opts = entry.get("options", {})
    parts = []
    if entry["kind"] == "excel":
        parts.append(f"sheet_name={entry['sheet']!r}")
    else:
        if opts.get("sep", ",") != ",":
            parts.append(f"sep={opts['sep']!r}")
        if opts.get("encoding", "utf-8") != "utf-8":
            parts.append(f"encoding={opts['encoding']!r}")
    if entry.get("parse_dates"):
        parts.append(f"parse_dates={entry['parse_dates']!r}")
        if opts.get("dayfirst"):
            parts.append("dayfirst=True")
    return "".join(", " + p for p in parts)


def pandas_snippet(entry: dict) -> str:
    reader = "read_excel" if entry["kind"] == "excel" else "read_csv"
    path = resolve_path(entry).as_posix()
    return (
        "import pandas as pd\n\n"
        f"{entry['name']} = pd.{reader}(r\"{path}\"{_kwargs_repr(entry)})\n"
        f"{entry['name']}.head()"
    )


def duckdb_snippet(entry: dict) -> str:
    path = resolve_path(entry).as_posix()
    name = entry["name"]
    if entry["kind"] == "excel":
        return (
            "import duckdb, pandas as pd\n\n"
            f"{name} = pd.read_excel(r\"{path}\", sheet_name={entry['sheet']!r})\n"
            f"duckdb.sql(\"SELECT * FROM {name} LIMIT 10\").df()   # DuckDB видит DataFrame по имени"
        )
    opts = entry.get("options", {})
    args = [f"'{path}'"]
    if opts.get("sep", ",") != ",":
        args.append(f"delim = '{opts['sep']}'")
    return (
        "import duckdb\n\n"
        f"duckdb.sql(\"\"\"\n    SELECT *\n    FROM read_csv({', '.join(args)})\n    LIMIT 10\n\"\"\").df()"
    )


def lab_snippet(entry: dict) -> str:
    return (
        "import sys\n"
        f"sys.path.insert(0, r\"{LAB_DIR.as_posix()}\")\n"
        "import lab\n\n"
        f"{entry['name']} = lab.load({entry['name']!r})\n"
        f"lab.sql(\"SELECT COUNT(*) FROM {entry['name']}\")"
    )


# ---------------------------------------------------------------- профиль таблицы

def profile(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "колонка": df.columns.astype(str),
        "тип pandas": [str(t) for t in df.dtypes],
        "не пусто": df.notna().sum().values,
        "пропуски": df.isna().sum().values,
        "уникальных": [df[c].nunique(dropna=True) for c in df.columns],
        "пример": [next(iter(df[c].dropna().astype(str).head(1)), "") for c in df.columns],
    })


# ---------------------------------------------------------------- выполнение

@dataclass
class RunResult:
    ok: bool
    result: object = None
    stdout: str = ""
    error: str = ""
    elapsed: float = 0.0
    figures: list = field(default_factory=list)


def connect(tables: dict[str, pd.DataFrame]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    for name, df in tables.items():
        con.register(name, df)
    return con


def run_sql(query: str, tables: dict[str, pd.DataFrame]) -> RunResult:
    start = time.perf_counter()
    con = connect(tables)
    try:
        statements = [s for s in _split_sql(query) if s.strip()]
        if not statements:
            return RunResult(False, error="Пустой запрос")
        rel = None
        for stmt in statements:
            rel = con.execute(stmt)
        df = rel.df() if rel is not None and rel.description else pd.DataFrame()
        return RunResult(True, df, elapsed=time.perf_counter() - start)
    except duckdb.Error as exc:
        return RunResult(False, error=str(exc), elapsed=time.perf_counter() - start)
    finally:
        con.close()


def _split_sql(query: str) -> list[str]:
    """Делит скрипт по «;», не трогая точки с запятой внутри строк и комментариев."""
    parts, buf, quote, i = [], [], None, 0
    while i < len(query):
        ch = query[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif query.startswith("--", i):
            end = query.find("\n", i)
            end = len(query) if end == -1 else end
            buf.append(query[i:end])
            i = end
            continue
        elif ch == ";":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def run_pandas(code: str, tables: dict[str, pd.DataFrame]) -> RunResult:
    """Выполняет код как ячейку Jupyter: результат — последнее выражение или переменная result."""
    namespace = {"pd": pd, "np": np, "dfs": {k: v.copy() for k, v in tables.items()}}
    namespace.update({k: v for k, v in namespace["dfs"].items()})
    namespace["sql"] = lambda q: _sql_or_raise(q, namespace["dfs"])
    out = io.StringIO()
    start = time.perf_counter()
    try:
        tree = ast.parse(code or "")
        last_expr = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last_expr = ast.Expression(tree.body.pop().value)
        with contextlib.redirect_stdout(out):
            exec(compile(tree, "<pandas>", "exec"), namespace)
            value = eval(compile(last_expr, "<pandas>", "eval"), namespace) if last_expr else namespace.get("result")
        figures = _collect_figures()
        return RunResult(True, value, out.getvalue(), elapsed=time.perf_counter() - start, figures=figures)
    except Exception:  # noqa: BLE001 — показываем пользователю любую ошибку его кода
        tb = traceback.format_exc()
        tb = tb[tb.find('File "<pandas>"'):] if '"<pandas>"' in tb else tb
        return RunResult(False, stdout=out.getvalue(), error=tb, elapsed=time.perf_counter() - start)


def _sql_or_raise(query: str, tables: dict) -> pd.DataFrame:
    res = run_sql(query, tables)
    if not res.ok:
        raise RuntimeError(res.error)
    return res.result


def _collect_figures() -> list:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    figs = [plt.figure(n) for n in plt.get_fignums()]
    plt.close("all")
    return figs


# ---------------------------------------------------------------- история и прогресс

def add_history(kind: str, code: str, ok: bool) -> None:
    history = _read_json(HISTORY_FILE, [])
    if history and history[0]["code"] == code and history[0]["kind"] == kind:
        return
    history.insert(0, {"kind": kind, "code": code, "ok": ok, "at": datetime.now().strftime("%Y-%m-%d %H:%M")})
    _write_json(HISTORY_FILE, history[:200])


def load_history(kind: str | None = None) -> list[dict]:
    history = _read_json(HISTORY_FILE, [])
    return [h for h in history if kind is None or h["kind"] == kind]


def load_progress() -> dict:
    return _read_json(PROGRESS_FILE, {})


def mark_solved(task_id: str, mode: str, code: str) -> None:
    progress = load_progress()
    item = progress.setdefault(task_id, {"modes": [], "at": ""})
    if mode not in item["modes"]:
        item["modes"].append(mode)
    item["at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    item[f"code_{mode}"] = code
    _write_json(PROGRESS_FILE, progress)
