# Jarvis
### An AI Chatbot framework build in Python
JARVIS is an AI based conversational dialog interface built in Python. It can be used to create Natural language conversation scenarios with zero coding effort.The simple web UI makes it very easy to create and train your conversations. Jarvis's API can be used to integrate with any channel of your choice such as Messenger,Slack etc. This is a very basic project so you can satrt building on it.It may contain lots of bugs,please free to contribute via pull requests.

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

* Then use pip to install all required python packages
```sh
pip install -r requirments.txt
```
* Run setup script for setting up some default intents
```sh
$ python setup.py
```
That's it.

### Docker
will be added soon.

#### docker-compose.yml

will be added soon

### running
* Development
```sh
$ python run.py
```
* Production
```sh
$ APPLICATION_ENV="Production" gunicorn -k gevent --bind 0.0.0.0:8080 run:app
```
### Creating and Training your stories
Navigate to http://localhost:8080

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




**Free Software, Hell Yeah!**
