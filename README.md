<div align="center">
  <img src="assets/profile-banner.svg" alt="Ярослав Зинченко — аналитик данных" width="100%">
</div>

<br>

**Data / Product Analyst** · Москва · открыт к предложениям

Перехожу в аналитику данных из востоковедения, магистрант НИУ ВШЭ. Работаю с продуктовыми и бизнес-данными: строю SQL-витрины, провожу A/B-тесты, считаю ключевые метрики и довожу расчёты до конкретных рекомендаций с явно обозначенными ограничениями.

[Резюме (PDF)](cv/Yaroslav_Zinchenko_CV.pdf) · [Telegram](https://t.me/ZYaroslavR) · [Email](mailto:yrzinchenko@edu.hse.ru)

<br>

## Обо мне

- Магистрант НИУ ВШЭ; практическую подготовку прошёл в Karpov.Courses — программы «Аналитик данных» и «Симулятор аналитика данных» (2026).
- Специализируюсь на продуктовой аналитике: удержание, воронки, юнит-экономика, сегментация клиентов, A/B-тестирование.
- Каждый проект строю по единой логике — задача → данные → метод → результат → рекомендация → ограничения, — включая случаи, когда эффект оказывался незначимым.
- Проверяю качество данных до расчёта метрик: дубликаты, пропуски, гранулярность, ссылочную целостность.

## Стек

| | |
|---|---|
| **Анализ и статистика** | Python, pandas, NumPy, SciPy, A/B-тесты, bootstrap |
| **SQL и базы данных** | PostgreSQL, ClickHouse, SQLite, оконные функции, CTE |
| **BI и визуализация** | Tableau, Apache Superset, Yandex DataLens, Excel, Google Таблицы |
| **Инструменты** | Git, Docker, Apache Airflow, Jupyter, REST API, GitHub Actions |

## Избранные проекты

| Проект | Что сделано и найдено | Стек |
|---|---|---|
| **[Yandex Metrica Analytics Pipeline](https://github.com/yzinchenko-data/yandex-metrica-analytics-pipeline)** | Сквозной ETL: API Яндекс.Метрики (OAuth, пагинация, retry) → валидация качества → трёхслойная модель PostgreSQL (`raw` → `staging` → `analytics`) → SQL-витрины по трафику, источникам, устройствам и географии → самодостаточный Python-дашборд с поиском аномалий. На демоданных за 599 дней: 2,40 млн пользователей, 3,08 млн визитов, mobile формирует ~58% аудитории с отказами на 15,8 п.п. выше desktop. 43 автотеста, ежедневный CI в GitHub Actions. | Python, PostgreSQL, SQLAlchemy, Docker, Pytest, GitHub Actions |
| **[Аналитика и BI Olist](https://github.com/yzinchenko-data/olist-tableau-analytics)** | PostgreSQL-витрина на уровне заказа: продажи, удержание, RFM, доставка и отзывы. На 96 478 заказах доля повторных клиентов — 3,00%, доля плохих отзывов при опоздании — 53,99% против 9,19% при доставке вовремя. 3 дашборда Tableau и 4 страницы DataLens. [Аналитическая часть →](https://github.com/yzinchenko-data/olist-ecommerce-analytics) | PostgreSQL, SQL, Python, pandas, Tableau, DataLens |
| **[Аналитика роста StudyFlow](https://github.com/yzinchenko-data/studyflow-growth-analytics)** | Воспроизводимый SaaS/EdTech-кейс: продуктовые этапы, когорты, юнит-экономика, A/B-тест. Умный онбординг повысил активацию на 16,89 п.п., оплату — на 7,37 п.п. | Python, pandas, SQL, SQLite, статистика |
| **[Рост и удержание TheLook](https://github.com/yzinchenko-data/thelook-growth-analytics)** | Сквозной аудит 100 тыс. пользователей: чистая выручка $8,07 млн, повторные покупки 30,4%, удержание M1 5,1%. Показано, почему статистически значимый рост конверсии ещё не гарантирует выгодный запуск. | Python, pandas, BigQuery SQL, статистика |
| **[Индекс инвестиционного климата MENA](https://github.com/yzinchenko-data/MENA-INVESTMENT-INDEX)** | Исследовательский индекс для 19 стран за 2000–2024: панель из 475 наблюдений, фиксированные эффекты, Монте-Карло, Dash. Слабый бэктест зафиксирован как явная граница применимости модели. | Python, World Bank API, IMF API, Dash |
| **[Продуктовая аналитика мобильной игры](https://github.com/yzinchenko-data/mobile-game-product-analytics)** | Когортное удержание и A/B-тест предложения. Набор B не рекомендован к запуску: рост ARPU незначим, конверсия снизилась статистически значимо. | Python, pandas, SciPy, A/B-тесты |
| **[ИИ в образовании](https://github.com/yzinchenko-data/ai-education-analyst)** | Разведочный анализ 50 тыс. наблюдений: умеренное использование ИИ связано с приростом GPA, 20+ часов — с риском выгорания. Причинные ограничения обозначены явно. | Python, pandas, SciPy, статистика |

## Визуализация

**[Yandex Metrica Analytics Pipeline — Python-дашборд](https://github.com/yzinchenko-data/yandex-metrica-analytics-pipeline)**

<a href="https://github.com/yzinchenko-data/yandex-metrica-analytics-pipeline">
  <img src="https://raw.githubusercontent.com/yzinchenko-data/yandex-metrica-analytics-pipeline/main/dashboards/dashboard_full.png" alt="Yandex Metrica Analytics Pipeline — дашборд" width="100%">
</a>

Самодостаточный HTML-дашборд без CDN и внешних запросов: Executive Overview, Acquisition, Audience & Technology, Content — с поиском аномалий в дневном трафике и приоритизацией страниц для оптимизации.

[Репозиторий и методология](https://github.com/yzinchenko-data/yandex-metrica-analytics-pipeline)

**[Olist E-commerce Overview — Tableau](https://github.com/yzinchenko-data/olist-tableau-analytics)**

<a href="https://github.com/yzinchenko-data/olist-tableau-analytics">
  <img src="https://raw.githubusercontent.com/yzinchenko-data/olist-tableau-analytics/main/images/olist_dashboard.png" alt="Olist E-commerce Overview — Tableau" width="100%">
</a>

Дашборд продаж и качества исполнения заказов: R$15,8 млн GMV, 99 092 заказа, динамика по времени, топ-10 категорий, карта штатов, статусы и связь задержки доставки с оценкой клиента. Глобальные фильтры пересчитывают все KPI и визуализации.

[Репозиторий и методология](https://github.com/yzinchenko-data/olist-tableau-analytics) · [Скачать workbook](https://github.com/yzinchenko-data/olist-tableau-analytics/raw/main/tableau/olist_ecommerce_dashboard.twbx)

## Учебные проекты Karpov.Courses

Три варианта финального проекта — воспроизводимые аналитические кейсы: проверка качества данных, продуктовые метрики, статистические тесты, ограничения и решение для бизнеса.

**1. [Продуктовая аналитика мобильной игры](https://github.com/yzinchenko-data/mobile-game-product-analytics)**

<a href="https://github.com/yzinchenko-data/mobile-game-product-analytics">
  <img src="assets/karpov/project-1-mobile-game-analytics.png" alt="Продуктовая аналитика мобильной игры" width="100%">
</a>

Когортное удержание, A/B-тест акционных предложений, метрики события. Набор B не рекомендован: рост ARPU не подтверждён, конверсия снизилась значимо.
[Репозиторий](https://github.com/yzinchenko-data/mobile-game-product-analytics) · [Ноутбук](https://github.com/yzinchenko-data/mobile-game-product-analytics/blob/main/notebooks/final_project_variant_1.ipynb) · [Отчёт](https://github.com/yzinchenko-data/mobile-game-product-analytics/blob/main/reports/final_report.md)

**2. [A/B-тест оплаты и сегментация клиентов](https://github.com/yzinchenko-data/karpov-courses-projects/tree/main/project-2-payment-ab-segmentation)**

<a href="https://github.com/yzinchenko-data/karpov-courses-projects/tree/main/project-2-payment-ab-segmentation">
  <img src="assets/karpov/project-2-payment-ab-segmentation.png" alt="A/B-тест оплаты и сегментация клиентов" width="100%">
</a>

CR, ARPU, ARPPU, bootstrap, SQL-сегментация. Значимо вырос только ARPPU — запуск механики без проверки пикового времени платежей (~19:00) не рекомендован.
[Проект](https://github.com/yzinchenko-data/karpov-courses-projects/tree/main/project-2-payment-ab-segmentation) · [Ноутбук](https://github.com/yzinchenko-data/karpov-courses-projects/blob/main/project-2-payment-ab-segmentation/notebooks/project_2_full.ipynb) · [SQL](https://github.com/yzinchenko-data/karpov-courses-projects/blob/main/project-2-payment-ab-segmentation/sql/customer_segmentation.sql)

**3. [A/B-тест цены премиум-подписки](https://github.com/yzinchenko-data/karpov-courses-projects/tree/main/project-3-premium-price-ab-test)**

<a href="https://github.com/yzinchenko-data/karpov-courses-projects/tree/main/project-3-premium-price-ab-test">
  <img src="assets/karpov/project-3-premium-price-ab-test.png" alt="A/B-тест цены премиум-подписки" width="100%">
</a>

Проверка транзакций, A/A-контроль, A/B-тест новой цены. Конверсия снизилась, рост ARPU статистически не подтверждён — новую цену раскатывать не стоит.
[Проект](https://github.com/yzinchenko-data/karpov-courses-projects/tree/main/project-3-premium-price-ab-test) · [Ноутбук](https://github.com/yzinchenko-data/karpov-courses-projects/blob/main/project-3-premium-price-ab-test/notebooks/project_3_variant_3.ipynb) · [Пошаговый разбор](https://github.com/yzinchenko-data/karpov-courses-projects/blob/main/project-3-premium-price-ab-test/docs/project_3_step_by_step_explanation.md)

**[Все учебные проекты Karpov.Courses →](https://github.com/yzinchenko-data/karpov-courses-projects)**

## Контакты

Telegram — [@ZYaroslavR](https://t.me/ZYaroslavR)
Email — [yrzinchenko@edu.hse.ru](mailto:yrzinchenko@edu.hse.ru)
Резюме — [PDF](cv/Yaroslav_Zinchenko_CV.pdf)
