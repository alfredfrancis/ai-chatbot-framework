from celery import Celery

from ikyCore.intentClassifier import IntentClassifier
from ikyCore import sequenceLabeler
from ikyCore.packResult import packResult
from ikyCore.interface import executeAction

from ikyCommons.mail import emailManager
from ikyCommons import errorCodes

celery = Celery()

celery.config_from_object('ikyMainframe.celeryconfig')


gmailSmtp = "smtp.gmail.com"
gmailImap = "imap.gmail.com"
gmailUsername = "ikytesting@gmail.com"
gmailPassword = "ikytesting999"


@celery.task
def addToSendEmailQueue(singleMail,result):
    emailSender = emailManager(gmailImap, gmailSmtp, gmailUsername, gmailPassword)
    emailSender.openSMTP()
    body = "Hi,\n\n  %s \n\nCheers,\n\t iKY" %result
    emailSender.sendEmail(singleMail["From"], "Reply to your query", body)
    emailSender.closeSMTP()
    return True

@celery.task
def processEmail(singleMail):
    if singleMail["body"]:
        intentClassifier = IntentClassifier()
        storyId = intentClassifier.predict(singleMail["body"])
        if storyId:
            extractedEntities = sequenceLabeler.predict(storyId, singleMail["body"])
            resultDictonary = packResult(storyId, extractedEntities)
            if "errorCode" not in resultDictonary:
                result = executeAction(resultDictonary['actionType'], resultDictonary['actionName'],
                                                 resultDictonary["entities"])
            else:
                result = errorCodes.UnableToextractentities["description"]
        else:
            result = errorCodes.UnidentifiedIntent["description"]
    else:
        result = errorCodes.EmptyInput["description"]
    addToSendEmailQueue.apply_async(args=[singleMail,result])
    return True


@celery.task
def listen():
    emailReader = emailManager(gmailImap, gmailSmtp, gmailUsername, gmailPassword)
    emailReader.openIMAP()
    count = 0
    for singleMail in emailReader.getUnReadMessages():
        singleMail["body"] = emailReader.cleanEmail(singleMail["body"])
        print(singleMail["body"])
        processEmail.apply_async(args=[singleMail])
        count += 1
    emailReader.closeIMAP()
    return count


if __name__ == '__main__':
    celery.start()