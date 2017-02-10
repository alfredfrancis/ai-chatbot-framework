FROM ubuntu

# Install Python.
RUN \
  apt-get update && \
  apt-get install -y python python-dev python-pip && \
  rm -rf /var/lib/apt/lists/*

RUN apt-get update

RUN apt-get install -y gunicorn

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

RUN python -m nltk.downloader "averaged_perceptron_tagger"; python
RUN python -m nltk.downloader "punkt"; python

WORKDIR app-container/

EXPOSE 8080

ENTRYPOINT ["gunicorn","--bind", "0.0.0.0:8080", "run:app"]
