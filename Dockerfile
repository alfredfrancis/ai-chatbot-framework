FROM python:3.12-bullseye

WORKDIR /usr/src/app

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 80

CMD ["fastapi", "run" ,"--host", "0.0.0.0","--port", "80" ]