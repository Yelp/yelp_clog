.PHONY: all production docs test coverage clean

all: production

production:
	  @true

tests: test

test:
	  tox2

coverage:
	  tox2 -e cover

docs:
	echo $(PWD)
	tox2 -e docs

clean:
	make -C docs clean
	rm -rf build dist *.egg-info/ .tox
	find . -iname *.pyc -delete

flakes:
	pyflakes setup.py clog tests
