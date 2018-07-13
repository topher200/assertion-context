.PHONY: deploy-k8s
deploy-k8s: push-to-docker deploy-current-version

VERSION := $(shell cat web/version)
.PHONY: bump-web-patch-version
bump-web-patch-version:
	bumpversion --current-version $(VERSION) patch web/VERSION
	git commit -m 'version bump' -o web/VERSION

.PHONY: bump-and-deploy
bump-and-deploy: bump-web-patch-version deploy-k8s

.PHONY: install
install:
	pip install -r requirements.txt
	pip install -r web/requirements.txt

.PHONY: test
test: install
	nosetests --py3where web
	pylint --load-plugins pylint_flask web --reports n

.PHONY: fresh-deploy-to-kubernetes
fresh-deploy-to-k8s: cleanup-kubernetes
	kubectl create secret generic papertrail-destination     --from-env-file .env.papertrail
	kubectl create -f 'https://help.papertrailapp.com/assets/files/papertrail-logspout-daemonset.yml'
	kubectl create configmap      assertion-context-env-file --from-env-file .env
	kubectl create -f kubernetes/
	helm init --wait
	helm install stable/redis                --name redis                --set usePassword=false                   --set master.persistence.size=80Gi
	helm install stable/kubernetes-dashboard --name kubernetes-dashboard --set rbac.clusterAdminRole=true
	helm install stable/heapster             --name heapster
	helm install incubator/jaeger            --name jaeger               --set provisionDataStore.cassandra=false  --set provisionDataStore.elasticsearch=true --namespace jaeger-infra --set query.service.type=NodePort --set storage.type=elasticsearch
	$(MAKE) deploy-current-version

.PHONY: cleanup-kubernetes
cleanup-kubernetes:
	helm ls --short | xargs helm delete --purge
	-helm reset
	-kubectl delete -f kubernetes-elasticsearch/
	-kubectl delete -f kubernetes/
	-kubectl delete configmap assertion-context-env-file
	-kubectl delete -f 'https://help.papertrailapp.com/assets/files/papertrail-logspout-daemonset.yml'
	-kubectl delete secret papertrail-destination

.PHONY: deploy-current-version
deploy-current-version:
	cat nginx/VERSION | tr -d '\n' | xargs -I {} kubectl set image deploy nginx  nginx=topher200/assertion-context-nginx:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} kubectl set image deploy web    web=topher200/assertion-context:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} kubectl set image deploy celery celery=topher200/assertion-context:{}

.PHONY: push-to-docker
push-to-docker:
	cat nginx/VERSION | tr -d '\n' | xargs -I {} docker build nginx/ --tag topher200/assertion-context-nginx:{}
	cat nginx/VERSION | tr -d '\n' | xargs -I {} docker push               topher200/assertion-context-nginx:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} docker build web/   --tag topher200/assertion-context:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} docker push               topher200/assertion-context:{}
