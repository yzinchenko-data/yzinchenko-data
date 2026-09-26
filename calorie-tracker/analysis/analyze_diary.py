"""Анализ выгрузки из «Дневника калорий».

Берёт два CSV из раздела «Данные» приложения и собирает отчёт в Markdown с графиками:
покрытие данных, средние КБЖУ и попадание в цель, паттерны по дням недели
и приёмам пищи, главные источники калорий, энергобаланс и оценка фактического
расхода энергии по динамике веса.

Запуск:
    python analyze_diary.py --days kalorii-dni.csv --entries kalorii-zapisi.csv --out report
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KCAL_PER_KG = 7700  # приблизительная энергоёмкость 1 кг жировой ткани
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MEALS = {"breakfast": "Завтрак", "lunch": "Обед", "dinner": "Ужин", "snack": "Перекус"}


def load(days_path: Path, entries_path: Path | None) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    days = pd.read_csv(days_path, encoding="utf-8-sig", parse_dates=["date"])
    days = days.sort_values("date").drop_duplicates("date").set_index("date")
    # Дни без записей о еде не считаем нулевым потреблением: это пропуск, а не голодание.
    days["logged"] = days["entries"].fillna(0) > 0
    entries = None
    if entries_path is not None:
        entries = pd.read_csv(entries_path, encoding="utf-8-sig", parse_dates=["date"])
    return days, entries


def quality(days: pd.DataFrame) -> dict:
    span = pd.date_range(days.index.min(), days.index.max(), freq="D")
    logged = days[days["logged"]]
    return {
        "Период": f"{span[0]:%d.%m.%Y} — {span[-1]:%d.%m.%Y} ({len(span)} дн.)",
        "Дней с записями еды": f"{len(logged)} ({len(logged) / len(span):.0%})",
        "Дней с весом": int(days["weight_kg"].notna().sum()),
        "Подозрительно низкие дни (< 800 ккал)": int((logged["kcal"] < 800).sum()),
    }


def nutrition(days: pd.DataFrame) -> dict:
    d = days[days["logged"]]
    goal = d["goal_kcal"].iloc[-1]
    within = (d["kcal"] - d["goal_kcal"]).abs() <= d["goal_kcal"] * 0.1
    energy = d["protein_g"] * 4 + d["fat_g"] * 9 + d["carbs_g"] * 4
    return {
        "Калории в среднем": f"{d['kcal'].mean():.0f} ккал (медиана {d['kcal'].median():.0f}, цель {goal:.0f})",
        "Дней в цели ±10%": f"{within.sum()} из {len(d)} ({within.mean():.0%})",
        "Б / Ж / У в среднем": f"{d['protein_g'].mean():.0f} / {d['fat_g'].mean():.0f} / {d['carbs_g'].mean():.0f} г",
        "Доля калорий Б / Ж / У": " / ".join(
            f"{(d[c] * k / energy).mean():.0%}" for c, k in [("protein_g", 4), ("fat_g", 9), ("carbs_g", 4)]
        ),
        "Клетчатка в среднем": f"{d['fiber_g'].mean():.1f} г",
        "Вода в среднем": f"{days.loc[days['water_glasses'] > 0, 'water_l'].mean():.2f} л",
    }


def energy_balance(days: pd.DataFrame) -> tuple[dict, pd.Series | None]:
    """Сравнивает фактическую динамику веса с ожидаемой по калориям.

    Наклон тренда веса (кг/день) по линейной регрессии переводится в энергию:
    фактический расход ≈ среднее потребление − наклон × 7700.
    """
    w = days["weight_kg"].dropna()
    if len(w) < 5:
        return {"Энергобаланс": "нужно хотя бы 5 взвешиваний"}, None
    trend = w.reindex(pd.date_range(w.index.min(), w.index.max())).interpolate().rolling(7, min_periods=1).mean()
    t = (w.index - w.index[0]).days.to_numpy()
    slope = np.polyfit(t, w.to_numpy(), 1)[0]
    window = days.loc[w.index.min():w.index.max()]
    intake = window.loc[window["logged"], "kcal"].mean()
    est_tdee = intake - slope * KCAL_PER_KG
    out = {
        "Изменение веса (тренд 7 дн.)": f"{trend.iloc[-1] - trend.iloc[0]:+.1f} кг",
        "Скорость": f"{slope * 7:+.2f} кг в неделю",
        "Фактический расход по весу": f"≈ {est_tdee:.0f} ккал/день",
    }
    tdee = window["tdee_kcal"].dropna()
    if len(tdee):
        planned = tdee.iloc[-1]
        out["Расход из настроек"] = f"{planned:.0f} ккал/день"
        out["Расхождение"] = (
            f"{est_tdee - planned:+.0f} ккал/день: недоучёт еды в дневнике или неточная оценка активности"
            if abs(est_tdee - planned) > 150 else f"{est_tdee - planned:+.0f} ккал/день, в пределах погрешности"
        )
    return out, trend


def patterns(days: pd.DataFrame, entries: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    d = days[days["logged"]].copy()
    d["weekday"] = d.index.dayofweek
    by_wd = d.groupby("weekday")["kcal"].agg(["mean", "count"]).reindex(range(7))
    by_wd.index = WEEKDAYS
    res = {"weekday": by_wd}
    if entries is not None and len(entries):
        meal = entries.groupby("meal")["kcal"].sum()
        res["meals"] = (meal / meal.sum()).rename(index=MEALS).sort_values(ascending=False).to_frame("share")
        top = entries.groupby("name").agg(kcal=("kcal", "sum"), times=("kcal", "size"))
        top["share"] = top["kcal"] / top["kcal"].sum()
        res["top"] = top.sort_values("kcal", ascending=False).head(10)
    return res


def plots(days: pd.DataFrame, trend: pd.Series | None, pats: dict, out: Path) -> list[str]:
    files = []
    d = days[days["logged"]]
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.bar(d.index, d["kcal"], color="#1F7A55", alpha=0.45, label="калории за день")
    ax.plot(d["kcal"].rolling(7, min_periods=3).mean(), color="#1F7A55", lw=2, label="среднее за 7 записей")
    ax.plot(d["goal_kcal"], color="#56645B", ls="--", lw=1, label="цель")
    ax.set_ylabel("ккал"); ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out / "kcal.png", dpi=150); plt.close(fig); files.append("kcal.png")

    if trend is not None:
        fig, ax = plt.subplots(figsize=(9, 3.2))
        ax.scatter(days.index, days["weight_kg"], s=14, color="#56645B", label="взвешивания")
        ax.plot(trend, color="#1F7A55", lw=2, label="тренд, 7 дн.")
        ax.set_ylabel("кг"); ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout(); fig.savefig(out / "weight.png", dpi=150); plt.close(fig); files.append("weight.png")

    wd = pats["weekday"]
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(wd.index, wd["mean"], color="#3867D6")
    ax.set_ylabel("ккал в среднем"); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out / "weekday.png", dpi=150); plt.close(fig); files.append("weekday.png")
    return files


def table(d: dict) -> str:
    return "| Показатель | Значение |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in d.items())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", required=True, type=Path, help="CSV «Сводка по дням»")
    ap.add_argument("--entries", type=Path, help="CSV «Записи о еде» (необязательно)")
    ap.add_argument("--out", default=Path("report"), type=Path, help="папка для отчёта")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    days, entries = load(args.days, args.entries)
    if not days["logged"].any():
        raise SystemExit("В выгрузке нет дней с записями о еде.")
    q, n = quality(days), nutrition(days)
    eb, trend = energy_balance(days)
    pats = patterns(days, entries)
    files = plots(days, trend, pats, args.out)

    wd = pats["weekday"].dropna()
    parts = [
        "# Анализ дневника питания", "",
        "## Данные", table(q), "",
        "## Питание", table(n), "", "![Калории по дням](kcal.png)", "",
        "## Вес и энергобаланс", table(eb), "",
        *(["![Вес](weight.png)", ""] if "weight.png" in files else []),
        "## Дни недели", "",
        f"Больше всего калорий — {wd['mean'].idxmax()} ({wd['mean'].max():.0f} ккал), "
        f"меньше всего — {wd['mean'].idxmin()} ({wd['mean'].min():.0f} ккал).", "",
        "![По дням недели](weekday.png)", "",
    ]
    if "meals" in pats:
        parts += ["## Приёмы пищи", "", "| Приём | Доля калорий |", "|---|---|",
                  *[f"| {m} | {s:.0%} |" for m, s in pats["meals"]["share"].items()], ""]
        parts += ["## Главные источники калорий", "", "| Продукт | Ккал всего | Раз | Доля |", "|---|---|---|---|",
                  *[f"| {name} | {r.kcal:.0f} | {int(r.times)} | {r.share:.0%} |" for name, r in pats["top"].iterrows()], ""]
    parts += [
        "## Ограничения", "",
        "- Калорийность базы и оценки Claude приблизительны; ошибка отдельной записи может достигать 20–30%.",
        "- Дни без записей исключены из средних, поэтому пропуски после «срывов» завышают дисциплину.",
        "- 7700 ккал на кг — упрощение: в первые недели диеты вес сильно меняется за счёт воды и гликогена.",
        "- Выводы про дни недели ненадёжны, если по каждому дню меньше 4–5 наблюдений.",
    ]
    (args.out / "report.md").write_text("\n".join(parts), encoding="utf-8")
    print(f"Готово: {args.out / 'report.md'}")


if __name__ == "__main__":
    main()
