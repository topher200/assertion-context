.PHONY: test
test: install
	nosetests --py3where web
	pylint --load-plugins pylint_flask web --reports n

.PHONY: install
install:
	pip install -r requirements.txt
	pip install -r web/requirements.txt

.PHONY: run-local
run-local: build-local stop
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up -d --remove-orphans
	docker-compose restart nginx

.PHONY: run-prod
run-prod: build-prod stop
	docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml up -d --remove-orphans
	docker-compose restart nginx

.PHONY: build-local
build-local:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml build

.PHONY: build-prod
build-prod:
	docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml build

.PHONY: stop
stop:
	docker-compose stop --timeout 120 celery
	docker-compose stop web

.PHONY: stop-all
stop-all:
	docker-compose stop --timeout 60

.PHONY: kill
kill:
	docker-compose stop --timeout 2 web celery

.PHONY: push-to-docker
push-to-docker:
	cat VERSION | tr -d '\n' | xargs -I {} docker build web/ --tag topher200/assertion-context:{}
	cat VERSION | tr -d '\n' | xargs -I {} docker push topher200/assertion-context:{}
