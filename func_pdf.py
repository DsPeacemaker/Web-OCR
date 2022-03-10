'''from fpdf import FPDF

pdf = FPDF()
pdf.add_page()

pdf.add_font('DejaVu', 'DejaVuSansCondensed.ttf', uni=True)
pdf.set_font('DejaVu', size=15)
pdf.cell(200, 10, txt="Заглавие", ln=1, align='C')
pdf.cell(200, 10, txt="текст.", ln=2, align='C')

pdf.output("output_txt.pdf")
'''
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()

pdf.set_font("Arial", size=16)
f = open("text.txt", "r")
#x = open("text.pdf", "w", encoding="windows-1251")
for x in f:
    pdf.cell(50, 10, txt=x, ln=1, align='C')

pdf.output("output_txt.pdf", 'F')
