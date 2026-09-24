"""SQL & Pandas Lab — интерактивный тренажёр на своих CSV и Excel.

Запуск:  streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from lab import core
from lab.tasks import LEVELS, all_tasks, check, create_demo_data

st.set_page_config(page_title="SQL & Pandas Lab", page_icon="🧪", layout="wide")

PAGES = ["📥 Данные", "🧮 SQL", "🐼 Pandas", "🎯 Задачи", "📓 Jupyter"]

SQL_TEMPLATES = {
    "SELECT с фильтром": "SELECT *\nFROM {t}\nWHERE 1 = 1\nLIMIT 100",
    "GROUP BY": "SELECT {c}, COUNT(*) AS cnt\nFROM {t}\nGROUP BY {c}\nORDER BY cnt DESC",
    "JOIN": "SELECT *\nFROM {t} a\nJOIN другая_таблица b ON a.id = b.id\nLIMIT 100",
    "CTE": "WITH base AS (\n    SELECT *\n    FROM {t}\n)\nSELECT COUNT(*)\nFROM base",
    "Оконная функция": "SELECT *,\n       ROW_NUMBER() OVER (PARTITION BY {c} ORDER BY {c}) AS rn\nFROM {t}\nLIMIT 100",
    "Пропуски по колонкам": "SUMMARIZE {t}",
    "Структура таблицы": "DESCRIBE {t}",
}
PANDAS_TEMPLATES = {
    "Первый взгляд": "{t}.head()",
    "info / describe": "{t}.info()\n{t}.describe(include='all')",
    "Фильтр": "{t}[{t}[{c!r}].notna()].head(20)",
    "groupby": "{t}.groupby({c!r}).size().sort_values(ascending=False)",
    "merge": "{t}.merge(другая_таблица, on='id', how='left')",
    "pivot_table": "{t}.pivot_table(index={c!r}, aggfunc='size')",
    "Пропуски": "{t}.isna().sum()",
    "SQL внутри pandas": "sql(\"SELECT COUNT(*) FROM {t}\")",
}


# ---------------------------------------------------------------- данные

@st.cache_data(show_spinner=False)
def _load_cached(entry_json: str, mtime: float) -> pd.DataFrame:
    return core.read_table(json.loads(entry_json))


def get_tables() -> dict[str, pd.DataFrame]:
    tables = {}
    for name, entry in core.load_catalog().items():
        path = core.resolve_path(entry)
        if not path.exists():
            continue
        tables[name] = _load_cached(json.dumps(entry, sort_keys=True, ensure_ascii=False), path.stat().st_mtime)
    return tables


def go(page: str, **state) -> None:
    """Колбэк: переключить страницу и подставить значения (например, текст запроса)."""
    st.session_state.page = page
    st.session_state.update(state)


def first_text_col(df: pd.DataFrame) -> str:
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            return str(c)
    return str(df.columns[0])


# ---------------------------------------------------------------- общие виджеты

def schema_sidebar(tables: dict[str, pd.DataFrame], mode: str) -> None:
    st.markdown("**Таблицы**")
    if not tables:
        st.caption("Пока пусто — загрузите файлы на вкладке «Данные».")
    for name, df in tables.items():
        with st.expander(f"`{name}` · {len(df):,} × {df.shape[1]}".replace(",", " ")):
            st.dataframe(pd.DataFrame({"колонка": df.columns.astype(str), "тип": df.dtypes.astype(str).values}),
                         hide_index=True, width="stretch")
            if mode == "sql":
                st.button("SELECT * →", key=f"ins_sql_{name}", on_click=go, args=("🧮 SQL",),
                          kwargs={"sql_code": f"SELECT *\nFROM {name}\nLIMIT 100"})
            else:
                st.button(f"{name}.head() →", key=f"ins_pd_{name}", on_click=go, args=("🐼 Pandas",),
                          kwargs={"pd_code": f"{name}.head()"})


def show_result(res: core.RunResult, prefix: str) -> None:
    if res.stdout:
        st.code(res.stdout, language=None)
    if not res.ok:
        st.error("Ошибка")
        st.code(res.error, language=None)
        return
    value = res.result
    if isinstance(value, pd.Series):
        value = value.to_frame()
    if isinstance(value, pd.DataFrame):
        c1, c2, c3 = st.columns(3)
        c1.metric("Строк", f"{len(value):,}".replace(",", " "))
        c2.metric("Колонок", value.shape[1])
        c3.metric("Время", f"{res.elapsed * 1000:.0f} мс")
        st.dataframe(value, width="stretch", height=min(38 + 35 * len(value), 520))
        d1, d2 = st.columns([1, 3])
        d1.download_button("⬇️ CSV", value.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{prefix}_result.csv", mime="text/csv", key=f"dl_{prefix}")
        quick_chart(value, prefix, d2)
    elif value is not None:
        if isinstance(value, (str, int, float, bool)) or pd.api.types.is_scalar(value):
            st.metric("Результат", str(value))
        else:
            st.write(value)
        st.caption(f"{res.elapsed * 1000:.0f} мс")
    elif not res.figures and not res.stdout:
        st.success(f"Выполнено за {res.elapsed * 1000:.0f} мс (без результата: последней строкой поставьте выражение).")
    for fig in res.figures:
        st.pyplot(fig)


def quick_chart(df: pd.DataFrame, prefix: str, container) -> None:
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if df.shape[1] < 2 or not numeric or len(df) > 5000:
        return
    with container.popover("📊 Быстрый график"):
        x = st.selectbox("Ось X", df.columns, key=f"x_{prefix}")
        y = st.multiselect("Значения", [c for c in numeric if c != x], default=[c for c in numeric if c != x][:1],
                           key=f"y_{prefix}")
        kind = st.radio("Тип", ["Столбцы", "Линия"], horizontal=True, key=f"k_{prefix}")
        if y:
            data = df[[x, *y]].set_index(x)
            (st.bar_chart if kind == "Столбцы" else st.line_chart)(data)


def history_block(kind: str, key: str) -> None:
    history = core.load_history(kind)[:30]
    if not history:
        return
    with st.expander(f"🕘 История ({len(history)})"):
        for i, h in enumerate(history):
            c1, c2 = st.columns([6, 1])
            c1.code(h["code"], language="sql" if kind == "sql" else "python")
            c2.caption(("✅ " if h["ok"] else "❌ ") + h["at"])
            c2.button("↩️", key=f"h_{kind}_{i}", on_click=st.session_state.update, args=({key: h["code"]},),
                      help="Вернуть в редактор")


# ---------------------------------------------------------------- страницы

def page_data() -> None:
    st.header("📥 Данные")
    st.caption(f"Файлы копируются в `{core.DATA_DIR}` и сразу становятся таблицами для SQL и переменными для pandas. "
               "Кодировка, разделитель и колонки-даты определяются автоматически.")

    left, right = st.columns([3, 2])
    with left, st.form("upload", clear_on_submit=True):
        files = st.file_uploader("Перетащите CSV или Excel (можно несколько)", type=[e[1:] for e in core.SUPPORTED_EXT],
                                 accept_multiple_files=True)
        with st.expander("Параметры (обычно не нужны)"):
            c1, c2, c3 = st.columns(3)
            table_name = c1.text_input("Имя таблицы", placeholder="по имени файла")
            sep = c2.selectbox("Разделитель CSV", ["авто", ",", ";", "\\t", "|"])
            enc = c3.selectbox("Кодировка", ["авто", *core.ENCODINGS])
        if st.form_submit_button("Загрузить", type="primary", width="stretch") and files:
            for f in files:
                try:
                    added = core.save_upload(
                        f.name, f.getvalue(), table_name=table_name or None,
                        sep=None if sep == "авто" else sep.replace("\\t", "\t"),
                        encoding=None if enc == "авто" else enc)
                    st.toast(f"{f.name} → " + ", ".join(e["name"] for e in added), icon="✅")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"{f.name}: {exc}")
    with right:
        with st.form("by_path", clear_on_submit=True):
            path = st.text_input("…или путь к файлу на диске", placeholder=r"C:\Users\me\Downloads\sales.xlsx")
            st.caption("Файл не копируется — лаборатория читает его по этому пути.")
            if st.form_submit_button("Подключить", width="stretch") and path:
                try:
                    added = core.add_file(Path(path.strip().strip('"')))
                    st.toast("Подключено: " + ", ".join(e["name"] for e in added), icon="✅")
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
        if st.button("🛒 Загрузить демо-магазин (orders, customers, products)", width="stretch"):
            added = create_demo_data()
            st.toast("Демо-данные готовы" if added else "Демо-данные уже загружены", icon="🛒")

    catalog = core.load_catalog()
    tables = get_tables()
    st.subheader(f"Каталог · {len(catalog)} табл.")
    if not catalog:
        st.info("Загрузите первый файл или демо-магазин — и можно тренироваться.")
    for name, entry in catalog.items():
        path = core.resolve_path(entry)
        df = tables.get(name)
        src = path.name + (f" · лист «{entry['sheet']}»" if entry["kind"] == "excel" else "")
        with st.expander(f"**{name}** — {src} · {entry['rows']:,} строк × {entry['cols']} колонок".replace(",", " ")):
            if df is None:
                st.error(f"Файл не найден: {path}")
                st.button("Убрать из каталога", key=f"rm_missing_{name}", on_click=core.remove_table, args=(name,))
                continue
            b1, b2, b3 = st.columns(3)
            b1.button("🧮 Открыть в SQL", key=f"sql_{name}", on_click=go, args=("🧮 SQL",),
                      kwargs={"sql_code": f"SELECT *\nFROM {name}\nLIMIT 100"}, width="stretch")
            b2.button("🐼 Открыть в Pandas", key=f"pd_{name}", on_click=go, args=("🐼 Pandas",),
                      kwargs={"pd_code": f"{name}.head(20)"}, width="stretch")
            b3.button("🎯 Задачи по таблице", key=f"tk_{name}", on_click=go, args=("🎯 Задачи",),
                      kwargs={"task_set": name}, width="stretch")
            t1, t2, t3, t4 = st.tabs(["Просмотр", "Структура", "Код загрузки", "Управление"])
            with t1:
                st.dataframe(df.head(200), width="stretch")
            with t2:
                st.dataframe(core.profile(df), hide_index=True, width="stretch")
                if entry.get("options"):
                    st.caption("Параметры чтения: " + ", ".join(f"{k}={v!r}" for k, v in entry["options"].items()))
            with t3:
                st.markdown("**Путь к файлу**")
                st.code(path.as_posix(), language=None)
                st.markdown("**pandas** — вставьте в Jupyter / скрипт")
                st.code(core.pandas_snippet(entry), language="python")
                st.markdown("**DuckDB SQL**")
                st.code(core.duckdb_snippet(entry), language="python")
                st.markdown("**Через помощник лаборатории** (все таблицы и SQL в одну строку)")
                st.code(core.lab_snippet(entry), language="python")
            with t4:
                c1, c2 = st.columns(2)
                new = c1.text_input("Новое имя", value=name, key=f"rn_{name}")
                if c1.button("Переименовать", key=f"rnb_{name}") and new != name:
                    try:
                        core.rename_table(name, new)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                del_file = c2.checkbox("Удалить и сам файл из data/", key=f"df_{name}",
                                       disabled=not path.is_relative_to(core.DATA_DIR))
                if c2.button("🗑 Удалить таблицу", key=f"del_{name}"):
                    core.remove_table(name, delete_file=del_file)
                    st.rerun()


def editor_page(kind: str, tables: dict[str, pd.DataFrame]) -> None:
    is_sql = kind == "sql"
    key = "sql_code" if is_sql else "pd_code"
    st.header("🧮 SQL" if is_sql else "🐼 Pandas")
    if is_sql:
        st.caption("Диалект DuckDB — очень близок к PostgreSQL: CTE, оконные функции, `strftime`, `date_trunc`, `ILIKE`. "
                   "Можно несколько запросов через `;` — покажется результат последнего.")
    else:
        st.caption("Каждая таблица — переменная с тем же именем; также доступны `pd`, `np`, словарь `dfs` и `sql(\"...\")`. "
                   "Результат — последнее выражение (как в Jupyter) или переменная `result`. Исходные данные не меняются.")

    main, side = st.columns([3, 1])
    with side:
        schema_sidebar(tables, kind)
    with main:
        if key not in st.session_state:
            first = next(iter(tables), "my_table")
            st.session_state[key] = f"SELECT *\nFROM {first}\nLIMIT 100" if is_sql else f"{first}.head()"
        templates = SQL_TEMPLATES if is_sql else PANDAS_TEMPLATES
        t1, t2 = st.columns([2, 1])
        tpl = t1.selectbox("Шаблон", ["—", *templates], key=f"tpl_{kind}", label_visibility="collapsed")
        if tpl != "—" and tables:
            tname = next(iter(tables))
            code = templates[tpl].format(t=tname, c=first_text_col(tables[tname]))
            t2.button("Вставить шаблон", on_click=st.session_state.update, args=({key: code},), width="stretch")
        code = st.text_area("Код", key=key, height=260, label_visibility="collapsed")
        run = st.button("▶ Выполнить", type="primary", key=f"run_{kind}")
        if run:
            res = core.run_sql(code, tables) if is_sql else core.run_pandas(code, tables)
            core.add_history(kind, code, res.ok)
            st.session_state[f"res_{kind}"] = res
        if f"res_{kind}" in st.session_state:
            show_result(st.session_state[f"res_{kind}"], kind)
        history_block(kind, key)


def page_tasks(tables: dict[str, pd.DataFrame]) -> None:
    st.header("🎯 Задачи")
    if not tables:
        st.info("Загрузите данные или демо-магазин — задачи появятся автоматически.")
        st.button("🛒 Загрузить демо-магазин", on_click=create_demo_data)
        return

    tasks = all_tasks(tables)
    progress = core.load_progress()
    sets = sorted({"Демо-магазин" if t.id.startswith("demo_") else t.tables[0] for t in tasks},
                  key=lambda s: (s != "Демо-магазин", s))
    if st.session_state.get("task_set") not in sets:
        st.session_state.task_set = sets[0]

    progress_bar = st.empty()

    f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
    task_set = f1.selectbox("Набор", sets, key="task_set")
    pool = [t for t in tasks if ("Демо-магазин" if t.id.startswith("demo_") else t.tables[0]) == task_set]
    levels = f2.multiselect("Уровень", list(LEVELS), format_func=LEVELS.get, default=list(LEVELS))
    topics = sorted({t.topic for t in pool})
    topic = f3.selectbox("Тема", ["Все", *topics])
    only_new = f4.toggle("Нерешённые")
    pool = [t for t in pool if t.level in levels and (topic == "Все" or t.topic == topic)
            and not (only_new and t.id in progress)]
    if not pool:
        st.success("По этим фильтрам задач не осталось 🎉")
        return

    def label(t):
        return f"{'✅' if t.id in progress else '⬜'} {LEVELS[t.level][:1]} {t.title} · {t.topic}"

    task = st.selectbox("Задача", pool, format_func=label)
    st.markdown(f"### {task.title}")
    st.markdown(f"{LEVELS[task.level]} · {task.topic} · таблицы: " + ", ".join(f"`{t}`" for t in task.tables))
    st.info(task.text)
    if task.ordered:
        st.caption("Порядок строк важен. Названия колонок можно давать любые — сравниваются значения.")
    else:
        st.caption("Порядок строк не важен. Названия колонок можно давать любые — сравниваются значения.")

    with st.expander("Структура таблиц задачи"):
        for t in task.tables:
            st.markdown(f"`{t}`")
            st.dataframe(tables[t].head(5), width="stretch")

    mode = st.radio("Решаю на", ["SQL", "Pandas"], horizontal=True, key="task_mode")
    m = "sql" if mode == "SQL" else "pandas"
    key = f"task_{task.id}_{m}"
    if key not in st.session_state:
        st.session_state[key] = progress.get(task.id, {}).get(f"code_{m}", "")
    st.text_area("Ваше решение", key=key, height=200,
                 placeholder="SELECT ..." if m == "sql" else f"{task.tables[0]}...  # последняя строка — ответ")

    c1, c2, c3, c4 = st.columns(4)
    do_check = c1.button("✔️ Проверить", type="primary", width="stretch")
    c2.button("▶ Только выполнить", key="try", width="stretch", on_click=st.session_state.update,
              args=({"task_try": key},))
    show_hint = c3.toggle("💡 Подсказка")
    show_solution = c4.toggle("👀 Решение")

    code = st.session_state[key]
    if show_hint and task.hint:
        st.warning(task.hint)
    if do_check:
        ok, message, user_res, expected = check(task, m, code, tables)
        (st.success if ok else st.error)(message)
        if ok:
            core.mark_solved(task.id, m, code)
            st.balloons()
        if user_res is not None:
            show_result(user_res, f"task_{m}")
        if not ok and expected is not None:
            with st.expander("Показать ожидаемый результат"):
                st.dataframe(expected, width="stretch")
    elif st.session_state.pop("task_try", None) == key:
        show_result(core.run_sql(code, tables) if m == "sql" else core.run_pandas(code, tables), f"task_{m}")
    progress = core.load_progress()
    solved = sum(t.id in progress for t in tasks)
    progress_bar.progress(solved / len(tasks), text=f"Решено {solved} из {len(tasks)}")
    if show_solution:
        s1, s2 = st.columns(2)
        s1.markdown("**SQL**")
        s1.code(task.sql, language="sql")
        s2.markdown("**pandas**")
        s2.code(task.pandas, language="python")


def page_jupyter(tables: dict[str, pd.DataFrame]) -> None:
    st.header("📓 Jupyter и свои скрипты")
    st.markdown("Всё, что загружено сюда, доступно в любом ноутбуке одной строкой — пути подставляются сами.")
    st.code(
        "import sys\n"
        f"sys.path.insert(0, r\"{core.LAB_DIR.as_posix()}\")\n"
        "import lab\n\n"
        "lab.tables()                       # список таблиц, размеры и пути\n"
        f"df = lab.load(\"{next(iter(tables), 'orders')}\")         # DataFrame по имени\n"
        "lab.sql(\"SELECT COUNT(*) FROM orders\")  # SQL по всем таблицам\n"
        "lab.path(\"orders\")                 # путь к файлу\n"
        "lab.add(r\"C:/path/to/file.xlsx\")     # подключить новый файл из ноутбука",
        language="python",
    )
    st.markdown(f"Готовый ноутбук-шаблон: `{(core.LAB_DIR / 'practice.ipynb').as_posix()}`")
    if tables:
        st.subheader("Загрузить всё обычным pandas")
        catalog = core.load_catalog()
        body = "\n".join(core.pandas_snippet(e).splitlines()[2] for n, e in catalog.items() if n in tables)
        st.code("import pandas as pd\n\n" + body, language="python")


# ---------------------------------------------------------------- каркас

def main() -> None:
    tables = get_tables()
    with st.sidebar:
        st.title("🧪 SQL & Pandas Lab")
        st.radio("Раздел", PAGES, key="page", label_visibility="collapsed")
        st.divider()
        progress = core.load_progress()
        st.caption(f"Таблиц: **{len(tables)}** · решено задач: **{len(progress)}**")
        st.caption(f"Папка данных:\n`{core.DATA_DIR}`")

    page = st.session_state.get("page", PAGES[0])
    if page == "📥 Данные":
        page_data()
    elif page == "🧮 SQL":
        editor_page("sql", tables)
    elif page == "🐼 Pandas":
        editor_page("pandas", tables)
    elif page == "🎯 Задачи":
        page_tasks(tables)
    else:
        page_jupyter(tables)


main()
