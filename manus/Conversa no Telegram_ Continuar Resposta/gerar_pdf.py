from fpdf import FPDF

def gerar_pdf_exemplo(nome_arquivo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(40, 10, 'Relatório em PDF de Exemplo')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 10, 'Este é um exemplo de relatório em PDF gerado usando a biblioteca Fpdf2 em Python. É possível adicionar texto, imagens, tabelas e controlar o layout de forma programática.')
    pdf.ln(10)
    pdf.multi_cell(0, 10, 'A Fpdf2 oferece um controle granular sobre a posição dos elementos, fontes, cores e outros aspectos visuais do documento.')

    pdf.output(nome_arquivo)
    print(f'Documento {nome_arquivo} gerado com sucesso.')

if __name__ == '__main__':
    gerar_pdf_exemplo('relatorio_exemplo.pdf')
