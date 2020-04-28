FROM python:3.6-slim

# Install common libraries
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends \
    # required by psycopg2 at build and runtime
    libpq-dev \
 && apt-get autoremove -y

# Install all required build libraries
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends \
    build-essential

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download en; python

EXPOSE 8080

COPY . .

CMD ["make","run_docker"]