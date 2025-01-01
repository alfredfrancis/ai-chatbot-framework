release: APPLICATION_ENV="Heroku" flask --app=manage  manage  migrate
web: APPLICATION_ENV="Heroku" gunicorn -k gevent run:app
