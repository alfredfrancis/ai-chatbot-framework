setup:
	test -d venv || virtualenv -p python3 venv
	. venv/bin/activate; pip install -Ur requirements.txt
	. venv/bin/activate; python -m spacy download en_core_web_md && python -m spacy link en_core_web_md en

migrate:
	. venv/bin/activate; python manage.py migrate

run_dev: 
	. venv/bin/activate && python run.py

run_prod: 
	. venv/bin/activate && APPLICATION_ENV="Production" gunicorn -k gevent --bind 0.0.0.0:8080 run:app

run_docker:
	gunicorn run:app --bind 0.0.0.0:8080 --access-logfile=logs/gunicorn-access.log --error-logfile logs/gunicorn-error.log

clean:
	rm -rf venv
	find -iname "*.pyc" -delete
