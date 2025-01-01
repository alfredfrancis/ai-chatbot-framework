<img src="https://i.ibb.co/vLR1wpG/logo.png" width="280"/>

[![Join the chat at https://gitter.im/ai-chatbot-framework/Lobby](https://badges.gitter.im/ai-chatbot-framework/Lobby.svg)](https://gitter.im/ai-chatbot-framework/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) [![Build Status](https://github.com/alfredfrancis/ai-chatbot-framework/actions/workflows/docker-build-push.yml/badge.svg)](https://github.com/alfredfrancis/ai-chatbot-framework/actions/workflows/docker-build-push.yml)



### An AI Chatbot framework built in Python

AI Chatbot Framework is an AI powered conversational dialog interface built in Python. With this tool, it’s easy to create Natural Language conversational scenarios with no coding efforts whatsoever. The smooth UI makes it effortless to create and train conversations to the bot. AI Chatbot Framework can live on any channel of your choice (such as Messenger, Slack etc.) by integrating it’s API with that platform.

You don’t need to be an expert at artificial intelligence to create an awesome chatbot that has AI capabilities. With this boilerplate project you can create an AI powered chatting machine in no time. Since this is a hobby project, there could be numerous bugs, so contributions through pull requests are welcome!

![](https://image.ibb.co/eMJ9Wx/Screen_Shot_2018_04_28_at_1_45_28_PM.png)

[//]: # (add an index)

## Index

* [Installation](#installation)
  * [Docker Compose](#using-docker-compose)
  * [Helm](#using-helm)
  * [Docker](#using-docker)
  * [Without Docker](#without-docker)
  * [Updating Frontend](#update-frontend-dist)
  * [Heroku](#heroku)
* [Development](#development)
* [Screenshots](#screenshots)
* [Tutorial](#tutorial)
* [Dependencies](#dependencies-documentations)

### Installation

### Using docker-compose (recommended)
```sh
docker-compose up -d
```

Open http://localhost:8080/

### Using Helm

```sh
helm dep update helm/ai-chatbot-framework

helm upgrade --install --create-namespace -n ai-chatbot-framework ai-chatbot-framework helm/ai-chatbot-framework

# port forward to local (optional)
kubectl port-forward --namespace=ai-chatbot-framework service/ingress-nginx-controller 8080:80
```

Open http://localhost:8080/

### Using Docker

```sh
# pull docker images
docker pull alfredfrancis/ai-chatbot-framework:latest

# start a mongodb server
docker run --name mongodb -d mongo:3.6

# start the container
docker run -d --name=ai-chatbot-framework --link mongodb:mongodb -e="APPLICATION_ENV=Production" alfredfrancis/ai-chatbot-framework:latest

# setup default intents
docker exec -it ai-chatbot-framework flask --app=manage  manage  migrate 
```

Open http://localhost/

### without docker

* Setup Virtualenv and install python requirements
```sh
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt
flask --app=manage  manage  migrate 
flask run --host=127.0.0.1 --debug --port=8080
```
* Production
```sh
APPLICATION_ENV="Production" gunicorn --bind 0.0.0.0:8080 run:app
```
* Open http://localhost:8080/

### Heroku
[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy)

* add your dev/production configurations in config.py

## Development

### Start development server

```sh
docker-compose -f docker-compose.dev.yml up -d
```
Open http://localhost:8080/

### Update Frontend Dist
* Run Development mode
```sh
cd frontend
npm install
ng serve
```
* Update Production build
```sh
cd frontend
ng build --prod --optimize
cp dist/ ../app/static/
```

### Screenshots

![](https://image.ibb.co/i9ReWx/Screen_Shot_2018_04_28_at_1_38_15_PM.png)
---
![](https://image.ibb.co/ivXKWx/Screen_Shot_2018_04_28_at_1_38_36_PM.png)
---
![](https://image.ibb.co/nf9Bdc/Screen_Shot_2018_04_28_at_1_38_57_PM.png)
---
![](https://image.ibb.co/b4q1dc/Screen_Shot_2018_04_28_at_1_43_06_PM.png)

### Tutorial

Checkout this basic tutorial on youtube,

[![Coming Soon](https://www.wpcc.edu/wp-content/uploads/2021/04/YouTube-Stream-Coming-Soon.jpg)](https://www.youtube.com/watch?v=S1Fj7WinaBA)

<hr></hr>
