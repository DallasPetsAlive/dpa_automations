build:
	cd ./petfinder_sync && zip -r ../infrastructure/petfinder_sync.zip petfinder_sync.py constants.py __init__.py config.ini

build-layer:
	cd ./infrastructure/layer && pip install requests -t python && zip -r ../requests.zip python

plan:
	cd ./infrastructure && terraform plan

deploy:
	cd ./infrastructure && terraform apply

test:
	cd ./petfinder_sync && pytest --cov=. --cov-report=term-missing --omit="/tests/*"

lint:
	pre-commit run --all-files
