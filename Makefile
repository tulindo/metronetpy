# Based on code from https://gitlab.com/keatontaylor/alexapy/blob/master/Makefile
coverage:
	Not implemented yet
	#py.test -s --verbose --cov-report term-missing --cov-report xml --cov=metronetpy tests
bump:
	semantic-release release
	semantic-release changelog
bump_and_publish:
	semantic-release publish
check_vulns:
	pipenv check
clean:
	rm -rf dist/ build/ .egg metronetpy.egg-info/
lint: flake8 docstyle pylint typing isort black
flake8:
	flake8 metronetpy metronet
docstyle:
	pydocstyle metronetpy metronet
pylint:
	pylint metronetpy metronet
isort:
	isort metronetpy/*py metronet
black:
	black metronetpy/*py metronet
typing:
	mypy --ignore-missing-imports metronetpy metronet
publish:
	python setup.py sdist bdist_wheel
	twine upload dist/*
	rm -rf dist/ build/ .egg metronetpy.egg-info/
test:
	#Not implemented yet
	#py.test

