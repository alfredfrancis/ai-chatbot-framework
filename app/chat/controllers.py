from flask import Blueprint, request, abort, current_app as app
from app.commons import build_response
from app.dialogue_manager.dialogue_manager import DialogueManager
from app.dialogue_manager.models import ChatModel

chat = Blueprint('chat', __name__, url_prefix='/api')

# Initialize DialogueManager
dialogue_manager : DialogueManager  = DialogueManager()

@chat.before_app_first_request
def initialize_dialogue_manager():
    global dialogue_manager
    dialogue_manager.update_model(app)

@chat.route('/v1', methods=['POST'])
def api():
    """
    Endpoint to converse with the chatbot.
    Delegates the request processing to DialogueManager.

    :return: JSON response with the chatbot's reply and context.
    """
    request_json = request.get_json(silent=True)
    if not request_json:
        app.logger.error("Invalid request: No JSON payload")
        return abort(400)

    try:
        # Delegate processing to DialogueManager
        chat_request = ChatModel.from_json(request_json)
        chat_response = dialogue_manager.process(app, chat_request)
        return build_response.build_json(chat_response.to_json())
    except Exception as e:
        app.logger.error(f"Error processing request: {e}", exc_info=True)
        return abort(500)