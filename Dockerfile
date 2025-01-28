FROM --platform=linux/x86_64 python:3.12.7-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 80

CMD ["fastapi", "run" ,"--host", "0.0.0.0","--port", "80" ]