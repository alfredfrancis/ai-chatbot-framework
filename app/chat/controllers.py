from flask import Blueprint, render_template

chat = Blueprint('chat_blueprint', __name__,
                 url_prefix='/',
                 template_folder='templates'
                 )


@chat.route('/', methods=['GET'])
def home():
    return render_template('chat.html')
