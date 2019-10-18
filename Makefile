.PHONY: install
install:
	pip install -r requirements.txt --quiet
	pip install -r src/requirements.txt --quiet
	command -v papertrail || sudo gem install papertrail

.PHONY: test
test: install
	dynaconf list -e testing | tail -n +2 | sed 's/: /=/' > .env
	./scripts/run-tests.sh --skip-integration-tests
	mypy --config-file src/mypy.ini src/server.py
	pylint src --reports n
	mypy --config-file src/mypy.ini src
	pylint src --reports n

.PHONY: push-to-docker
push-to-docker:
	cat nginx/VERSION | tr -d '\n' | xargs -I {} docker build nginx/ --tag topher200/assertion-context-nginx:{}
	cat nginx/VERSION | tr -d '\n' | xargs -I {} docker push               topher200/assertion-context-nginx:{}
	cat src/VERSION   | tr -d '\n' | xargs -I {} docker build src/   --tag topher200/assertion-context:{}
	cat src/VERSION   | tr -d '\n' | xargs -I {} docker push               topher200/assertion-context:{}

.PHONY: run-app-docker-compose
run-app-docker-compose:
	dynaconf list -e production | tail -n +2 | sed 's/: /=/' > .env
	docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml up --detach --remove-orphans

.PHONY: run-badcorp
run-badcorp:
	docker build . -f Dockerfile-badcorp -t badcorp
	docker run badcorp

.PHONY: integration-test
integration-test: install
	dynaconf list -e testing | tail -n +2 | sed 's/: /=/' > .env
	./scripts/setup-es-database.sh
	./scripts/run-tests.sh
