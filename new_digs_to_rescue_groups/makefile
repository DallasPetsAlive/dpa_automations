build:
	cd ./new_digs_to_rescue_groups && zip -r ../infrastructure/new_digs_to_rescue_groups.zip new_digs_to_rescue_groups.py config.ini

build-layer:
	cd ./infrastructure/layer && pip install requests -t python && zip -r ../requests.zip python

plan:
	cd ./infrastructure && terraform plan

deploy:
	cd ./infrastructure && terraform apply

test:
	cd ../ && pytest --cov=. --cov-report=term-missing -k new_digs_to_rescue_groups

lint:
	pre-commit run --all-files
