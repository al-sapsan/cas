"""
Поиск по заданным параметрам экспертизы
Номера, дата, временные интервалы, адрес БС
"""
import pandas as pd

df = pd.read_parquet('output/tables/billing_extracted.parquet')

# ===== ПАРАМЕТРЫ ПОИСКА =====
TARGET_DATE = "10.02.2020"
TIME_PERIODS = [
    ("12:14:22", "12:14:52"),
    ("12:16:42", "12:16:42"),
    ("12:18:29", "13:00:00"),
]
TARGET_PHONES = ["79186633236", "79184610186"]
TARGET_ADDRESS = "ул. Красноармейская"  # часть адреса БС
# ============================

# Объединить даты из двух столбцов
df["_dt"] = pd.NaT
if "Время начала соединения" in df.columns:
    df["_dt"] = df["_dt"].fillna(pd.to_datetime(df["Время начала соединения"], format="%d.%m.%Y %H:%M:%S", errors="coerce"))
if "Дата и время" in df.columns:
    df["_dt"] = df["_dt"].fillna(pd.to_datetime(df["Дата и время"], format="ISO8601", errors="coerce"))

target_dt = pd.to_datetime(TARGET_DATE, format="%d.%m.%Y")

print("=" * 70)
print(f"ПОИСК: {TARGET_DATE}, адрес БС: {TARGET_ADDRESS}")
print(f"Номера: {TARGET_PHONES}")
print("=" * 70)

for phone in TARGET_PHONES:
    print(f"\n{'─' * 50}")
    print(f"📱 Абонент: {phone}")
    print(f"{'─' * 50}")
    
    # Найти столбец с номером
    phone_col = None
    for col in ["Номер абонента", "Номер А"]:
        if col in df.columns:
            phone_col = col
            break
    
    if not phone_col:
        print("  ❌ Столбец с номером не найден")
        continue
    
    # Фильтр по номеру
    phone_mask = df[phone_col].astype(str).str.contains(phone, na=False)
    phone_df = df[phone_mask].copy()
    print(f"  Всего записей по номеру: {len(phone_df)}")
    
    # Фильтр по дате
    date_mask = phone_df["_dt"].dt.date == target_dt.date()
    date_df = phone_df[date_mask].copy()
    print(f"  За {TARGET_DATE}: {len(date_df)}")
    
    # Фильтр по адресу БС
    addr_mask = date_df["Адрес БС"].astype(str).str.lower().str.contains(TARGET_ADDRESS.lower(), na=False)
    addr_df = date_df[addr_mask].copy()
    print(f"  С адресом БС '{TARGET_ADDRESS}': {len(addr_df)}")
    
    if len(addr_df) == 0:
        print(f"  ❌ НЕТ записей с указанным адресом БС")
        continue
    
    # Фильтр по временным интервалам
    print(f"\n  Анализ по временным интервалам:")
    
    all_results = []
    for t_from_str, t_to_str in TIME_PERIODS:
        t_from = pd.to_datetime(t_from_str, format="%H:%M:%S").time()
        t_to = pd.to_datetime(t_to_str, format="%H:%M:%S").time()
        
        if t_from == t_to:
            # Точное время
            mask = addr_df["_dt"].dt.time == t_from
            label = f"точно в {t_from_str}"
        else:
            # Интервал
            mask = (addr_df["_dt"].dt.time >= t_from) & (addr_df["_dt"].dt.time <= t_to)
            label = f"{t_from_str} – {t_to_str}"
        
        period_df = addr_df[mask]
        all_results.append(period_df)
        
        if len(period_df) > 0:
            print(f"    ✅ {label}: {len(period_df)} соединений")
            for _, row in period_df.iterrows():
                print(f"       {row['_dt']} | {row.get('Номер контакта', '—')} | {row.get('Тип соединения', '—')} | {row.get('Длительность, сек', row.get('Продолжительность (сек.)', '—'))}с")
        else:
            print(f"    ❌ {label}: 0 соединений")
    
    # Сохранить все найденные записи
    if all_results:
        combined = pd.concat(all_results).drop_duplicates()
        combined = combined.sort_values("_dt")
        filename = f"output/tables/экспертиза_{phone}_{TARGET_DATE.replace('.', '')}.xlsx"
        combined.to_excel(filename, index=False)
        print(f"\n  ✅ Сохранено {len(combined)} записей → {filename}")

print(f"\n{'=' * 70}")
print("ПОИСК ЗАВЕРШЁН")
print(f"{'=' * 70}")

