FROM python:2

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m nltk.downloader "averaged_perceptron_tagger"; python
RUN python -m nltk.downloader "punkt"; python
RUN python -m nltk.downloader "stopwords"; python
RUN python -m nltk.downloader "wordnet"; python

EXPOSE 8080

COPY . .

# CMD  ["gunicorn", "run:app" ,"--bind", "0.0.0.0:8001", ""--access-logfile=logs/gunicorn-access.log", ""--error-logfile", "logs/gunicorn-error.log"]
CMD ["make","run_docker"]