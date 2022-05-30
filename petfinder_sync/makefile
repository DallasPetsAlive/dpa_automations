run:
	../venv/Scripts/python ./backend/run.py

build:
	cd ./backend && zip -r ../infrastructure/petfinder_sync.zip petfinder_sync.py

plan:
	cd ./infrastructure && terraform plan

deploy:
	cd ./infrastructure && terraform apply

test:
	cd ./backend/tests && pytest
