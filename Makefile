.PHONY: test
test: requirements
	nosetests --py3where web
	pylint --load-plugins pylint_flask web --reports n

.PHONY: requirements
requirements:
	pip install -r requirements.txt
	pip install -r web/requirements.txt
	pip install -r web/realtime_updater/requirements.txt
