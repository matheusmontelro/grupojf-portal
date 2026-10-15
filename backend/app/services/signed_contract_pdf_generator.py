"""
Gerador de PDF para contratos digitais assinados
Inclui selfie, assinatura e dados completos do contrato
"""

import io
import base64
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from PIL import Image as PILImage
from ..database.db import DatabaseConnection

logger = logging.getLogger(__name__)

class SignedContractPDFGenerator:
    """Gerador de PDF para contratos digitais assinados"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Configura estilos customizados"""
        # Título principal
        self.styles.add(ParagraphStyle(
            name='ContractTitle',
            parent=self.styles['Title'],
            fontSize=18,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtítulo
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#374151'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold'
        ))
        
        # Texto normal
        self.styles.add(ParagraphStyle(
            name='ContractNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#111827'),
            alignment=TA_JUSTIFY,
            spaceAfter=8
        ))
        
        # Dados destacados
        self.styles.add(ParagraphStyle(
            name='HighlightData',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1e40af'),
            fontName='Helvetica-Bold'
        ))
    
    def format_currency(self, value: float) -> str:
        """Formata valor monetário"""
        return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    def format_cpf(self, cpf: str) -> str:
        """Formata CPF"""
        if not cpf or len(cpf) != 11:
            return cpf
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    
    def _base64_to_image(self, base64_data: str, max_width: float = 150, max_height: float = 150) -> Optional[Image]:
        """Converte base64 para imagem ReportLab"""
        try:
            if not base64_data:
                return None
                
            # Remove o prefixo data:image/...;base64, se presente
            if ',' in base64_data:
                base64_data = base64_data.split(',')[1]
            
            # Decodifica e cria imagem PIL
            image_data = base64.b64decode(base64_data)
            pil_image = PILImage.open(io.BytesIO(image_data))
            
            # Redimensiona mantendo proporção
            pil_image.thumbnail((int(max_width * 2), int(max_height * 2)), PILImage.Resampling.LANCZOS)
            
            # Converte para bytes novamente
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format='JPEG')
            img_buffer.seek(0)
            
            # Cria imagem ReportLab
            return Image(img_buffer, width=max_width, height=max_height)
            
        except Exception as e:
            logger.error(f"Erro ao processar imagem base64: {e}")
            return None
    
    def _get_dependent_info(self, dependente_id: int) -> Optional[Dict]:
        """Busca informações do dependente"""
        if not dependente_id:
            return None
            
        try:
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT nome, data_nascimento, parentesco, cpf, rg
                    FROM dependentes 
                    WHERE id = %s
                """, (dependente_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'nome': result[0],
                        'data_nascimento': result[1],
                        'parentesco': result[2],
                        'cpf': result[3],
                        'rg': result[4]
                    }
        except Exception as e:
            logger.error(f"Erro ao buscar dados do dependente: {e}")
            
        return None
    
    def generate_signed_contract_pdf(self, contract_data: Dict[str, Any]) -> bytes:
        """
        Gera o PDF do contrato assinado
        
        Args:
            contract_data: Dicionário com os dados do contrato assinado
                
        Returns:
            bytes: PDF gerado
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm
        )
        
        elements = []
        
        # Cabeçalho
        elements.append(Paragraph("CONTRATO DIGITAL ASSINADO", self.styles['ContractTitle']))
        elements.append(Paragraph("GRUPO JF ODONTOLOGIA", self.styles['ContractTitle']))
        elements.append(Spacer(1, 15))
        
        # Informações do contrato
        info_data = [
            ['Contrato ID:', f"#{contract_data.get('contract_id', '')}"],
            ['Data de Assinatura:', contract_data.get('data_assinatura', datetime.now()).strftime('%d/%m/%Y às %H:%M')],
            ['Vendedor:', contract_data.get('vendedor_nome', 'N/A')],
            ['Unidade:', contract_data.get('unidade', 'Nova Iguaçu 1')]
        ]
        
        info_table = Table(info_data, colWidths=[80, 200])
        info_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 15))
        
        # Dados do Paciente/Responsável
        elements.append(Paragraph("1. DADOS DO CONTRATANTE", self.styles['SectionTitle']))
        
        paciente_text = f"""
        <b>Nome:</b> {contract_data.get('paciente_nome', '').upper()}<br/>
        <b>CPF:</b> {self.format_cpf(contract_data.get('paciente_cpf', ''))}<br/>
        <b>Unidade:</b> {contract_data.get('unidade', 'Nova Iguaçu 1')}<br/>
        """
        elements.append(Paragraph(paciente_text, self.styles['ContractNormal']))
        
        # Dados do dependente se houver
        dependente_info = self._get_dependent_info(contract_data.get('dependente_id'))
        if dependente_info:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph("TRATAMENTO PARA DEPENDENTE:", self.styles['SectionTitle']))
            dependente_text = f"""
            <b>Nome do Dependente:</b> {dependente_info['nome'].upper()}<br/>
            <b>Data de Nascimento:</b> {dependente_info['data_nascimento'] or 'N/A'}<br/>
            <b>Parentesco:</b> {dependente_info['parentesco'] or 'N/A'}<br/>
            """
            elements.append(Paragraph(dependente_text, self.styles['ContractNormal']))
        
        elements.append(Spacer(1, 15))
        
        # Dados Financeiros
        elements.append(Paragraph("2. DADOS FINANCEIROS", self.styles['SectionTitle']))
        
        qtd_parcelas = contract_data.get('qtd_parcelas', 12)
        valor_parcela = contract_data.get('valor_parcela', 0)
        
        financeiro_text = f"""
        <b>Valor Total:</b> {self.format_currency(contract_data.get('valor_total', 0))}<br/>
        <b>Forma de Pagamento:</b> {contract_data.get('forma_pagamento', 'CARNÊ')}<br/>
        <b>Parcelas:</b> {qtd_parcelas}x de {self.format_currency(valor_parcela)}<br/>
        <b>Vencimento:</b> Todo dia {contract_data.get('dia_vencimento', 15)} de cada mês<br/>
        """
        elements.append(Paragraph(financeiro_text, self.styles['ContractNormal']))
        elements.append(Spacer(1, 15))
        
        # Seção de Validação Digital
        elements.append(Paragraph("3. VALIDAÇÃO DIGITAL", self.styles['SectionTitle']))
        
        # Criar tabela com selfie e assinatura lado a lado
        validation_data = []
        validation_images = []
        
        # Processar selfie
        selfie_img = self._base64_to_image(contract_data.get('selfie'), 120, 120)
        if selfie_img:
            validation_images.append([
                Paragraph("<b>Selfie de Validação</b>", self.styles['ContractNormal']),
                Paragraph("<b>Assinatura Digital</b>", self.styles['ContractNormal'])
            ])
        
        # Processar assinatura
        signature_img = self._base64_to_image(contract_data.get('signature'), 150, 80)
        
        if selfie_img or signature_img:
            img_row = []
            if selfie_img:
                img_row.append(selfie_img)
            else:
                img_row.append(Paragraph("Selfie não disponível", self.styles['ContractNormal']))
                
            if signature_img:
                img_row.append(signature_img)
            else:
                img_row.append(Paragraph("Assinatura não disponível", self.styles['ContractNormal']))
            
            validation_images.append(img_row)
        
        if validation_images:
            validation_table = Table(validation_images, colWidths=[150, 150])
            validation_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ]))
            elements.append(validation_table)
        
        elements.append(Spacer(1, 15))
        
        # Informações do Dispositivo
        device_info = contract_data.get('device_info', {})
        if device_info:
            elements.append(Paragraph("4. INFORMAÇÕES DE AUDITORIA", self.styles['SectionTitle']))
            
            device_text = f"""
            <b>Tipo de Dispositivo:</b> {device_info.get('device_type', 'N/A').title()}<br/>
            <b>Resolução da Tela:</b> {device_info.get('screen_resolution', 'N/A')}<br/>
            <b>Navegador:</b> {device_info.get('user_agent', 'N/A')[:80]}...<br/>
            <b>Data/Hora da Assinatura:</b> {device_info.get('timestamp', 'N/A')}<br/>
            """
            elements.append(Paragraph(device_text, self.styles['ContractNormal']))
            elements.append(Spacer(1, 15))
        
        # Termos Legais
        elements.append(Paragraph("5. TERMOS E CONDIÇÕES", self.styles['SectionTitle']))
        
        termos_text = """
        Este contrato foi assinado digitalmente de acordo com a Lei 14.063/2020 que dispõe sobre o uso de 
        assinaturas eletrônicas em interações com entes públicos e privados. A assinatura eletrônica 
        apresentada possui validade jurídica equivalente à assinatura manuscrita.
        
        O presente documento comprova a manifestação de vontade das partes em aderir aos termos e 
        condições do tratamento odontológico contratado, conforme plano de tratamento apresentado 
        e aceito digitalmente.
        """
        elements.append(Paragraph(termos_text, self.styles['ContractNormal']))
        elements.append(Spacer(1, 20))
        
        # Rodapé
        elements.append(Paragraph("_" * 80, self.styles['ContractNormal']))
        rodape_text = f"""
        <font size="8">
        Documento gerado automaticamente pelo sistema Grupo JF Odontologia<br/>
        Data de geração: {datetime.now().strftime('%d/%m/%Y às %H:%M')}<br/>
        ID do Contrato: {contract_data.get('contract_id', '')}<br/>
        Este documento possui validade jurídica conforme Lei 14.063/2020
        </font>
        """
        elements.append(Paragraph(rodape_text, self.styles['Normal']))
        
        # Gerar PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes