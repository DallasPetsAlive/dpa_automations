build:
	cd ./gsheet_to_mailchimp_volunteers && zip -r ../infrastructure/gsheet_to_mailchimp_volunteers.zip gsheet_to_mailchimp_volunteers.py service_account.json
	cd ./infrastructure && zip -r ../infrastructure/gsheet_to_mailchimp_volunteers.zip config.ini

build-layer:
	pip install . -t infrastructure/layer/python && zip -r infrastructure/layer.zip infrastructure/layer/python

plan:
	cd ./infrastructure && terraform plan

deploy:
	cd ./infrastructure && terraform apply

test:
	cd ../ && pytest --cov=. --cov-report=term-missing -k gsheet_to_mailchimp_volunteers

lint:
	pre-commit run --all-files
