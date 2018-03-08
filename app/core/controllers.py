import html2text

from flask import Blueprint, request, Response, g

from flask import current_app as app

from app.commons import buildResponse
from app.core.intentClassifier import IntentClassifier
import app.core.sequenceLabeler as sequenceLabeler
import app.core.nlp as nlp
from app.stories.models import Bot
from functools import wraps

core = Blueprint('core_blueprint', __name__, url_prefix='/core')

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    bot = Bot.objects(username =username , password=password)
    if bot:
      g.bot = bot[0]
      g.botId = g.bot._id
    return bot <> None
    #return username == 'admin' and password == 'secret'

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
      if app.config["PROTECTED"]==False:
        g.botId = None
        return f(*args, **kwargs)
      auth = request.authorization
      if not auth or not check_auth(auth.username, auth.password):
          return authenticate()
      return f(*args, **kwargs)
    return decorated

@core.route('/buildModel/<storyId>', methods=['POST'])
@requires_auth
def buildModel(storyId):
    sequenceLabeler.train(storyId)
    intentClassifier = IntentClassifier()
    intentClassifier.setBotId(g.botId)
    intentClassifier.train()
    return buildResponse.sentOk()


@core.route('/sentenceTokenize', methods=['POST'])
def sentenceTokenize():
    sentences = html2text.html2text(request.form['sentences'])
    result = nlp.sentenceTokenize(sentences)
    return buildResponse.sentPlainText(result)


@core.route('/posTagAndLabel', methods=['POST'])
def posTagAndLabel():
    content = request.get_json(silent=True)
    sentences = None
    if content:
        sentences = content.get("sentences")
    if not sentences:
        sentences = request.form['sentences']
    cleanSentences = html2text.html2text(sentences)
    result = nlp.posTagAndLabel(cleanSentences)
    return buildResponse.buildJson(result)