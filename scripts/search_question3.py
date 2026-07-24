import pandas as pd

df = pd.read_parquet('output/tables/billing_extracted.parquet')

# Принудительно преобразовать ArrowString в обычные строки
for col in df.columns:
    if df[col].dtype == 'string[pyarrow]' or 'arrow' in str(df[col].dtype):
        df[col] = df[col].astype(str)

TARGET_DATE = "24.04.2020"
TIME_FROM = "14:50:00"
TIME_TO = "17:30:00"
TARGET_PHONES = ["79181115519", "79184610186"]
TARGET_ADDRESS = "Красноармейск"

df["_dt"] = pd.NaT
df["_dt"] = pd.to_datetime(df["Дата и время"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
iso_dt = pd.to_datetime(df["Дата и время"], format="ISO8601", errors="coerce")
df["_dt"] = df["_dt"].fillna(iso_dt)

target_dt = pd.to_datetime(TARGET_DATE, format="%d.%m.%Y")
t_from = pd.to_datetime(TIME_FROM, format="%H:%M:%S").time()
t_to = pd.to_datetime(TIME_TO, format="%H:%M:%S").time()

print("=" * 70)
print(f"ПОИСК: {TARGET_DATE} {TIME_FROM}–{TIME_TO} | Адрес: {TARGET_ADDRESS}")
print("=" * 70)

all_combined = []

for phone in TARGET_PHONES:
    print(f"\n📱 {phone}")
    
    phone_mask = pd.Series(False, index=df.index)
    for col in df.columns:
        if df[col].dtype == 'object' or df[col].dtype == 'string':
            mask = df[col].astype(str).str.contains(phone, na=False)
            if mask.any():
                phone_mask |= mask
    
    if not phone_mask.any():
        print(f"  ❌ Номер не найден")
        continue
    
    phone_df = df[phone_mask].copy()
    print(f"  Всего: {len(phone_df)}")
    
    date_mask = phone_df["_dt"].dt.date == target_dt.date()
    date_df = phone_df[date_mask].copy()
    print(f"  За {TARGET_DATE}: {len(date_df)}")
    
    if len(date_df) == 0:
        continue
    
    time_mask = (date_df["_dt"].dt.time >= t_from) & (date_df["_dt"].dt.time <= t_to)
    time_df = date_df[time_mask].copy()
    print(f"  В {TIME_FROM}–{TIME_TO}: {len(time_df)}")
    
    if len(time_df) == 0:
        continue
    
    addr_mask = time_df["Адрес БС"].astype(str).str.contains(TARGET_ADDRESS, na=False)
    addr_df = time_df[addr_mask].copy()
    print(f"  С адресом: {len(addr_df)}")
    
    if len(addr_df) > 0:
        print(f"  ✅ НАЙДЕНО:")
        for _, row in addr_df.sort_values("_dt").iterrows():
            print(f"    {row['_dt']} | {row['Тип соединения']} | {row['Адрес БС'][:80]}")
        all_combined.append(addr_df)
    else:
        print(f"  ❌ Адрес не найден")
        addrs = time_df["Адрес БС"].dropna().unique()
        print(f"  Адреса в период ({len(addrs)}):")
        for a in addrs[:10]:
            print(f"    • {str(a)[:100]}")

if all_combined:
    result = pd.concat(all_combined).drop_duplicates().sort_values("_dt")
    fname = "output/tables/экспертиза_24.04.2020_Красноармейская.xlsx"
    result.to_excel(fname, index=False)
    print(f"\n✅ Сохранено {len(result)} записей → {fname}")
else:
    print(f"\n❌ Ни один номер не зафиксирован на указанной БС")
