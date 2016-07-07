

import re
import string

def parse(email_text, remove_quoted_statements=True):
    email_text = email_text.strip()
    email_text = strip_automated_notation(email_text)    
    if remove_quoted_statements:
        pattern = """(?P<quoted_statement>".*?")"""
        matches = re.findall(pattern, email_text, re.IGNORECASE + re.DOTALL)
        for m in matches:
            email_text = email_text.replace(m, '"[quote]"')
    result = { \
              "salutation":get_salutation(email_text), \
              "body":get_body(email_text), \
              "signature":get_signature(email_text), \
              "reply_text":get_reply_text(email_text) \
              }
    return result

#automated_notation could be any labels or sections in the email giving special notation for
#human readers of the email text. For example, email_text may start with "A message from your customer:"
def strip_automated_notation(email_text):
    #Use a paramater name email_text to indicate text in the actual email message
    notations = [
                 "Hi, there has been a new enquiry from\..*?Enquiry:(?P<email_message>.*)",
                 ]
    for n in notations:
        groups = re.match(n, email_text, re.IGNORECASE + re.DOTALL)
        if not groups is None:
            if groups.groupdict().has_key("email_message"):
                email_text = groups.groupdict()["email_message"]
    
    return email_text
    

def get_reply_text(email_text):
    #Notes on regex
    #Search for classic prefix from GMail and other mail clients "On May 16, 2011, Dave wrote:"
    #Search for prefix from outlook clients From: Some Person [some.person@domain.tld]
    #Search for prefix from outlook clients when used for sending to recipients in the same domain From: Some Person\nSent: 16/05/2011 22:42\nTo: Some Other Person
    #Search for prefix when message has been forwarded
    #Search for From: <email@domain.tld>\nTo: <email@domain.tld>\nDate:<email@domain.tld
    #Search for From:, To:, Sent:
    #Some clients use -*Original Message-*
    pattern = "(?P<reply_text>" + \
        "On ([a-zA-Z0-9, :/<>@\.\"\[\]]* wrote:.*)|" + \
        "From: [\w@ \.]* \[mailto:[\w\.]*@[\w\.]*\].*|" + \
        "From: [\w@ \.]*(\n|\r\n)+Sent: [\*\w@ \.,:/]*(\n|\r\n)+To:.*(\n|\r\n)+.*|" + \
        "[- ]*Forwarded by [\w@ \.,:/]*.*|" + \
        "From: [\w@ \.<>\-]*(\n|\r\n)To: [\w@ \.<>\-]*(\n|\r\n)Date: [\w@ \.<>\-:,]*\n.*|" + \
        "From: [\w@ \.<>\-]*(\n|\r\n)To: [\w@ \.<>\-]*(\n|\r\n)Sent: [\*\w@ \.,:/]*(\n|\r\n).*|" + \
        "From: [\w@ \.<>\-]*(\n|\r\n)To: [\w@ \.<>\-]*(\n|\r\n)Subject:.*|" + \
        "(-| )*Original Message(-| )*.*)"
    groups = re.search(pattern, email_text, re.IGNORECASE + re.DOTALL)
    reply_text = None
    if not groups is None:
        if groups.groupdict().has_key("reply_text"):
            reply_text = groups.groupdict()["reply_text"]
    return reply_text
    

def get_signature(email_text):
    
    #try not to have the signature be the very start of the message if we can avoid it
    salutation = get_salutation(email_text)
    if salutation: email_text = email_text[len(salutation):]
    
    #note - these openinged statements *must* be in lower case for 
    #sig within sig searching to work later in this func
    sig_opening_statements = [
                              "thanks & regards",
                              "warm regards",
                              "kind regards",
                              "regards",
                              "cheers",
                              "many thanks",
                              "thanks",
                              "sincerely",
                              "ciao",
                              "Best",
                              "bGIF",
                              "thank you",
                              "thankyou",
                              "talk soon",
                              "cordially",
                              "yours truly",
                              "thanking You",
                              "sent from my iphone"]
    pattern = "(?P<signature>(" + string.joinfields(sig_opening_statements, "|") + ")(.)*)"
    groups = re.search(pattern, email_text, re.IGNORECASE + re.DOTALL)
    signature = None
    if groups:
        if groups.groupdict().has_key("signature"):
            signature = groups.groupdict()["signature"]
            reply_text = get_reply_text(email_text[email_text.find(signature):])
            if reply_text: signature = signature.replace(reply_text, "")
            
            #search for a sig within current sig to lessen chance of accidentally stealing words from body
            tmp_sig = signature
            for s in sig_opening_statements:
                if tmp_sig.lower().find(s) == 0:
                    tmp_sig = tmp_sig[len(s):]
            groups = re.search(pattern, tmp_sig, re.IGNORECASE + re.DOTALL)
            if groups: signature = groups.groupdict()["signature"]
        
    #if no standard formatting has been provided (e.g. Regards, <name>), 
    #try a probabilistic approach by looking for phone numbers, names etc. to derive sig    
    if not signature:
        #body_without_sig = get_body(email_text, check_signature=False)
        pass
    
    #check to see if the entire body of the message has been 'stolen' by the signature. If so, return no sig so body can have it.
    body_without_sig = get_body(email_text, check_signature=False)
    if signature==body_without_sig: signature = None
    
    return signature

#todo: complete this out (I bit off a bit more than I could chew with this function. Will probably take a bunch of basian stuff
def is_word_likely_in_signature(word, text_before="", text_after=""):
    #Does it look like a phone number?
    
    #is it capitalized?
    if word[:1] in string.ascii_uppercase and word[1:2] in string.ascii_lowercase: return True
    
    return
    
#check_<zone> args provided so that other functions can call get_body without causing infinite recursion
def get_body(email_text, check_salutation=True, check_signature=True, check_reply_text=True):
    
    if check_salutation:
        sal = get_salutation(email_text)
        if sal: email_text = email_text[len(sal):]
    
    if check_signature:
        sig = get_signature(email_text)
        if sig: email_text = email_text[:email_text.find(sig)]
    
    if check_reply_text:
        reply_text = get_reply_text(email_text)
        if reply_text: email_text = email_text[:email_text.find(reply_text)]
            
    return email_text

def get_salutation(email_text):
    #remove reply text fist (e.g. Thanks\nFrom: email@domain.tld causes salutation to consume start of reply_text
    reply_text = get_reply_text(email_text)
    if reply_text: email_text = email_text[:email_text.find(reply_text)]
    #Notes on regex:
    #Max of 5 words succeeding first Hi/To etc, otherwise is probably an entire sentence
    salutation_opening_statements = [
                                     "hi",
                                     "dear",
                                     "to",
                                     "hey",
                                     "hello",
                                     "thanks",
                                     "good morning",
                                     "good afternoon",
                                     "good evening",
                                     "thankyou",
                                     "thank you"]
    pattern = "\s*(?P<salutation>(" + string.joinfields(salutation_opening_statements, "|") + ")+(\s*\w*)(\s*\w*)(\s*\w*)(\s*\w*)(\s*\w*)[\.,\xe2:]+\s*)"
    groups = re.match(pattern, email_text, re.IGNORECASE)
    salutation = None
    if not groups is None:
        if groups.groupdict().has_key("salutation"):
            salutation = groups.groupdict()["salutation"]
    return salutation
    
