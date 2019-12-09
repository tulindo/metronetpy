# Based on code from https://gitlab.com/keatontaylor/alexapy/blob/master/Makefile
coverage:
	Not implemented yet
	#pipenv run py.test -s --verbose --cov-report term-missing --cov-report xml --cov=metronetpy tests
bump:
	pipenv run semantic-release release
	pipenv run semantic-release changelog
bump_and_publish:
	pipenv run semantic-release publish
check_vulns:
	pipenv check
clean:
	rm -rf dist/ build/ .egg metronetpy.egg-info/
init:
	pip3 install pip pipenv
	pipenv lock
	pipenv install --three --dev
lint: flake8 docstyle pylint typing
flake8:

	pipenv run flake8 metronetpy
docstyle:
	pipenv run pydocstyle metronetpy
pylint:
	pipenv run pylint metronetpy
publish:
	pipenv run python setup.py sdist bdist_wheel
	pipenv run twine upload dist/*
	rm -rf dist/ build/ .egg metronetpy.egg-info/
setup_env:
	pip3 install pip pipenv
	pipenv sync --three --dev
test:
	#Not implemented yet
	#pipenv run py.test
typing:
	pipenv run mypy --ignore-missing-imports metronetpy
