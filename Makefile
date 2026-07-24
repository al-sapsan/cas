.PHONY: all normalize import validate extract merge verify test clean

# Полный цикл: нормализация + обработка
all: normalize import validate extract merge

# Нормализация исходных файлов (input/billing → input/normalized)
normalize:
	python scripts/normalize.py

# Импорт нормализованных файлов + SHA-256
import:
	python scripts/01_import.py

# Валидация + нормализация типов
validate:
	python scripts/02_validate.py

# Фильтрация по датам и времени
extract:
	python scripts/03_extract_dates.py

# Сопоставление с БС по адресу
merge:
	python scripts/04_merge_bs.py

# Верификация: оригинал ↔ нормализация ↔ extracted
verify:
	python scripts/verify.py

# Тесты
test:
	pytest tests/ -v

# Очистка результатов
clean:
	rm -rf output/tables/* output/logs/* output/maps/* output/reports/*
	rm -f output/manifests/*

# Заморозить версии библиотек
freeze:
	pip freeze > requirements.txt
