from flask import Blueprint, render_template

chat = Blueprint('chat_blueprint', __name__,
                 url_prefix='/',
                 template_folder='templates'
                 )


@chat.route('/', methods=['GET'])
def home():
    return render_template('chat.html')


@chat.route('/angular', methods=['GET'])
def home_angular():
    return render_template('../apps/chat-angular/dist/index.html')

@chat.route('/admin/angular', methods=['GET'])
def home_admin_angular():
    return render_template('../apps/admin-angular/dist/index.html')