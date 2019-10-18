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

.PHONY: run-badcorp
run-badcorp:
	docker build . -f Dockerfile-badcorp -t badcorp
	docker run badcorp

.PHONY: integration-test
integration-test: install
	dynaconf list -e testing | tail -n +2 | sed 's/: /=/' > .env
	./scripts/setup-es-database.sh
	./scripts/run-tests.sh

.PHONY: install-docker-dependencies-on-amazon-linux
install-docker-dependencies-on-amazon-linux:
	sudo yum install -y docker
	sudo curl -L "https://github.com/docker/compose/releases/download/1.24.1/docker-compose-$$(uname -s)-$$(uname -m)" -o /usr/local/bin/docker-compose
	sudo chmod +x /usr/local/bin/docker-compose
