FROM python:3.6-slim

# Install common libraries
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends build-essential && apt-get autoremove -y

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download en; python

EXPOSE 8080

COPY . .

CMD ["make","run_docker"]