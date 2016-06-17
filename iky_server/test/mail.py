import imaplib
import email
from email.parser import Parser
import sys

conn = imaplib.IMAP4_SSL('imap.gmail.com')

try:
    (retcode, capabilities) = conn.login("ikytesting@gmail.com", "ikytesting999")
except:
    print sys.exc_info()[1]
    sys.exit(1)

conn.select(readonly=1) # Select inbox or default namespace
(retcode, messages) = conn.search(None, '(UNSEEN)')
if retcode == 'OK':
    for num in messages[0].split(' '):
        print 'Processing :', num
        typ, data = conn.fetch(num,'(RFC822)')
        msg = email.message_from_string(data[0][1])
        typ, data = conn.store(num,'-FLAGS','\\Seen')
        if typ == 'OK':
            print data,'\n',30*'-'
            print msg

conn.close()