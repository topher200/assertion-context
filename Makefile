.PHONY: deploy-k8s
deploy-k8s: push-to-docker
	cat nginx/VERSION | tr -d '\n' | xargs -I {} kubectl set image deploy nginx  nginx=topher200/assertion-context-nginx:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} kubectl set image deploy web    web=topher200/assertion-context:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} kubectl set image deploy celery celery=topher200/assertion-context:{}

VERSION := $(shell cat web/VERSION)
.PHONY: bump-web-patch-version
bump-web-patch-version:
	bumpversion --allow-dirty --current-version $(VERSION) patch web/VERSION
	git commit -m 'version bump' -o web/VERSION

.PHONY: bump-and-deploy
bump-and-deploy: bump-web-patch-version deploy-k8s

.PHONY: install
install:
	pip install -r requirements.txt --quiet
	pip install -r web/requirements.txt --quiet
	pip install -r src/badcorp/requirements.txt --quiet
	command -v papertrail || gem install papertrail-cli --user

.PHONY: test
test: install
	nosetests --py3where web --quiet
	mypy --config-file web/mypy.ini web/server.py
	pylint web --reports n
	nosetests --py3where src
	mypy --config-file src/mypy.ini src
	pylint src --reports n

.PHONY: fresh-deploy-to-kubernetes
fresh-deploy-to-k8s: cleanup-kubernetes
	kubectl create secret generic papertrail-destination     --from-env-file .env.papertrail
	kubectl create -f 'https://help.papertrailapp.com/assets/files/papertrail-logspout-daemonset.yml'
	kubectl create configmap      assertion-context-env-file --from-env-file .env
	kubectl create -f kubernetes/
	source .env && sed -e s@AWS_SSL_CERT@$AWS_SSL_CERT@ -e s@AWS_EXTRA_SECURITY_GROUP@$AWS_EXTRA_SECURITY_GROUP@ kubernetes/nginx-service.yaml | kubectl apply -f -

	echo install prometheus, from https://github.com/coreos/prometheus-operator/tree/master/contrib/kube-prometheus
	kubectl create -f prometheus-manifests/
	until kubectl get customresourcedefinitions servicemonitors.monitoring.coreos.com ; do date; sleep 1; echo ""; done
	until kubectl get servicemonitors --all-namespaces ; do date; sleep 1; echo ""; done
	kubectl create -f prometheus-manifests/

	echo install helm
	helm init --wait
	helm install stable/kubernetes-dashboard --namespace kube-system --name kubernetes-dashboard
	helm install stable/heapster             --namespace kube-system --name heapster

	$(MAKE) deploy-k8s

	echo install jaeger
	helm install incubator/jaeger --name jaeger --namespace jaeger-infra --set query.service.type=NodePort --set elasticsearch.rbac.create=true --set storage.type=elasticsearch --set elasticsearch.data.persistence.enabled=true --set provisionDataStore.elasticsearch=true --set provisionDataStore.cassandra=false

.PHONY: cleanup-kubernetes
cleanup-kubernetes:
	helm ls --short | xargs helm delete --purge
	helm reset
	kubectl delete -f prometheus-manifests/
	kubectl delete -f kubernetes/
	kubectl delete configmap assertion-context-env-file
	kubectl delete -f 'https://help.papertrailapp.com/assets/files/papertrail-logspout-daemonset.yml'
	kubectl delete secret papertrail-destination
	kubectl delete namespace default

.PHONY: push-to-docker
push-to-docker:
	cat nginx/VERSION | tr -d '\n' | xargs -I {} docker build nginx/ --tag topher200/assertion-context-nginx:{}
	cat nginx/VERSION | tr -d '\n' | xargs -I {} docker push               topher200/assertion-context-nginx:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} docker build web/   --tag topher200/assertion-context:{}
	cat web/VERSION   | tr -d '\n' | xargs -I {} docker push               topher200/assertion-context:{}

.PHONY: run-badcorp
run-badcorp:
	docker build . -f Dockerfile-badcorp -t badcorp
	docker run badcorp
