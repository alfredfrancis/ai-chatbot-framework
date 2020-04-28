release: APPLICATION_ENV="Heroku" python manage.py migrate
web: APPLICATION_ENV="Heroku" gunicorn -k gevent run:app
