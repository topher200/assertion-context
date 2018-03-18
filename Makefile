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
	cat nginx/VERSION | tr -d '\n' | xargs -I {} docker build nginx/ --tag topher200/assertion-context-nginx:{}
	cat nginx/VERSION | tr -d '\n' | xargs -I {} docker push               topher200/assertion-context-nginx:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} docker build web/   --tag topher200/assertion-context:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} docker push               topher200/assertion-context:{}

.PHONY: deploy-latest-version
deploy-latest-version:
	cat nginx/VERSION | tr -d '\n' | xargs -I {} kubectl set image deploy nginx  nginx=topher200/assertion-context-nginx:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} kubectl set image deploy web    web=topher200/assertion-context:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} kubectl set image deploy celery celery=topher200/assertion-context:{}

.PHONY: fresh-deploy-to-kubernetes
fresh-deploy-to-k8s: cleanup-kubernetes
	kubectl create configmap assertion-context-env-file --from-env-file .env
	kubectl create configmap assertion-context-env-file --from-env-file .env.kube-system --namespace kube-system
	kubectl create -f kubernetes/
	$(MAKE) deploy-latest-version

.PHONY: cleanup-kubernetes
cleanup-kubernetes:
	kubectl delete all --all
	kubectl delete configmap --all
	kubectl delete configmap --all --namespace kube-system
	kubectl delete daemonset --all --namespace kube-system
	kubectl delete role --all
	kubectl delete rolebinding --all
	kubectl delete serviceaccount --all
