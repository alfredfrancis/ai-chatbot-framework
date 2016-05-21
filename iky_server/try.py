"""
def extract_chunks(tagged_sent, chunk_type):
    grp1, grp2, chunk_type = [], "", "-" + chunk_type
    for ind, (s, tp) in enumerate(tagged_sent):
        if tp.endswith(chunk_type):
            if not tp.startswith("B"):
                grp2 = tp
                grp1.append(s)
            else:
                if grp1:
                    yield " ".join(grp1), "-".join(grp2)
                grp1, grp2 = [s], [str(ind)]
    yield " ".join(grp1), grp2
"""
"""
def extract_chunks(tagged_sent):
    checked = []
    grp1, grp2 = "",""
    for s, tp in tagged_sent:
        if tp != "O":
            label = tp[2:]
            if tp.startswith("B") && (label not in checked):
                grp2 = tp[2:]
                grp1.append(s)
            else:
                if grp1:
                    yield " ".join(grp1), "-".join(grp2)
                    grp1, grp2 = [s], [str(ind)]
    yield " ".join(grp1), grp2
"""

def extract_chunks(tagged_sent):
    labeled = {}
    labels=[]
    for s, tp in tagged_sent:
        if tp != "O":
            label = tp[2:]
            if tp.startswith("B"):
                labeled[label] = s
            elif tp.startswith("I") and (label not in labels) :
                labels.append(label)
                labeled[label] = s
            elif (tp.startswith("I") and (label in labels)):
                labeled[label] += " %s"%s
    return labeled

l = [('sms', 'B-TSK'), ('8714349616', 'B-MOB'), ('saying', 'I-MSG'), ('hello', 'I-MSG'), ('how', 'I-MSG'), ('are', 'I-MSG'), ('you', 'I-MSG')]




print(extract_chunks(l))