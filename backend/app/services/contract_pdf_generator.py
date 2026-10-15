"""
Gerador de PDF para contratos odontológicos
"""

import io
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT

logger = logging.getLogger(__name__)

class ContractPDFGenerator:
    """Gerador de PDF para contratos odontológicos"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Configura estilos customizados"""
        # Título principal
        self.styles.add(ParagraphStyle(
            name='ContractTitle',
            parent=self.styles['Title'],
            fontSize=20,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtítulo
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=12,
            spaceBefore=20,
            leftIndent=0,
            fontName='Helvetica-Bold'
        ))
        
        # Texto normal
        self.styles.add(ParagraphStyle(
            name='ContractNormal',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=16,
            textColor=colors.HexColor('#111827'),
            alignment=TA_JUSTIFY,
            spaceAfter=12
        ))
        
        # Dados destacados
        self.styles.add(ParagraphStyle(
            name='HighlightData',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#1e40af'),
            fontName='Helvetica-Bold'
        ))
    
    def format_currency(self, value: float) -> str:
        """Formata valor monetário"""
        return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    def generate_contract_pdf(self, contract_data: Dict[str, Any]) -> bytes:
        """
        Gera o PDF do contrato
        
        Args:
            contract_data: Dicionário com os dados do contrato
                - paciente_nome: Nome do paciente
                - paciente_cpf: CPF do paciente
                - venda_id: ID da venda
                - data_venda: Data da venda
                - valor_total: Valor total do contrato
                - qtd_parcelas: Quantidade de parcelas
                - valor_parcela: Valor de cada parcela
                - unidade: Unidade de atendimento
                - tratamentos: Lista de tratamentos (opcional)
                
        Returns:
            bytes: PDF gerado
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        # Elementos do PDF
        elements = []
        
        # Cabeçalho
        elements.append(Paragraph("CONTRATO DE PRESTAÇÃO DE SERVIÇOS ODONTOLÓGICOS", self.styles['ContractTitle']))
        elements.append(Spacer(1, 20))
        
        # Dados das partes
        elements.append(Paragraph("<b>1. DAS PARTES</b>", self.styles['SectionTitle']))
        
        # Contratante
        contratante_text = f"""
        <b>CONTRATANTE:</b><br/>
        Nome: <b>{contract_data.get('paciente_nome', '')}</b><br/>
        CPF: <b>{contract_data.get('paciente_cpf', '')}</b><br/>
        """
        elements.append(Paragraph(contratante_text, self.styles['ContractNormal']))
        
        # Contratada
        contratada_text = f"""
        <b>CONTRATADA:</b><br/>
        GRUPO JF ODONTOLOGIA<br/>
        Unidade: <b>{contract_data.get('unidade', 'Nova Iguaçu 1')}</b><br/>
        """
        elements.append(Paragraph(contratada_text, self.styles['ContractNormal']))
        elements.append(Spacer(1, 20))
        
        # Objeto do contrato
        elements.append(Paragraph("<b>2. DO OBJETO</b>", self.styles['SectionTitle']))
        objeto_text = """
        O presente contrato tem por objeto a prestação de serviços odontológicos pela CONTRATADA ao CONTRATANTE, 
        conforme plano de tratamento aprovado e detalhado neste instrumento.
        """
        elements.append(Paragraph(objeto_text, self.styles['ContractNormal']))
        elements.append(Spacer(1, 20))
        
        # Valor e forma de pagamento
        elements.append(Paragraph("<b>3. DO VALOR E FORMA DE PAGAMENTO</b>", self.styles['SectionTitle']))
        
        valor_total = self.format_currency(contract_data.get('valor_total', 0))
        qtd_parcelas = contract_data.get('qtd_parcelas', 0)
        valor_parcela = self.format_currency(contract_data.get('valor_parcela', 0))
        
        pagamento_text = f"""
        Valor Total do Tratamento: <b>{valor_total}</b><br/>
        Forma de Pagamento: <b>{qtd_parcelas}x de {valor_parcela}</b><br/>
        Vencimento: Todo dia <b>15</b> de cada mês<br/>
        """
        elements.append(Paragraph(pagamento_text, self.styles['ContractNormal']))
        elements.append(Spacer(1, 20))
        
        # Tratamentos (se houver)
        if contract_data.get('tratamentos'):
            elements.append(Paragraph("<b>4. DOS PROCEDIMENTOS</b>", self.styles['SectionTitle']))
            
            # Tabela de tratamentos
            table_data = [['Procedimento', 'Valor']]
            for trat in contract_data['tratamentos']:
                table_data.append([
                    trat.get('nome', ''),
                    self.format_currency(trat.get('valor', 0))
                ])
            
            # Adicionar total
            table_data.append(['TOTAL', valor_total])
            
            table = Table(table_data, colWidths=[350, 100])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e5e7eb')),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
        
        # Cláusulas gerais
        elements.append(Paragraph("<b>5. DAS DISPOSIÇÕES GERAIS</b>", self.styles['SectionTitle']))
        clausulas_text = """
        5.1. O presente contrato é firmado por prazo indeterminado, iniciando-se na data de sua assinatura.<br/>
        5.2. O CONTRATANTE declara ter sido informado sobre o tratamento, seus riscos e benefícios.<br/>
        5.3. Este contrato poderá ser rescindido por qualquer das partes mediante aviso prévio de 30 dias.<br/>
        5.4. O não pagamento de 3 (três) parcelas consecutivas poderá ensejar a suspensão do tratamento.<br/>
        """
        elements.append(Paragraph(clausulas_text, self.styles['ContractNormal']))
        elements.append(Spacer(1, 30))
        
        # Data e assinaturas
        data_contrato = datetime.now().strftime('%d de %B de %Y')
        elements.append(Paragraph(f"<b>{contract_data.get('unidade', 'Nova Iguaçu')}, {data_contrato}</b>", 
                                 self.styles['ContractNormal']))
        elements.append(Spacer(1, 40))
        
        # Linhas para assinatura
        assinatura_data = [
            ['_' * 50, '_' * 50],
            ['CONTRATANTE', 'CONTRATADA'],
            [contract_data.get('paciente_nome', ''), 'GRUPO JF ODONTOLOGIA']
        ]
        
        assinatura_table = Table(assinatura_data, colWidths=[220, 220])
        assinatura_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, 1), 20),
        ]))
        
        elements.append(assinatura_table)
        
        # Informações adicionais
        elements.append(Spacer(1, 30))
        info_text = f"""
        <font size="9">
        Documento: {contract_data.get('documento_venda', '')}<br/>
        Venda ID: {contract_data.get('venda_id', '')}<br/>
        Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}
        </font>
        """
        elements.append(Paragraph(info_text, self.styles['Normal']))
        
        # Gerar PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes