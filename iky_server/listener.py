from iky_server import app
from interface import execute_action
from mail import emailManager
from predict import predict
from celery import Celery
import celeryconfig

app.config.from_object(celeryconfig)

def make_celery(app):
    celery = Celery(app.import_name,
                    broker=app.config['BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

gmailSmtp = "smtp.gmail.com"
gmailImap = "imap.gmail.com"
gmailUsername = "ikytesting@gmail.com"
gmailPassword = "ikytesting999"


@celery.task
def addToSendEmailQueue(singleMail,result):
    emailSender = emailManager(gmailImap, gmailSmtp, gmailUsername, gmailPassword)
    emailSender.openSMTP()
    body = "Hi,\n\n  %s \n\nCheers,\n\tiKY"%result
    emailSender.sendEmail(singleMail["From"], "Reply to your query", body)
    emailSender.closeSMTP()
    return True

@celery.task
def processEmail(singleMail):
    predicted = predict(singleMail['body'])
    if "error_code" not in predicted:
        result = execute_action(predicted['action_type'],predicted['intent'],predicted["labels"])
    else:
        result = "Sorry im not trained to handle this email."
    addToSendEmailQueue.apply_async(args=[singleMail,result])
    return True


@celery.task
def listen():
    emailReader = emailManager(gmailImap, gmailSmtp, gmailUsername, gmailPassword)
    emailReader.openIMAP()
    count = 0
    for singleMail in emailReader.getUnReadMessages():
        processEmail.apply_async(args=[singleMail])
        count += 1
    emailReader.closeIMAP()
    return count
