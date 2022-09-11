build:
	cd ./new_digs_to_rescue_groups && zip -r ../infrastructure/new_digs_to_rescue_groups.zip new_digs_to_rescue_groups.py
	cd ./infrastructure && zip -r ../infrastructure/new_digs_to_rescue_groups.zip config.ini

build-layer:
	pip install . -t infrastructure/layer/python && zip -r infrastructure/layer.zip infrastructure/layer/python

plan:
	cd ./infrastructure && terraform plan

deploy:
	cd ./infrastructure && terraform apply

test:
	cd ../ && pytest --cov=. --cov-report=term-missing -k new_digs_to_rescue_groups

lint:
	pre-commit run --all-files
