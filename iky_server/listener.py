from celery import Celery
from mail import emailManager

BROKER_URL = 'mongodb://localhost:27017/test'

celery = Celery('EOD_TASKS', broker=BROKER_URL)

celery.config_from_object('celeryconfig')

gmailSmtp = "smtp.gmail.com"
gmailImap = "imap.gmail.com"
gmailUsername = "ikytesting@gmail.com"
gmailPassword = "ikytesting999"


@celery.task
def processEmail(singleMail):
    emailSender = emailManager(gmailImap, gmailSmtp, gmailUsername, gmailPassword)
    emailSender.openSMTP()
    body = "Hi,\nYour query has been received.We'll get back to you soon\nCheers,\n\tiKY"
    emailSender.sendEmail(singleMail["From"], "Reply to your query", body)
    emailSender.closeSMTP()
    return id


@celery.task
def listen():
    emailReader = emailManager(gmailImap, gmailSmtp, gmailUsername, gmailPassword)
    emailReader.openIMAP()
    count = 0
    for singleMail in emailReader.getUnReadMessages():
        processEmail.apply_async((singleMail), queue='emailProcessing')
        count += 1
    emailReader.closeIMAP()
    return count
