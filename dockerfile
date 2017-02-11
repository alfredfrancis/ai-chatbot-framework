FROM ubuntu

# Install Python.
RUN \
  apt-get update && \
  apt-get install -y python python-dev python-pip && \
  rm -rf /var/lib/apt/lists/*

RUN apt-get update

RUN apt-get install -y gunicorn

ADD . /app-container

WORKDIR app-container/

RUN pip install -r requirements.txt

RUN python -m nltk.downloader "averaged_perceptron_tagger"; python
RUN python -m nltk.downloader "punkt"; python
RUN python -m nltk.downloader "stopwords"; python
RUN python -m nltk.downloader "wordnet"; python