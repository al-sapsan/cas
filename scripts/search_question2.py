import pandas as pd

df = pd.read_parquet('output/tables/billing_extracted.parquet')

# ПРИНУДИТЕЛЬНОЕ преобразование ВСЕХ ArrowString в str
for col in df.columns:
    if 'arrow' in str(df[col].dtype).lower():
        df[col] = df[col].astype(str)

TARGET_DATE = "10.02.2020"
TARGET_PHONES = ["79186633236", "79184610186"]
TARGET_ADDRESS = "Красноармейск"

df["_dt"] = pd.NaT
df["_dt"] = pd.to_datetime(df["Дата и время"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
df["_dt"] = df["_dt"].fillna(pd.to_datetime(df["Дата и время"], format="ISO8601", errors="coerce"))

target_dt = pd.to_datetime(TARGET_DATE, format="%d.%m.%Y")

print("=" * 70)
print(f"ПОИСК: {TARGET_DATE}, адрес БС: {TARGET_ADDRESS}")
print(f"Номера: {TARGET_PHONES}")
print("=" * 70)

all_combined = []

for phone in TARGET_PHONES:
    print(f"\n📱 {phone}")
    
    # Искать ВО ВСЕХ столбцах
    phone_mask = pd.Series(False, index=df.index)
    for col in df.columns:
        if df[col].dtype == 'object' or df[col].dtype == 'str':
            mask = df[col].astype(str).str.contains(phone, na=False)
            if mask.any():
                phone_mask |= mask
    
    if not phone_mask.any():
        print("  ❌ Номер не найден ни в одном столбце")
        continue
    
    phone_df = df[phone_mask].copy()
    print(f"  Всего: {len(phone_df)}")
    
    date_mask = phone_df["_dt"].dt.date == target_dt.date()
    date_df = phone_df[date_mask].copy()
    print(f"  За {TARGET_DATE}: {len(date_df)}")
    
    if len(date_df) == 0:
        print(f"  ❌ Нет записей за {TARGET_DATE}")
        continue
    
    addr_mask = date_df["Адрес БС"].astype(str).str.contains(TARGET_ADDRESS, na=False)
    addr_df = date_df[addr_mask].copy()
    print(f"  С адресом: {len(addr_df)}")
    
    if len(addr_df) > 0:
        print(f"  ✅ НАЙДЕНО:")
        for _, row in addr_df.sort_values("_dt").iterrows():
            print(f"    {row['_dt']} | {row['Тип соединения']} | {row['Адрес БС'][:80]}")
        all_combined.append(addr_df)
    else:
        print(f"  ❌ Адрес не найден")
        addrs = date_df["Адрес БС"].dropna().unique()
        print(f"  Адреса за {TARGET_DATE} ({len(addrs)}):")
        for a in addrs[:10]:
            print(f"    • {str(a)[:100]}")

if all_combined:
    result = pd.concat(all_combined).drop_duplicates().sort_values("_dt")
    fname = "output/tables/экспертиза_10.02.2020_Красноармейская.xlsx"
    result.to_excel(fname, index=False)
    print(f"\n✅ Сохранено {len(result)} записей → {fname}")
else:
    print(f"\n❌ Ни один номер не зафиксирован на указанной БС")
