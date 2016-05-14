def levenshtein(s1, s2):
	n, m = len(s1), len(s2)
	if n < m:
		return levenshtein(s2, s1)

    # len(s1) >= len(s2)
	if m == 0:
		return n

	previous_row = range(m + 1)
	for i, c1 in enumerate(s1):
	    current_row = [i + 1]
	    for j, c2 in enumerate(s2):
	        insertions = previous_row[j + 1] + 1 # j+1 instead of j since previous_row and current_row are one character longer
	        deletions = current_row[j] + 1       # than s2
	        substitutions = previous_row[j] + (c1 != c2)
	        current_row.append(min(insertions, deletions, substitutions))
	    previous_row = current_row

	return previous_row[-1]