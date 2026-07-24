# CAS — Cellular Analysis System

**Полная инструкция по поиску, фильтрации и сохранению данных**
**Версия:** 2.0 | **Дата:** 2026-07-24

---

## 1. Структура проекта

```
~/cas/
├── input/
│   ├── billing/              # Детализации МТС (.xlsb, .xlsx)
│   └── bs/                   # Справочники базовых станций (.xlsx)
├── output/
│   ├── manifests/            # SHA-256 контрольные суммы
│   ├── tables/               # Результаты (Excel, TSV, JSON, TXT, Parquet)
│   ├── maps/                 # Интерактивные карты (HTML)
│   ├── reports/              # PDF-отчёты
│   └── logs/                 # Журналы операций с row-count
├── config/
│   ├── config.yaml           # Даты, время, формат, временная зона
│   └── column_aliases.yaml   # Словарь синонимов столбцов
├── scripts/
│   ├── 01_import.py          # Загрузка + SHA-256 + все листы
│   ├── 02_validate.py        # Нормализация + Hex→Dec
│   ├── 03_extract_dates.py   # Фильтр по датам и времени
│   ├── 04_merge_bs.py        # Сопоставление с БС по адресу
│   ├── ai_formats.py         # Экспорт в AI-форматы
│   └── search_multi.py       # Массовый поиск и сохранение
├── cas-venv/                 # Виртуальное окружение
└── Makefile
```

---

## 2. Подготовка файлов

### 2.1 Принимаемые форматы

| Тип | Расширения | Куда класть |
|-----|:---------:|-------------|
| Детализации | `.xlsb`, `.xlsx` | `input/billing/` |
| Справочники БС | `.xlsx` | `input/bs/` |

### 2.2 Предварительный осмотр файла

```bash
cd ~/cas
source cas-venv/bin/activate

python << 'EOF'
import pandas as pd
fp = "input/billing/твой_файл.xlsb"
engine = "pyxlsb" if fp.endswith(".xlsb") else "openpyxl"
excel = pd.ExcelFile(fp, engine=engine)
print("Листы:", excel.sheet_names)
for sh in excel.sheet_names:
    df = pd.read_excel(excel, sheet_name=sh)
    print(f"\nЛист: {sh}")
    print(f"  Строк: {len(df)} | Столбцов: {len(df.columns)}")
    print(f"  Столбцы: {df.columns.tolist()}")
    print(f"  Примеры (первые 2):")
    print(df.head(2).to_string())
EOF
```

### 2.3 Проверка формата дат

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_raw.parquet')
for c in df.columns:
    if 'дат' in c.lower() or 'врем' in c.lower():
        print(f"\n{c}:")
        print(df[c].dropna().head(3).tolist())
EOF
```

### 2.4 Очистка проблемных файлов

- Удалить объединённые ячейки, скрытые столбцы, формулы
- Конвертировать `.xlsb` → `.xlsx`: открыть в Excel → «Сохранить как» → Excel Workbook

---

## 3. Настройка поиска

### 3.1 Даты и время (`config/config.yaml`)

```yaml
analysis:
  date_format: "%d.%m.%Y %H:%M:%S"   # Формат дат в детализациях
  date_errors: "raise"                # raise = строгий | coerce = пропускать ошибки
  default_timezone: "Europe/Moscow"
  
  target_dates:
    - date: "2020-02-10"
      time_from: "12:00"
      time_to: "13:00"
    - date: "2020-04-27"
      time_from: "17:25"
      time_to: "19:06"
```

**Соответствие формата дат:**

| Пример в файле | `date_format` |
|:--------------:|:-------------:|
| `10.02.2020 12:00:00` | `"%d.%m.%Y %H:%M:%S"` |
| `2020-04-27 17:25:00` | `"ISO8601"` |
| `02/10/2020 12:00` | `"%m/%d/%Y %H:%M"` |

### 3.2 Словарь столбцов (`config/column_aliases.yaml`)

Если скрипт пишет `WARNING: Не найдены столбцы: {'lac', 'ci'}` — добавить названия в словарь:

```yaml
lac:
  - "LAC"
  - "LAC идентификатор"   # ← добавить сюда новое название из файла
ci:
  - "CI"
  - "Идентификатор ячейки" # ← добавить сюда
```

---

## 4. Запуск обработки

```bash
cd ~/cas
source cas-venv/bin/activate

make all            # Полный цикл
make import         # Только загрузка
make validate       # Только нормализация
make extract        # Только фильтрация
make merge          # Только сопоставление
make clean          # Очистить результаты
```

### 4.1 Просмотр логов

```bash
cat output/logs/01_import.log    # Какие файлы, SHA-256, сколько строк
cat output/logs/03_extract.log   # Какие даты найдены
cat output/logs/04_merge.log     # Сколько сопоставлено, балансировка
```

---

## 5. Поиск данных

Все команды выполняются после `make all` в активном окружении.

### 5.1 Поиск по номеру телефона

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')
target = "79181115519"  # ← ЗАМЕНИ

for col in ["Номер абонента", "Номер А"]:
    if col in df.columns:
        mask = df[col].astype(str).str.contains(target, na=False)
        result = df[mask]
        if len(result) > 0:
            result.to_excel(f"output/tables/поиск_по_номеру_{target}.xlsx", index=False)
            result.to_csv(f"output/tables/поиск_по_номеру_{target}.tsv", sep="\t", index=False, encoding="utf-8")
            print(f"✅ {col}: {len(result)} записей → output/tables/поиск_по_номеру_{target}.xlsx")
EOF
```

**Варианты поиска по номеру:**

| Что ищем | Код |
|----------|-----|
| Точный номер | `df[col] == "79181115519"` |
| Содержит часть номера | `.str.contains("115519")` |
| Начинается с | `.str.startswith("7918")` |
| Несколько номеров | `.str.contains("79181115519\|79181115520")` |

### 5.2 Поиск по адресу БС

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')
target = "ул. Митрофана Седина"  # ← ЗАМЕНИ

safe = target.replace(" ", "_").replace(",", "").replace(".", "")[:50]
mask = df["Адрес БС абонента на начало"].astype(str).str.lower().str.contains(target.lower(), na=False)
result = df[mask]

result.to_excel(f"output/tables/поиск_по_адресу_{safe}.xlsx", index=False)
result.to_csv(f"output/tables/поиск_по_адресу_{safe}.tsv", sep="\t", index=False, encoding="utf-8")
print(f"✅ {len(result)} записей → output/tables/поиск_по_адресу_{safe}.xlsx")
EOF
```

**Варианты поиска по адресу:**

| Что ищем | Код |
|----------|-----|
| Точное совпадение | `df["Адрес БС абонента на начало"] == "Россия, ..."` |
| Содержит слово | `.str.contains("Красная", na=False)` |
| Начинается с | `.str.startswith("Россия")` |
| Несколько адресов | `.str.contains("Красная\|Седина")` |

### 5.3 Поиск по дате и времени

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')

target_date = "10.02.2020"  # ← ЗАМЕНИ
time_from = "12:00"          # ← ЗАМЕНИ
time_to = "13:00"            # ← ЗАМЕНИ

df["_dt"] = pd.NaT
if "Время начала соединения" in df.columns:
    df["_dt"] = df["_dt"].fillna(pd.to_datetime(df["Время начала соединения"], format="%d.%m.%Y %H:%M:%S", errors="coerce"))
if "Дата и время" in df.columns:
    df["_dt"] = df["_dt"].fillna(pd.to_datetime(df["Дата и время"], format="ISO8601", errors="coerce"))

target_dt = pd.to_datetime(target_date, format="%d.%m.%Y")
t_from = pd.to_datetime(time_from, format="%H:%M").time()
t_to = pd.to_datetime(time_to, format="%H:%M").time()

subset = df[df["_dt"].dt.date == target_dt.date()]
result = subset[(subset["_dt"].dt.time >= t_from) & (subset["_dt"].dt.time <= t_to)]

safe = f"{target_date}_{time_from.replace(':','')}_{time_to.replace(':','')}"
result.to_excel(f"output/tables/поиск_по_дате_{safe}.xlsx", index=False)
print(f"✅ {len(result)} записей → output/tables/поиск_по_дате_{safe}.xlsx")
EOF
```

### 5.4 Поиск по LAC

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')
target_lac = 12322  # ← ЗАМЕНИ

mp_col = None
for c in df.columns:
    if "М/П" in c or "м/п" in c:
        mp_col = c
        break

if mp_col:
    parts = df[mp_col].astype(str).str.split("/", expand=True)
    if parts.shape[1] == 4:
        df["_lac"] = pd.to_numeric(parts[2], errors="coerce")
    elif parts.shape[1] == 2:
        df["_lac"] = pd.to_numeric(parts[1], errors="coerce")

result = df[df["_lac"] == target_lac]
result.to_excel(f"output/tables/поиск_по_LAC{target_lac}.xlsx", index=False)
print(f"✅ LAC={target_lac}: {len(result)} записей")
EOF
```

### 5.5 Поиск по LAC + CI

```bash
python << 'EOF'
import pandas as pd
df = pd.read_parquet('output/tables/billing_extracted.parquet')
target_lac = 12322      # ← ЗАМЕНИ
target_ci = 116175413   # ← ЗАМЕНИ

mp_col = None
for c in df.columns:
    if "М/П" in c or "м/п" in c:
        mp_col = c
        break

if mp_col:
    parts = df[mp_col].astype(str).str.split("/", expand=True)
    if parts.shape[1] == 4:
        df["_lac"] = pd.to_numeric(parts[2], errors="coerce")
        df["_ci"] = pd.to_numeric(parts[3], errors="coerce")
    elif parts.shape[1] == 2:
        df["_lac"] = pd.to_numeric(parts[0], errors="coerce")
        df["_ci"] = pd.to_numeric(parts[1], errors="coerce")

result = df[(df["_lac"] == target_lac) & (df["_ci"] == target_ci)]
result.to_excel(f"output/tables/поиск_по_LAC{target_lac}_CI{target_ci}.xlsx", index=False)
print(f"✅ LAC={target_lac} CI={target_ci}: {len(result)} записей")
EOF
```

---

## 6. Массовый поиск (все запросы в одном скрипте)

### 6.1 Создание скрипта

```bash
cat > scripts/search_multi.py << 'PYEOF'
import pandas as pd

df = pd.read_parquet('output/tables/billing_extracted.parquet')

# Извлечь LAC/CI
mp_col = None
for c in df.columns:
    if "М/П" in c or "м/п" in c:
        mp_col = c
        break
if mp_col:
    parts = df[mp_col].astype(str).str.split("/", expand=True)
    if parts.shape[1] == 4:
        df["_lac"] = pd.to_numeric(parts[2], errors="coerce")
        df["_ci"] = pd.to_numeric(parts[3], errors="coerce")
    elif parts.shape[1] == 2:
        df["_lac"] = pd.to_numeric(parts[0], errors="coerce")
        df["_ci"] = pd.to_numeric(parts[1], errors="coerce")

# ========== ЗАДАНИЯ (редактируй здесь) ==========
searches = [
    {"name": "номер_79181115519", "type": "phone", "phone": "79181115519"},
    {"name": "номер_79186633236", "type": "phone", "phone": "79186633236"},
    {"name": "адрес_Седина", "type": "address", "address": "ул. Митрофана Седина"},
    {"name": "адрес_Красная", "type": "address", "address": "ул. Красная"},
    {"name": "LAC12322_CI116175413", "type": "lac_ci", "lac": 12322, "ci": 116175413},
    {"name": "LAC12362_CI115353651", "type": "lac_ci", "lac": 12362, "ci": 115353651},
]
# ================================================

for s in searches:
    if s["type"] == "phone":
        for col in ["Номер абонента", "Номер А"]:
            if col in df.columns:
                mask = df[col].astype(str).str.contains(s["phone"], na=False)
                result = df[mask]
                if len(result) > 0:
                    break
    elif s["type"] == "address":
        mask = df["Адрес БС абонента на начало"].astype(str).str.lower().str.contains(s["address"].lower(), na=False)
        result = df[mask]
    elif s["type"] == "lac_ci":
        result = df[(df["_lac"] == s["lac"]) & (df["_ci"] == s["ci"])]
    
    if len(result) > 0:
        result.to_excel(f"output/tables/поиск_{s['name']}.xlsx", index=False)
        result.to_csv(f"output/tables/поиск_{s['name']}.tsv", sep="\t", index=False, encoding="utf-8")
        print(f"✅ {s['name']}: {len(result)} записей")
    else:
        print(f"⚠️ {s['name']}: 0 записей")
PYEOF
```

### 6.2 Запуск

```bash
python scripts/search_multi.py
```

### 6.3 Как добавить свой запрос

Добавить блок в секцию `searches`:

```python
{"name": "моё_название", "type": "phone", "phone": "79181115519"},     # поиск по номеру
{"name": "моё_название", "type": "address", "address": "ул. Ленина"}, # поиск по адресу
{"name": "моё_название", "type": "lac_ci", "lac": 12322, "ci": 456},  # поиск по LAC+CI
```

---

## 7. Форматы сохранения

| Формат | Расширение | Для чего |
|--------|:----------:|----------|
| **Excel** | `.xlsx` | Для эксперта — просмотр, печать, приложение к заключению |
| **TSV** | `.tsv` | Для AI-анализа — табуляция, устойчив к запятым в адресах |
| **TXT** | `.txt` | Для промптов AI — выровненная таблица |
| **JSON** | `.json` | Для API и программной обработки |
| **Markdown** | `.md` | Для документирования |
| **Parquet** | `.parquet` | Промежуточное хранение — быстрое, строго типизированное |

Все файлы сохраняются в `output/tables/`.

---

## 8. Типичные проблемы

| Проблема | Причина | Решение |
|----------|---------|---------|
| `KeyError: 'lac'` | Столбцы названы иначе | Добавить в `column_aliases.yaml` |
| `Нет записей за дату` | Формат даты не совпадает | Проверить `date_format` |
| `calamine: листов не найдено` | Файл .xlsb не читается | Конвертировать в .xlsx через Excel |
| `Сопоставлено: 0%` | Адреса не совпадают | Проверить написание адресов |
| `ДИСБАЛАНС строк` | Потеря данных при merge | Прислать лог разработчику |

---

## 9. Завершение работы

```bash
deactivate
```

---

> **Инструкция завершена.** CAS v2.0 — полный цикл от загрузки до сохранения результатов поиска.
