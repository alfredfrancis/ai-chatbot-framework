<img src="https://i.ibb.co/vLR1wpG/logo.png" width="280"/>

[![Join the chat at https://gitter.im/ai-chatbot-framework/Lobby](https://badges.gitter.im/ai-chatbot-framework/Lobby.svg)](https://gitter.im/ai-chatbot-framework/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) [![Build Status](https://github.com/alfredfrancis/ai-chatbot-framework/actions/workflows/docker-build-push.yml/badge.svg)](https://github.com/alfredfrancis/ai-chatbot-framework/actions/workflows/docker-build-push.yml)



### An AI Chatbot framework built in Python

AI Chatbot Framework is an AI powered conversational dialog interface built in Python. With this tool, it’s easy to create Natural Language conversational scenarios with no coding efforts whatsoever. The smooth UI makes it effortless to create and train conversations to the bot. AI Chatbot Framework can live on any channel of your choice (such as Messenger, Slack etc.) by integrating it’s API with that platform.

You don’t need to be an expert at artificial intelligence to create an awesome chatbot that has AI capabilities. With this boilerplate project you can create an AI powered chatting machine in no time. Since this is a hobby project, there could be numerous bugs, so contributions through pull requests are welcome!

![](docs/screenshots/admin_chat_screenshot.png)

## Index

* [Installation](#installation)
  * [Docker Compose](#using-docker-compose)
  * [Helm](#using-helm)
* [Development](#development)
* [Tutorial](#tutorial)
* [Dependencies](#dependencies-documentations)

### Installation

### Using docker-compose (recommended)
```sh
docker-compose up -d
```

Open http://localhost:3000/

### Using Helm

```sh
helm dep update helm/ai-chatbot-framework

helm upgrade --install --create-namespace -n ai-chatbot-framework ai-chatbot-framework helm/ai-chatbot-framework

# port forward to local (optional)
kubectl port-forward --namespace=ai-chatbot-framework service/ingress-nginx-controller 8080:80
```

Open http://localhost:8080/

## Development

### Start development server

```sh
docker-compose -f docker-compose.dev.yml up -d
```
Open http://localhost:3000/

### Tutorial

Checkout this basic tutorial on youtube,

[![Coming Soon](https://www.wpcc.edu/wp-content/uploads/2021/04/YouTube-Stream-Coming-Soon.jpg)](https://www.youtube.com/watch?v=S1Fj7WinaBA)

<hr></hr>
