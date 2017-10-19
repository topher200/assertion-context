.PHONY: test
test: requirements
	nosetests --py3where web
	pylint --load-plugins pylint_flask web --reports n

.PHONY: requirements
requirements:
	pip install -r requirements.txt
	pip install -r web/requirements.txt
	pip install -r web/realtime_updater/requirements.txt

.PHONY: run-local
run-local: build-local stop
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up -d
	docker-compose restart nginx

.PHONY: run-prod
run-prod: build-prod stop
	docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml up -d
	docker-compose restart nginx

.PHONY: build-local
build-local:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml build

.PHONY: build-prod
build-prod:
	docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml build

.PHONY: stop
stop:
	docker-compose kill realtime_updater
	docker-compose stop web celery
