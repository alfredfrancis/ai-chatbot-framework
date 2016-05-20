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

def extract_chunks(tagged_sent):
    grp1, grp2 = "",""
    for s, tp in tagged_sent:
        if tp != "O":
            if tp.endswith(chunk_type):
                if not tp.startswith("B"):
                    grp2 = tp
                    grp1.append(s)
                else:
                    if grp1:
                        yield " ".join(grp1), "-".join(grp2)
                    grp1, grp2 = [s], [str(ind)]
    yield " ".join(grp1), grp2

l = [('my', 'o'), ('name', 'B-DOMAIN'), ('is', 'o'), ('Alfred', 'B-NAME'),
 ('Francis', 'I-NAME')]

print(list(extract_chunks(l)))