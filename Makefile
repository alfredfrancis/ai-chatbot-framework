setup: venv/bin/activate

venv/bin/activate: requirements.txt
	test -d venv || virtualenv venv
	. venv/bin/activate; pip install -Ur requirements.txt

restore_db: 
	mongorestore --drop --db=iky-ai --dir=dump/iky-ai/

init: restore_db setup
	. venv/bin/activate && python setup.py

run_dev: 
	. venv/bin/activate && python run.py

run_prod: 
	. venv/bin/activate && APPLICATION_ENV="Production" gunicorn -k gevent --bind 0.0.0.0:8001 run:app

clean:
	rm -rf venv
	find -iname "*.pyc" -delete