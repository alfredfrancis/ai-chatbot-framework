# Installation

## Using docker-compose (recommended)

### Prerequisites

Before proceeding, make sure you have the latest version of docker and docker-compose installed.

We recommend a version equal to or higher than the following.

```sh
$ docker --version
Docker version 20.10.10, build b485636
$ docker compose version
Docker Compose version v2.14.1
```

### Steps to deploy

Get the service up and running.

```sh
docker-compose up -d
```

To access the admin panel, open http://<your-external-ip>:8080/ in your favorite browser

## Steps to deploy to Kubernetes (Using Helm)

### Prerequisites

Before proceeding, make sure you have access to a Kubernetes cluster and latest version of helm installed.

### Steps to deploy

Get the service up and running.

```sh
helm dep update helm/ai-chatbot-framework

helm upgrade --install --create-namespace -n ai-chatbot-framework ai-chatbot-framework helm/ai-chatbot-framework
```

To access the admin panel, open http://<your-external-ip>:8080/ in your favorite browser.

port forward to local (optional)
```sh
kubectl port-forward --namespace=ai-chatbot-framework service/ingress-nginx-controller 8080:80
```

## Next Steps
- [Getting started](02-getting-started.md)