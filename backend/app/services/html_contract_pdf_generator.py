"""
Gerador de PDF a partir do HTML real do contrato assinado
Converte o template HTML original para PDF mantendo a formatação
"""

import io
import base64
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from ..database.db import DatabaseConnection

logger = logging.getLogger(__name__)

class HTMLContractPDFGenerator:
    """Gerador de PDF a partir do HTML do contrato assinado"""
    
    def __init__(self):
        self.font_config = FontConfiguration()
    
    def _get_signed_contract_html(self, access_token: str) -> Optional[str]:
        """Busca o HTML do contrato assinado via service"""
        try:
            from ..digital_contracts.service import DigitalContractService
            service = DigitalContractService()
            
            # Buscar odontograma_id pelo access_token
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT odontograma_id 
                    FROM digital_contracts 
                    WHERE access_token = %s AND status = 'signed'
                """, (access_token,))
                
                result = cursor.fetchone()
                if not result:
                    return None
                    
                odontograma_id = result[0]
            
            # Usar o service para obter dados completos e HTML
            signed_data = service.get_signed_contract_data(odontograma_id)
            return signed_data.get('contract_html')
            
        except Exception as e:
            logger.error("Falha ao buscar HTML do contrato (%s)", type(e).__name__)
            return None
    
    def _save_temp_image(self, base64_data: str, prefix: str) -> str:
        """Salva imagem base64 EXATAMENTE como está - SEM processamento"""
        import tempfile
        import base64
        
        try:
            if not base64_data:
                return ""
            
            # Remove o prefixo data:image/...;base64, se presente
            if ',' in base64_data:
                header, base64_data = base64_data.split(',', 1)
            
            # Decodifica e salva DIRETO - sem PIL, sem conversão
            image_bytes = base64.b64decode(base64_data)
            
            # Criar arquivo temporário
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix='.jpg', 
                prefix=f'{prefix}_raw_'
            )
            temp_file.write(image_bytes)
            temp_file.close()
            
            logger.info(f"📸 {prefix} salva crua: {temp_file.name} ({len(image_bytes)} bytes)")
            return temp_file.name
            
        except Exception as e:
            logger.error("Falha ao salvar imagem temporária (%s)", type(e).__name__)
            return ""
    
    def _cleanup_temp_files(self, html_content: str):
        """Remove arquivos temporários de imagens criados"""
        import os
        import re
        
        try:
            # Encontrar todos os caminhos de arquivo temporários no HTML
            temp_paths = re.findall(r'file://(/tmp/[^"]+)', html_content)
            
            for temp_path in temp_paths:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                        logger.debug(f"Arquivo temporário removido: {temp_path}")
                except Exception as e:
                    logger.warning("Falha ao remover arquivo temporário (%s)", type(e).__name__)
                    
        except Exception as e:
            logger.error("Falha durante limpeza de arquivos temporários (%s)", type(e).__name__)
    
    def _add_signature_to_html(self, html: str, contract_data: Dict[str, Any]) -> str:
        """Adiciona selfie e assinatura ao HTML usando arquivos temporários"""
        try:
            signature_section = ""
            
            # Salvar imagens cruas como arquivos temporários
            selfie_path = self._save_temp_image(contract_data.get('selfie', ''), 'selfie')
            signature_path = self._save_temp_image(contract_data.get('signature', ''), 'signature')
            
            # Criar seção de validação digital
            if selfie_path or signature_path:
                signature_section += """
                <div style="page-break-before: always; padding: 20px;">
                    <h2 style="text-align: center; color: #1e40af;">Validação Digital</h2>
                    <table style="width: 100%;">
                        <tr>
                """
                
                if selfie_path:
                    signature_section += f"""
                            <td style="text-align: center; width: 50%;">
                                <h3>Selfie de Validação</h3>
                                <img src="file://{selfie_path}" style="max-width: 200px; max-height: 200px; border: 1px solid #ccc;">
                            </td>
                    """
                
                if signature_path:
                    signature_section += f"""
                            <td style="text-align: center; width: 50%;">
                                <h3>Assinatura Digital</h3>
                                <img src="file://{signature_path}" style="max-width: 300px; max-height: 100px; border: 1px solid #ccc;">
                            </td>
                    """
                
                signature_section += """
                        </tr>
                    </table>
                """
            
            # Adicionar informações de auditoria
            device_info = contract_data.get('device_info', {})
            if device_info:
                signature_section += f"""
                    <div style="margin-top: 30px; padding: 15px; background: #f8f9fa; border-left: 4px solid #1e40af;">
                        <h4>Informações de Auditoria</h4>
                        <p><strong>Dispositivo:</strong> {device_info.get('device_type', 'N/A').title()}</p>
                        <p><strong>Navegador:</strong> {device_info.get('user_agent', 'N/A')[:80]}...</p>
                        <p><strong>Data/Hora:</strong> {device_info.get('timestamp', 'N/A')}</p>
                        <p><strong>Resolução:</strong> {device_info.get('screen_resolution', 'N/A')}</p>
                    </div>
                """
            
            signature_section += "</div>"
            
            # Inserir antes do fechamento do body
            if "</body>" in html:
                html = html.replace("</body>", signature_section + "</body>")
            else:
                html += signature_section
                
            return html
            
        except Exception as e:
            logger.error("Falha ao adicionar assinatura ao HTML (%s)", type(e).__name__)
            return html
    
    def _enhance_html_for_pdf(self, html: str) -> str:
        """Melhora o HTML para conversão PDF"""
        try:
            # CSS para melhorar a conversão PDF
            pdf_css = """
            <style>
            @media print {
                .no-print { display: none !important; }
                
                body {
                    font-family: 'DejaVu Sans', Arial, sans-serif;
                    font-size: 12px;
                    line-height: 1.4;
                }
                
                .contract-header {
                    text-align: center;
                    margin-bottom: 20px;
                }
                
                .signature-section {
                    page-break-inside: avoid;
                    margin-top: 30px;
                }
                
                img {
                    max-width: 100%;
                    height: auto;
                }
                
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                }
                
                th, td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                
                th {
                    background-color: #f5f5f5;
                    font-weight: bold;
                }
                
                .page-break {
                    page-break-before: always;
                }
            }
            
            /* Estilos gerais */
            body {
                margin: 0;
                padding: 20px;
                font-family: 'DejaVu Sans', Arial, sans-serif;
            }
            
            .contract-title {
                font-size: 18px;
                font-weight: bold;
                text-align: center;
                color: #1e40af;
                margin-bottom: 20px;
            }
            
            .signature-validation {
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
            }
            </style>
            """
            
            # Inserir CSS no head
            if "<head>" in html:
                html = html.replace("<head>", f"<head>{pdf_css}")
            else:
                html = f"<html><head>{pdf_css}</head><body>" + html + "</body></html>"
            
            return html
            
        except Exception as e:
            logger.error("Falha ao preparar HTML para PDF (%s)", type(e).__name__)
            return html
    
    def generate_pdf_from_contract_html(self, access_token: str) -> bytes:
        """
        Gera PDF a partir do HTML real do contrato assinado
        
        Args:
            access_token: Token de acesso do contrato
            
        Returns:
            bytes: PDF gerado
        """
        try:
            logger.info("Geração de PDF de contrato iniciada")
            
            # Buscar dados do contrato
            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.id, c.contract_data, c.signed_at,
                           p.nome_paciente, p.cpf_cnpj
                    FROM digital_contracts c
                    JOIN pacientes p ON c.paciente_id = p.paciente_id
                    WHERE c.access_token = %s AND c.status = 'signed'
                """, (access_token,))
                
                result = cursor.fetchone()
                if not result:
                    raise Exception("Contrato não encontrado")
                
                contract_id, contract_json_data, signed_at, paciente_nome, paciente_cpf = result
            
            # Extrair dados do JSON
            contract_data = contract_json_data if contract_json_data else {}
            contract_data.update({
                'contract_id': contract_id,
                'data_assinatura': signed_at,
                'paciente_nome': paciente_nome,
                'paciente_cpf': paciente_cpf
            })
            
            # Buscar HTML original do contrato
            html_content = self._get_signed_contract_html(access_token)
            if not html_content:
                raise Exception("HTML do contrato não encontrado")
            
            logger.info(f"HTML do contrato obtido: {len(html_content)} caracteres")
            
            # Adicionar validação digital (selfie e assinatura)
            html_with_signatures = self._add_signature_to_html(html_content, contract_data)
            
            # Melhorar HTML para PDF
            final_html = self._enhance_html_for_pdf(html_with_signatures)
            
            # Gerar PDF usando WeasyPrint
            logger.info("Convertendo HTML para PDF...")
            pdf_document = HTML(string=final_html, base_url=".")
            pdf_bytes = pdf_document.write_pdf(font_config=self.font_config)
            
            # Limpar arquivos temporários das imagens
            self._cleanup_temp_files(final_html)
            
            logger.info(f"✅ PDF gerado com sucesso: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error("Falha ao gerar PDF do contrato (%s)", type(e).__name__)
            raise
