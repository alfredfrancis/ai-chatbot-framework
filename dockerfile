FROM python:2

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN python manage.py install_nltk_dependencies

EXPOSE 8080

COPY . .

CMD ["make","run_docker"]