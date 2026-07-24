.PHONY: all import validate extract merge test clean

all: import validate extract merge

import:
	python scripts/01_import.py

validate:
	python scripts/02_validate.py

extract:
	python scripts/03_extract_dates.py

merge:
	python scripts/04_merge_bs.py

test:
	pytest tests/ -v

clean:
	rm -rf output/tables/* output/logs/* output/maps/* output/reports/*

freeze:
	pip freeze > requirements.txt
