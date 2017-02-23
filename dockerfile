FROM ubuntu

# Install Python.
RUN \
  apt-get update && \
  apt-get install -y python python-dev python-pip && \
  rm -rf /var/lib/apt/lists/*

RUN apt-get update

COPY requirements.txt /app-container/requirements.txt

WORKDIR app-container/

RUN pip install -r requirements.txt

RUN python -m nltk.downloader "averaged_perceptron_tagger"; python
RUN python -m nltk.downloader "punkt"; python
RUN python -m nltk.downloader "stopwords"; python
RUN python -m nltk.downloader "wordnet"; python

ADD . /app-container