#!/usr/bin/env python
# title           :mail.py
# description     : Send,Receive and Parse Emails.
# author          :Alfred Francis , alfred.francis@pearldatadirect.com
# date            :18062016
# version         :0.1
# python_version  :2.7
# ==============================================================================
import imaplib
import smtplib
import sys
from email.parser import Parser as EmailParser
from email.utils import parseaddr

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

class emailManager:
    def __init__(self, imapservername, smtpservername, username, password):
        self.imapServerName = imapservername
        self.userName = username
        self.passWord = password
        self.imapConnection = imaplib.IMAP4_SSL(self.imapServerName, 993)
        self.smtpConnection = smtplib.SMTP(smtpservername, 587)

    def openIMAP(self):
        try:
            (self.responseCode, capabilities) = self.imapConnection.login(self.userName,
                                                                          self.passWord)
        except:
            print sys.exc_info()[1]
            sys.exit(1)
        return self.responseCode

    def openSMTP(self):
        try:
            self.smtpConnection.starttls()
            self.smtpConnection.login(self.userName, self.passWord)
        except:
            print sys.exc_info()[1]
            sys.exit(1)
        return True

    def sendEmail(self, toAddress, subject, body):
        msg = MIMEMultipart()
        msg['From'] = self.userName
        msg['To'] = toAddress
        msg['Subject'] = subject

        body = body
        msg.attach(MIMEText(body, 'plain'))

        text = msg.as_string()
        self.smtpConnection.sendmail(self.userName, toAddress, text)

    def closeSMTP(self):
        return self.smtpConnection.quit()

    def closeIMAP(self):
        return self.imapConnection.close()

    def get_decoded_email_body(self,msg):
        p = EmailParser()
        msgobj = p.parsestr(msg)
        body = None
        html = None
        for part in msgobj.walk():
            print (part.get_content_charset())
            if part.get_content_type() == "text/plain":
                if body is None:
                    body = ""
                body += unicode(
                    part.get_payload(decode=True),
                    "UTF-8",
                    'replace'
                ).encode('utf8', 'replace')
            elif part.get_content_type() == "text/html":
                if html is None:
                    html = ""
                html += unicode(
                    part.get_payload(decode=True),
                    part.get_content_charset(),
                    'replace'
                ).encode('utf8', 'replace')
        return {
            'body': body,
            'html': html,
            'from': parseaddr(msgobj.get('From'))[1],
            'to': parseaddr(msgobj.get('To'))[1]
        }

    def getUnReadMessages(self, emailSubject=""):
        self.imapConnection.select(readonly=0)
        # responseCode, emails = self.imapConnection.search(None,'(UNSEEN SUBJECT "%s")' % emailSubject)
        responseCode, emails = self.imapConnection.search(None, '(UnSeen)')
        if responseCode == 'OK':
            for mailNumber in emails[0].split():
                responseCode, resultData = self.imapConnection.fetch(mailNumber, '(RFC822)')
                #parsedEmail = parser.parsestr(resultData[0][1])
                #singleMail = dict(parsedEmail)
                singleMail = self.get_decoded_email_body(resultData[0][1])
                responseCode, resultData = self.imapConnection.uid('store',
                                                                   '542648', '+FLAGS', '(\\Seen)')
                yield singleMail

    def cleanEmail(self,dirtyMail):
        dirtyMail = dirtyMail.replace(r"\r\n", r"\n").replace(r"  ", r" ")
        result = ""
        for line in dirtyMail.splitlines():
            line = line.strip()
            if (line.startswith('From:')
                or line.startswith('Date:')
                or line.startswith('Subject:')
                or line.startswith('From:')
                or line.startswith('To:')
                or line.startswith('Cc:')
                or line.endswith('>,')
                or line.endswith('>')
                or line.endswith('<')
                or line.endswith(']')
                or line.startswith('Requester')
                or line.startswith('Due by time')
                or line.startswith('Category')
                or line.startswith('Description')
                or line.startswith('--')
                or line.strip() == ""
                ):
                pass
            else:
                result += line.strip() + "\n"
        return result.strip()


if __name__ == '__main__':
    testEmail = emailManager("imap.gmail.com", "smtp.gmail.com", "ikytesting@gmail.com", "ikytesting999")
    testEmail.openIMAP()
    testEmail.openSMTP()
    while True:
        try:
            for singleMail in testEmail.getUnReadMessages():
                print("New Email from :" + singleMail["from"])

                cleanedEmailContent = testEmail.cleanEmail(singleMail["body"])

                print (cleanedEmailContent)

                #r = requests.post("http://172.30.10.141:9999/ikyParseAndExecute?userQuery=" + singleMail["body"])
                #body = "Hi,\n" + r.content + "\nCheers,\n\tiKY"

                testEmail.sendEmail(singleMail["from"], "Reply to your query", body)
        except KeyboardInterrupt:
            testEmail.closeIMAP()
            testEmail.closeSMTP()
            print "Connections terminated"
            sys.exit()
