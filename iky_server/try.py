def extract_chunks(tagged_sent):
    labeled = {}
    labels=set()
    for s, tp in tagged_sent:
        if tp != "O":
            label = tp[2:]
            if tp.startswith("B"):
                labeled[label] = s
                labels.add(label)
            elif tp.startswith("I") and (label in labels) :
                labeled[label] += " %s"%s
    return labeled

l = [(u'google', 'B-DOMAIN'), (u'for', 'O'), (u'how', 'B-QUERY'), (u'are', 'I-QUERY'), (u'you', 'I-QUERY')]


print(extract_chunks(l))