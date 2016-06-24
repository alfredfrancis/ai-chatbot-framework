import html2text
from bs4 import BeautifulSoup
data = """
<span style="background-color: green; color: white;" class="Highlight"><span style="background-color: green; color: white;" class="Highlight"><span style="background-color: green; color: white;" class="Highlight">hello<br>dea<span style="background-color: green; color: white;" class="Highlight"><span style="background-color: green; color: white;" class="Highlight">r friend</span></span><br>how are<span style="background-color: green; color: white;" class="Highlight"> you to da</span>y<br><br></span></span></span>
"""
print html2text.html2text(data)

print ("\n\n")

soup = BeautifulSoup(data, "html.parser")
print(soup.getText())