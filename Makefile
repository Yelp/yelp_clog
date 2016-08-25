.PHONY: all production docs test coverage clean

all: production

production:
	@true

tests: test

test:
	tox

coverage:
	tox -e cover

docs:
	echo $(PWD)
	tox -e docs

clean:
	make -C docs clean
	rm -rf build dist *.egg-info/ .tox
	find . -iname *.pyc -delete

flakes:
	pyflakes setup.py clog tests
