FROM python:3.9.6-slim

# Install common libraries
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends build-essential && apt-get autoremove -y

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

COPY . .

CMD ["gunicorn", "run:app" ,"--log-level=debug", "--timeout", "90","--bind", "0.0.0.0:80" ]
