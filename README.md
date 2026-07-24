# CAS — Cellular Analysis System v3.0

**Полная инструкция по нормализации, поиску, фильтрации и сохранению данных**
**Дата:** 2026-07-25

---

## 1. Архитектура проекта

```
~/cas/
├── input/
│   ├── billing/              # Исходные файлы МТС (НЕ трогать)
│   ├── bs/                   # Справочники базовых станций
│   └── normalized/           # Нормализованные файлы (единый шаблон)
├── output/
│   ├── manifests/            # SHA-256 контрольные суммы
│   ├── tables/               # Результаты (Excel, TSV, JSON, TXT, Parquet)
│   ├── maps/                 # Интерактивные карты
│   ├── reports/              # PDF-отчёты
│   └── logs/                 # Журналы операций с row-count
├── config/
│   ├── config.yaml           # Даты, время, формат
│   └── column_aliases.yaml   # Словарь синонимов столбцов
├── scripts/
│   ├── normalize.py          # Нормализация исходных файлов
│   ├── 01_import.py          # Импорт + SHA-256
│   ├── 02_validate.py        # Валидация + нормализация типов
│   ├── 03_extract_dates.py   # Фильтр по датам и времени
│   ├── 04_merge_bs.py        # Сопоставление с БС по адресу
│   ├── ai_formats.py         # Экспорт в AI-форматы
│   ├── search_multi.py       # Массовый поиск
│   ├── search_question2.py   # Поиск по 10.02.2020
│   └── search_question3.py   # Поиск по 24.04.2020
├── cas-venv/                 # Виртуальное окружение
└── Makefile
```

### Поток данных

```
input/billing/*.xlsb, *.xlsx    (исходные файлы)
        │
        ▼
scripts/normalize.py            (единый шаблон)
        │
        ▼
input/normalized/*_normalized.xlsx
        │
        ▼
01_import.py → 02_validate.py → 03_extract_dates.py → 04_merge_bs.py
        │
        ▼
output/tables/billing_extracted.parquet
        │
        ▼
scripts/search_*.py             (поиск по параметрам)
        │
        ▼
output/tables/экспертиза_*.xlsx
```

---

## 2. Единый шаблон столбцов (после нормализации)

| Столбец | Содержание | Пример |
|---------|------------|--------|
| **Дата и время** | Момент соединения | `10.02.2020 12:14:42` или `2020-04-24 14:50:52` |
| **Номер абонента** | Исследуемый номер | `79184610186` |
| **Номер контакта** | С кем связывался | `79883881180` или `internet.mts.ru` |
| **Тип соединения** | GPRS, Вызов, SMS | `GPRS` |
| **Длительность (сек)** | Продолжительность | `48` |
| **IMEI** | Идентификатор устройства | `35722309618673` |
| **LAC** | Location Area Code | `10162` |
| **CI** | Cell Identity | `58566` |
| **Адрес БС** | Адрес базовой станции | `г. Краснодар, ул. Красноармейская, напротив дома №14` |
| **Азимут** | Направление антенны | `120` |

---

## 3. Нормализация исходных файлов

### 3.1 Запуск

```bash
cd ~/cas
source cas-venv/bin/activate
python scripts/normalize.py
```

### 3.2 Что делает

1. Читает все файлы из `input/billing/`
2. Приводит столбцы к единому шаблону
3. Извлекает LAC/CI из форматов: `12322/116175413` и `12362-115902250`
4. Показывает процент заполнения каждого столбца
5. Проверяет, что количество строк совпадает
6. Сохраняет в `input/normalized/`

### 3.3 Пример вывода

```
📄 файл.xlsb
  Строк: 15470 → 15470
  ✅ ROW-COUNT: совпадает (15470)
  Заполнение (% от 15470):
  ✅ Дата и время         100.0% ████████████████████
  ✅ Номер абонента       100.0% ████████████████████
  ✅ Адрес БС              86.4% █████████████████░░░
  ...
```

---

## 4. Настройка дат и времени поиска

### 4.1 Редактирование `config/config.yaml`

```yaml
analysis:
  date_format: "%d.%m.%Y %H:%M:%S"
  date_errors: "raise"
  default_timezone: "Europe/Moscow"
  
  target_dates:
    - date: "2020-02-10"
      time_from: "12:00"
      time_to: "13:00"
    - date: "2020-04-24"
      time_from: "14:50"
      time_to: "15:51"
    - date: "2020-04-24"
      time_from: "16:30"
      time_to: "17:30"
    - date: "2020-04-27"
      time_from: "17:25"
      time_to: "18:20"
    - date: "2020-04-27"
      time_from: "18:40"
      time_to: "19:06"
```

### 4.2 Форматы дат

| Пример в файле | date_format |
|:--------------:|:-----------:|
| `10.02.2020 12:00:00` | `%d.%m.%Y %H:%M:%S` |
| `2020-04-27 17:25:00` | `ISO8601` |

Скрипт `03_extract_dates.py` парсит оба формата автоматически.

---

## 5. Запуск обработки

```bash
make all            # Полный цикл: import → validate → extract → merge
make import         # Только импорт
make validate       # Только валидация
make extract        # Только фильтрация
make merge          # Только сопоставление
make clean          # Очистить результаты
```

### 5.1 Просмотр логов

```bash
cat output/logs/01_import.log    # SHA-256, row-count
cat output/logs/03_extract.log   # Какие даты найдены
cat output/logs/04_merge.log     # Сопоставление, балансировка
```

---

## 6. Поиск данных

Все скрипты поиска работают с нормализованными столбцами. **Имена столбцов после нормализации:** `Дата и время`, `Номер абонента`, `Номер контакта`, `Адрес БС`.

### 6.1 Поиск по номеру телефона

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')

# Принудительно преобразовать ArrowString
for col in df.columns:
    if 'arrow' in str(df[col].dtype):
        df[col] = df[col].astype(str)

target = "79184610186"  # ← ЗАМЕНИ

for col in ["Номер абонента", "Номер контакта"]:
    if col in df.columns:
        mask = df[col].astype(str).str.contains(target, na=False)
        result = df[mask]
        if len(result) > 0:
            safe = target.replace(" ", "_")
            result.to_excel(f"output/tables/поиск_по_номеру_{safe}.xlsx", index=False)
            print(f"✅ {col}: {len(result)} записей")
EOF
```

### 6.2 Поиск по адресу БС

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')

for col in df.columns:
    if 'arrow' in str(df[col].dtype):
        df[col] = df[col].astype(str)

target = "Красноармейск"  # ← ЗАМЕНИ (часть адреса)

mask = df["Адрес БС"].astype(str).str.contains(target, na=False)
result = df[mask]

safe = target.replace(" ", "_")[:50]
result.to_excel(f"output/tables/поиск_по_адресу_{safe}.xlsx", index=False)
print(f"✅ {len(result)} записей")
EOF
```

### 6.3 Поиск по дате и времени

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')

for col in df.columns:
    if 'arrow' in str(df[col].dtype):
        df[col] = df[col].astype(str)

target_date = "24.04.2020"  # ← ЗАМЕНИ
time_from = "14:50"
time_to = "15:51"

df["_dt"] = pd.NaT
df["_dt"] = pd.to_datetime(df["Дата и время"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
df["_dt"] = df["_dt"].fillna(pd.to_datetime(df["Дата и время"], format="ISO8601", errors="coerce"))

target_dt = pd.to_datetime(target_date, format="%d.%m.%Y")
t_from = pd.to_datetime(time_from, format="%H:%M").time()
t_to = pd.to_datetime(time_to, format="%H:%M").time()

subset = df[df["_dt"].dt.date == target_dt.date()]
result = subset[(subset["_dt"].dt.time >= t_from) & (subset["_dt"].dt.time <= t_to)]

safe = f"{target_date}_{time_from.replace(':','')}_{time_to.replace(':','')}"
result.to_excel(f"output/tables/поиск_по_дате_{safe}.xlsx", index=False)
print(f"✅ {len(result)} записей")
EOF
```

### 6.4 Поиск по LAC + CI

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')

for col in df.columns:
    if 'arrow' in str(df[col].dtype):
        df[col] = df[col].astype(str)

target_lac = 10162   # ← ЗАМЕНИ
target_ci = 58566    # ← ЗАМЕНИ

df["LAC"] = pd.to_numeric(df["LAC"], errors="coerce")
df["CI"] = pd.to_numeric(df["CI"], errors="coerce")

result = df[(df["LAC"] == target_lac) & (df["CI"] == target_ci)]
result.to_excel(f"output/tables/поиск_по_LAC{target_lac}_CI{target_ci}.xlsx", index=False)
print(f"✅ {len(result)} записей")
EOF
```

### 6.5 Массовый поиск (все запросы в одном скрипте)

```bash
python scripts/search_multi.py
```

Редактировать список запросов в `scripts/search_multi.py`:

```python
searches = [
    {"name": "номер_79184610186", "type": "phone", "phone": "79184610186"},
    {"name": "адрес_Красноармейская", "type": "address", "address": "Красноармейск"},
    {"name": "LAC10162_CI58566", "type": "lac_ci", "lac": 10162, "ci": 58566},
]
```

---

## 7. Форматы сохранения

| Формат | Расширение | Для чего |
|--------|:----------:|----------|
| **Excel** | `.xlsx` | Эксперт — просмотр, печать, приложение к заключению |
| **TSV** | `.tsv` | AI-анализ — табуляция, устойчив к запятым |
| **TXT** | `.txt` | Промпты AI — выровненная таблица |
| **JSON** | `.json` | API и программная обработка |
| **Parquet** | `.parquet` | Промежуточное хранение — быстрое, типизированное |

Все файлы сохраняются в `output/tables/`.

---

## 8. Ключевые особенности после нормализации

| Особенность | Решение |
|-------------|---------|
| **Два формата дат** в одном столбце | `03_extract_dates.py` парсит `%d.%m.%Y` и `ISO8601` |
| **ArrowString вместо str** | Скрипты принудительно преобразуют `df[col].astype(str)` |
| **Номера в разных столбцах** | Поиск идёт по всем: `Номер абонента`, `Номер контакта` |
| **LAC/CI в формате 12362-115902250** | `normalize.py` разбивает по дефису |
| **Адрес в одном столбце** | `Адрес БС` — единое имя после нормализации |

---

## 9. Типичные проблемы

| Проблема | Решение |
|----------|---------|
| `KeyError: 'Адрес БС абонента на начало'` | Использовать `Адрес БС` (нормализованное имя) |
| `❌ Номер не найден` | Проверить `print(df['Номер абонента'].unique()[:10])` |
| `ArrowString` | Добавить `df[col] = df[col].astype(str)` |
| `0 записей за дату` | Проверить `cat output/logs/03_extract.log` |

---

## 10. Завершение работы

```bash
deactivate
```

---

> **Инструкция завершена.** CAS v3.0 — полный цикл от нормализации до экспертного поиска.

