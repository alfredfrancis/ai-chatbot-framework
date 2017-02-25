# Jarvis
### An AI Chatbot framework built in Python
JARVIS is an AI based conversational dialog interface built in Python. It can be used to create Natural language conversation scenarios with zero coding effort.The simple web UI makes it very easy to create and train your conversations. Jarvis's API can be used to integrate with any channel of your choice such as Messenger,Slack etc. This is a very basic project so you can start building on it.It may contain lots of bugs,please free to contribute via pull requests.


### Demo

Checkout this basic tutorial on youtube,

[![IMAGE ALT TEXT HERE](https://img.youtube.com/vi/S1Fj7WinaBA/0.jpg)](https://www.youtube.com/watch?v=S1Fj7WinaBA)

Please visit my [website](http://alfredfrancis.github.io) to see my personal chatbot in action

### Installation

* add your dev/production configurations in config.py 

```python
class Production(Config):
    # MongoDB Database Details
    DB_HOST = "mongodb://127.0.0.1:27017/"
    DB_USERNAME = ""
    DB_PASSWORD = ""

    # Web Server details
    WEB_SERVER_PORT = 80

class Development(Config):
    DEBUG = True
```

### Docker
```sh
docker build -t "ai-chat-bot" .
docker run --name=chabot-node-1  -e="APPLICATION_ENV=Production" -v ./:/app-container -p 8001:8080 -it ai-chat-bot gunicorn --bind 0.0.0.0:8080 run:app
docker exec -it chabot-node-1 python /app-container/setup.py
```
#### OR
#### Docker Compose ( Recommended)
```sh
docker-compose build
docker-compose up -d
```
### without docker

* Then use pip to install all required python packages
```sh
pip install -r requirments.txt
```
* Run setup script for setting up some default intents
```sh
$ python setup.py
```

* Development
```sh
$ python run.py
```
* Production
```sh
$ APPLICATION_ENV="Production" gunicorn -k gevent --bind 0.0.0.0:8001 run:app
```
That's it.

### Creating and Training your stories
Navigate to http://localhost:8001

#### NLTK
See [NLTK documentation](www.nltk.org/)

#### SKlearn
See [SKLearn documentation](http://scikit-learn.org/)

#### CRFsuite
See [CRFsuite documentation](http://www.chokkan.org/software/crfsuite/)

See [python CRfSuite](https://python-crfsuite.readthedocs.io/en/latest/)


### Todos

 - Write Unit Tests
 - Improve intent classification accuracy
 - Add parameter types
 - Migrate UI to React JS

License
----
[MIT](https://opensource.org/licenses/MIT) 



**Free Software, Hell Yeah!**
