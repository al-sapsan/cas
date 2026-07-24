"""
Верификация данных на каждом этапе обработки.
Сравнивает:
  1. Оригинал ↔ Нормализованный (row-count, номера, адреса)
  2. Нормализованный ↔ billing_extracted (row-count, номера, адреса)
  3. Поиск в extracted ↔ Поиск в оригинале
"""
import pandas as pd
from pathlib import Path

CAS_DIR = Path(".")
ORIG_DIR = CAS_DIR / "input/billing"
NORM_DIR = CAS_DIR / "input/normalized"
EXTRACTED_FILE = CAS_DIR / "output/tables/billing_extracted.parquet"

# ===== ПАРАМЕТРЫ ПРОВЕРКИ =====
TARGET_PHONES = ["79184610186", "79186633236", "79181115519"]
TARGET_DATES = ["10.02.2020", "24.04.2020", "27.04.2020"]
TARGET_ADDRESS = "Красноармейск"
# ==============================

def find_date_cols(df):
    """Найти столбцы с датой/временем."""
    return [c for c in df.columns if 'дат' in c.lower() or 'врем' in c.lower()]

def parse_dates(series):
    """Парсить даты в двух форматах."""
    d1 = pd.to_datetime(series, format="%d.%m.%Y %H:%M:%S", errors="coerce")
    d2 = pd.to_datetime(series, format="ISO8601", errors="coerce")
    return d1.fillna(d2)

def count_phone(df, phone):
    """Посчитать записи с номером во всех столбцах."""
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        if df[col].dtype in ('object', 'str', 'string[pyarrow]'):
            mask |= df[col].astype(str).str.contains(phone, na=False)
    return mask.sum()

def count_address(df, address):
    """Посчитать записи с адресом во всех столбцах."""
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        if 'адрес' in col.lower() or 'address' in col.lower():
            mask |= df[col].astype(str).str.contains(address, na=False)
    return mask.sum()

def count_date(df, date_str):
    """Посчитать записи за дату."""
    target = pd.to_datetime(date_str, format="%d.%m.%Y").date()
    mask = pd.Series(False, index=df.index)
    for dc in find_date_cols(df):
        dates = parse_dates(df[dc])
        mask |= (dates.dt.date == target)
    return mask.sum()

def count_phone_date_address(df, phone, date_str, address):
    """Посчитать записи по трём критериям."""
    target = pd.to_datetime(date_str, format="%d.%m.%Y").date()
    
    # Маска номера
    phone_mask = pd.Series(False, index=df.index)
    for col in df.columns:
        if df[col].dtype in ('object', 'str', 'string[pyarrow]'):
            phone_mask |= df[col].astype(str).str.contains(phone, na=False)
    
    # Маска даты
    date_mask = pd.Series(False, index=df.index)
    for dc in find_date_cols(df):
        dates = parse_dates(df[dc])
        date_mask |= (dates.dt.date == target)
    
    # Маска адреса
    addr_mask = pd.Series(False, index=df.index)
    for col in df.columns:
        if 'адрес' in col.lower() or 'address' in col.lower():
            addr_mask |= df[col].astype(str).str.contains(address, na=False)
    
    return (phone_mask & date_mask & addr_mask).sum()

print("=" * 70)
print("ВЕРИФИКАЦИЯ ДАННЫХ CAS")
print("=" * 70)

# === Этап 1: Оригинал ↔ Нормализованный ===
print("\n" + "=" * 70)
print("ЭТАП 1: ОРИГИНАЛ ↔ НОРМАЛИЗОВАННЫЙ")
print("=" * 70)

for orig_file in sorted(ORIG_DIR.glob("*")):
    if orig_file.name.startswith("."):
        continue
    
    norm_file = NORM_DIR / f"{orig_file.stem}_normalized.xlsx"
    if not norm_file.exists():
        print(f"\n❌ {orig_file.name}: нормализованный файл не найден")
        continue
    
    engine = "pyxlsb" if orig_file.suffix == ".xlsb" else "openpyxl"
    df_orig = pd.read_excel(orig_file, engine=engine)
    df_norm = pd.read_excel(norm_file)
    
    print(f"\n📄 {orig_file.name}")
    print(f"   Строк: оригинал={len(df_orig)}, нормализованный={len(df_norm)}")
    
    if len(df_orig) == len(df_norm):
        print(f"   ✅ ROW-COUNT совпадает")
    else:
        print(f"   ❌ ROW-COUNT: разница {len(df_orig) - len(df_norm)}")
    
    for phone in TARGET_PHONES:
        c_orig = count_phone(df_orig, phone)
        c_norm = count_phone(df_norm, phone)
        status = "✅" if c_orig == c_norm else "❌"
        print(f"   {status} {phone}: оригинал={c_orig}, норма={c_norm}")
    
    c_orig = count_address(df_orig, TARGET_ADDRESS)
    c_norm = count_address(df_norm, TARGET_ADDRESS)
    status = "✅" if c_orig == c_norm else "❌"
    print(f"   {status} '{TARGET_ADDRESS}': оригинал={c_orig}, норма={c_norm}")

# === Этап 2: Нормализованный ↔ extracted ===
print("\n" + "=" * 70)
print("ЭТАП 2: НОРМАЛИЗОВАННЫЙ ↔ EXTRACTED")
print("=" * 70)

# Суммируем все нормализованные
dfs_norm = []
for f in sorted(NORM_DIR.glob("*_normalized.xlsx")):
    dfs_norm.append(pd.read_excel(f))
df_all_norm = pd.concat(dfs_norm, ignore_index=True)

df_ext = pd.read_parquet(EXTRACTED_FILE)
# Принудительно строки
for col in df_ext.columns:
    if 'arrow' in str(df_ext[col].dtype).lower():
        df_ext[col] = df_ext[col].astype(str)

print(f"\nСтрок: норма={len(df_all_norm)}, extracted={len(df_ext)}")

for phone in TARGET_PHONES:
    c_norm = count_phone(df_all_norm, phone)
    c_ext = count_phone(df_ext, phone)
    status = "✅" if c_norm > 0 and c_ext > 0 else "⚠️" if c_norm == 0 else "❌"
    print(f"   {status} {phone}: норма={c_norm}, extracted={c_ext}")

for date_str in TARGET_DATES:
    c_norm = count_date(df_all_norm, date_str)
    c_ext = count_date(df_ext, date_str)
    status = "✅" if c_norm > 0 and c_ext > 0 else "⚠️" if c_norm == 0 else "❌"
    print(f"   {status} {date_str}: норма={c_norm}, extracted={c_ext}")

c_norm = count_address(df_all_norm, TARGET_ADDRESS)
c_ext = count_address(df_ext, TARGET_ADDRESS)
status = "✅" if c_norm > 0 and c_ext > 0 else "⚠️" if c_norm == 0 else "❌"
print(f"   {status} '{TARGET_ADDRESS}': норма={c_norm}, extracted={c_ext}")

# === Этап 3: Перекрёстная проверка (оригинал ↔ extracted) ===
print("\n" + "=" * 70)
print("ЭТАП 3: ПЕРЕКРЁСТНАЯ ПРОВЕРКА")
print("=" * 70)

for orig_file in sorted(ORIG_DIR.glob("*")):
    if orig_file.name.startswith("."):
        continue
    
    engine = "pyxlsb" if orig_file.suffix == ".xlsb" else "openpyxl"
    df_orig = pd.read_excel(orig_file, engine=engine)
    
    print(f"\n📄 {orig_file.name}")
    
    for phone in TARGET_PHONES:
        for date_str in TARGET_DATES:
            c_orig = count_phone_date_address(df_orig, phone, date_str, TARGET_ADDRESS)
            c_ext = count_phone_date_address(df_ext, phone, date_str, TARGET_ADDRESS)
            
            if c_orig > 0 or c_ext > 0:
                status = "✅" if c_orig == c_ext else "❌"
                print(f"   {status} {phone} {date_str} '{TARGET_ADDRESS}': оригинал={c_orig}, extracted={c_ext}")

print("\n" + "=" * 70)
print("ВЕРИФИКАЦИЯ ЗАВЕРШЕНА")
print("=" * 70)
