setup: venv/bin/activate

venv/bin/activate: requirements.txt
	test -d venv || virtualenv venv
	. venv/bin/activate; pip install -Ur requirements.txt
	. venv/bin/activate; python manage.py install_nltk_dependencies

restore_db: 
	mongorestore --drop --db=iky-ai --dir=dump/iky-ai/

init: restore_db setup
	. venv/bin/activate && python setup.py

run_dev: 
	. venv/bin/activate && python run.py

run_prod: 
	. venv/bin/activate && APPLICATION_ENV="Production" gunicorn -k gevent --bind 0.0.0.0:8080 run:app

run_docker:
	gunicorn run:app --bind 0.0.0.0:8080 --access-logfile=logs/gunicorn-access.log --error-logfile logs/gunicorn-error.log

clean:
	rm -rf venv
	find -iname "*.pyc" -delete