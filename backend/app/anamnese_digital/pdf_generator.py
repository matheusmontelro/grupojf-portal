# app/anamnese_digital/pdf_generator.py

import base64
import io
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    CondPageBreak,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)


class AnamnesePDFGenerator:
    """Gera uma ficha clínica A4 compacta, legível e adequada para impressão."""

    INK = colors.HexColor("#1D2939")
    TEXT = colors.HexColor("#344054")
    MUTED = colors.HexColor("#667085")
    BORDER = colors.HexColor("#D0D5DD")
    SOFT_BORDER = colors.HexColor("#EAECF0")
    SURFACE = colors.HexColor("#F8FAFC")
    SURFACE_ALT = colors.HexColor("#F2F4F7")
    ALERT_BG = colors.HexColor("#FFF7E6")
    ALERT_TEXT = colors.HexColor("#7A4E00")
    WHITE = colors.white

    ANSWER_LABELS = {
        "sim": "Sim",
        "nao": "Não",
        "frio": "Ao frio",
        "quente": "Ao quente",
        "escova": "Ao escovar",
        "fio": "Com fio dental",
    }

    DISEASE_LABELS = {
        "pressao_alta": "Pressão alta",
        "diabetes": "Diabetes",
        "problemas_cardiacos": "Problemas cardíacos",
        "asma": "Asma / Bronquite",
        "hepatite": "Hepatite",
        "anemia": "Anemia",
        "nenhuma": "Nenhuma dessas",
    }

    STATUS_LABELS = {
        "rascunho": "Rascunho",
        "aguardando_assinatura": "Aguardando assinatura",
        "assinado": "Assinada",
        "expirado": "Expirada",
    }

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.assinaturas: List[Dict[str, Any]] = []
        self.doc_data: Dict[str, Any] = {}
        self.generated_at = datetime.now()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name="DocumentEyebrow",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=self.MUTED,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="DocumentTitle",
            parent=self.styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=self.INK,
            alignment=TA_LEFT,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="DocumentSubtitle",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=self.MUTED,
            spaceAfter=12,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionTitle",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=self.INK,
            spaceBefore=11,
            spaceAfter=6,
            keepWithNext=True,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHint",
            parent=self.styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=self.MUTED,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="Label",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=self.MUTED,
        ))
        self.styles.add(ParagraphStyle(
            name="Value",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=self.INK,
            wordWrap="CJK",
        ))
        self.styles.add(ParagraphStyle(
            name="Question",
            parent=self.styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=self.TEXT,
            wordWrap="CJK",
        ))
        self.styles.add(ParagraphStyle(
            name="Answer",
            parent=self.styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=self.INK,
            wordWrap="CJK",
        ))
        self.styles.add(ParagraphStyle(
            name="Small",
            parent=self.styles["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=self.MUTED,
            wordWrap="CJK",
        ))
        self.styles.add(ParagraphStyle(
            name="AlertTitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=self.ALERT_TEXT,
        ))
        self.styles.add(ParagraphStyle(
            name="AlertText",
            parent=self.styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=self.ALERT_TEXT,
            wordWrap="CJK",
        ))
        self.styles.add(ParagraphStyle(
            name="Declaration",
            parent=self.styles["Normal"],
            fontSize=8.5,
            leading=12,
            textColor=self.TEXT,
            alignment=TA_JUSTIFY,
        ))

    def generate(self, anamnese_data: Dict[str, Any]) -> bytes:
        """Gera o PDF da anamnese e retorna seus bytes."""
        self.doc_data = anamnese_data or {}
        self.generated_at = datetime.now()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=23 * mm,
            bottomMargin=18 * mm,
            title="Ficha de Anamnese",
            author="Grupo JF",
        )

        self._load_signatures(self.doc_data.get("id"))
        questionnaire = self.doc_data.get("dados_anamnese") or {}
        identification = questionnaire.get("dados_identificacao") or {}
        general_health = questionnaire.get("saude_geral") or {}
        oral_health = questionnaire.get("saude_bucal") or {}

        elements = []
        elements.extend(self._create_document_header(self.doc_data))
        elements.extend(self._create_identification_section(identification))
        elements.extend(self._create_clinical_summary(general_health, oral_health))
        elements.extend(self._create_general_health_section(general_health))
        elements.extend(self._create_oral_health_section(oral_health))

        if self.doc_data.get("observacoes"):
            elements.extend(self._create_observations_section(self.doc_data["observacoes"]))

        elements.extend(self._create_signatures_section(self.doc_data))

        doc.build(
            elements,
            onFirstPage=self._draw_page_frame,
            onLaterPages=self._draw_page_frame,
        )
        buffer.seek(0)
        return buffer.read()

    def _create_document_header(self, data: Dict[str, Any]) -> list:
        beneficiary_name = data.get("dependente_nome") or data.get("beneficiario_nome") or data.get("paciente_nome")
        status_value = getattr(data.get("status"), "value", data.get("status"))
        if not status_value and data.get("signed_at"):
            status_value = "assinado"
        status = self.STATUS_LABELS.get(str(status_value or "").lower(), self._display_value(status_value))
        document_id = f"#{data.get('id')}" if data.get("id") else "Sem número"
        filled_at = self._format_datetime(data.get("preenchida_em") or data.get("signed_at") or data.get("updated_at"))

        title = [
            Paragraph("DOCUMENTO CLÍNICO", self.styles["DocumentEyebrow"]),
            Paragraph("Ficha de Anamnese", self.styles["DocumentTitle"]),
            Paragraph(
                "Informações declaradas pelo paciente ou responsável para apoio ao atendimento odontológico.",
                self.styles["DocumentSubtitle"],
            ),
        ]

        metadata = [
            [self._label("ANAMNESE"), self._value(document_id), self._label("STATUS"), self._value(status)],
            [self._label("BENEFICIÁRIO"), self._value(beneficiary_name), self._label("UNIDADE"), self._value(data.get("unidade"))],
            [self._label("DATA"), self._value(filled_at), self._label("RESPONSÁVEL"), self._value(data.get("vendedor_nome"))],
        ]
        table = Table(metadata, colWidths=[27 * mm, 59 * mm, 27 * mm, 61 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.SURFACE),
            ("BOX", (0, 0), (-1, -1), 0.7, self.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, self.SOFT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        title.extend([table, Spacer(1, 3 * mm)])
        return title

    def _create_identification_section(self, beneficiary: Dict[str, Any]) -> list:
        elements = [self._section_title("Identificação")]

        if self.doc_data.get("dependente_nome"):
            beneficiary_data = dict(beneficiary)
            beneficiary_data.setdefault("nome", self.doc_data.get("dependente_nome"))
            beneficiary_data.setdefault("parentesco", self.doc_data.get("dependente_parentesco"))
            elements.append(self._identity_card("BENEFICIÁRIO", beneficiary_data, compact=True))
            elements.append(Spacer(1, 2.5 * mm))

            holder = dict(self.doc_data.get("dados_titular") or {})
            holder.setdefault("nome", self.doc_data.get("paciente_nome"))
            holder.setdefault("cpf", self.doc_data.get("paciente_cpf"))
            elements.append(self._identity_card("TITULAR RESPONSÁVEL", holder))
        else:
            patient = dict(beneficiary)
            patient.setdefault("nome", self.doc_data.get("paciente_nome"))
            patient.setdefault("cpf", self.doc_data.get("paciente_cpf"))
            elements.append(self._identity_card("PACIENTE", patient))

        return elements

    def _identity_card(self, heading: str, data: Dict[str, Any], compact: bool = False) -> Table:
        city_state = " / ".join(filter(None, [self._clean(data.get("cidade")), self._clean(data.get("estado"))]))
        address = self._clean(data.get("endereco") or data.get("logradouro"))
        number = self._clean(data.get("numero"))
        if address and number and number not in address:
            address = f"{address}, {number}"

        rows = [
            [Paragraph(escape(heading), self.styles["DocumentEyebrow"]), "", "", ""],
            [self._field("Nome", data.get("nome")), "", self._field("CPF", data.get("cpf")), self._field("RG", data.get("rg"))],
            [self._field("Nascimento", self._format_date(data.get("nascimento") or data.get("data_nascimento"))), self._field("Gênero", data.get("genero")), self._field("Parentesco", data.get("parentesco")), self._field("Profissão", data.get("profissao"))],
        ]

        if not compact:
            rows.extend([
                [self._field("Celular", data.get("celular")), self._field("Telefone", data.get("telefone_casa")), self._field("E-mail", data.get("email")), ""],
                [self._field("Endereço", address), "", self._field("Complemento", data.get("complemento")), self._field("Bairro", data.get("bairro"))],
                [self._field("Cidade / UF", city_state), self._field("CEP", data.get("cep")), self._field("Como conheceu", data.get("como_conheceu")), ""],
            ])

        table = Table(rows, colWidths=[48 * mm, 38 * mm, 46 * mm, 42 * mm], hAlign="LEFT")
        spans = [("SPAN", (0, 0), (3, 0)), ("SPAN", (0, 1), (1, 1))]
        if not compact:
            spans.extend([
                ("SPAN", (2, 3), (3, 3)),
                ("SPAN", (0, 4), (1, 4)),
                ("SPAN", (2, 5), (3, 5)),
            ])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.SURFACE_ALT),
            ("BOX", (0, 0), (-1, -1), 0.7, self.BORDER),
            ("INNERGRID", (0, 1), (-1, -1), 0.35, self.SOFT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            *spans,
        ]))
        return table

    def _create_clinical_summary(self, general: Dict[str, Any], oral: Dict[str, Any]) -> list:
        alerts = self._collect_clinical_alerts(general, oral)
        elements = [self._section_title("Resumo clínico")]

        if not alerts:
            content = [[Paragraph("Nenhum alerta clínico identificado nas respostas informadas.", self.styles["Answer"])]]
            background = self.SURFACE
            border = self.BORDER
        else:
            content = [[
                Paragraph(escape(title), self.styles["AlertTitle"]),
                Paragraph(escape(detail), self.styles["AlertText"]),
            ] for title, detail in alerts]
            background = self.ALERT_BG
            border = self.ALERT_TEXT

        table = Table(content, colWidths=[47 * mm, 127 * mm] if alerts else [174 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("BOX", (0, 0), (-1, -1), 0.7, border),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, border),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, self.SOFT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.extend([table, Spacer(1, 2 * mm)])
        return elements

    def _collect_clinical_alerts(self, general: Dict[str, Any], oral: Dict[str, Any]) -> List[Tuple[str, str]]:
        alerts: List[Tuple[str, str]] = []

        def is_yes(value: Any) -> bool:
            return str(value or "").strip().lower() == "sim"

        if is_yes(general.get("q1")):
            alerts.append(("Tratamento médico", self._display_value(general.get("q1_motivo"))))
        if is_yes(general.get("q2")):
            alerts.append(("Uso de medicamentos", self._display_value(general.get("q2_quais"))))

        diseases = [item for item in (general.get("doencas") or []) if item != "nenhuma"]
        if diseases:
            alerts.append(("Condições de saúde", ", ".join(self.DISEASE_LABELS.get(item, self._display_value(item)) for item in diseases)))
        if self._clean(general.get("outras_doencas")):
            alerts.append(("Outras condições", self._display_value(general.get("outras_doencas"))))
        if is_yes(general.get("q3")):
            pregnancy_detail = self._clean(general.get("q3_mes"))
            alerts.append(("Gestação", f"{pregnancy_detail} mês(es)" if pregnancy_detail else "Informada"))
        if is_yes(general.get("q4")):
            alerts.append(("Alergia medicamentosa", self._display_value(general.get("q4_quais"))))
        if is_yes(general.get("q6")):
            alerts.append(("Reação à anestesia", "Resposta positiva"))
        if is_yes(general.get("q7")):
            alerts.append(("Histórico de hemorragia", "Resposta positiva"))
        if str(general.get("q8") or "").strip().lower() == "nao":
            alerts.append(("Cicatrização", "Paciente informou cicatrização não normal"))
        if is_yes(general.get("q11")):
            alerts.append(("Tabagismo", "Paciente informou que fuma"))
        if is_yes(oral.get("q15")) or str(oral.get("q15") or "").lower() in {"escova", "fio"}:
            alerts.append(("Sangramento gengival", self._display_value(oral.get("q15_motivo") or oral.get("q15"))))
        if is_yes(oral.get("dor_ouvido")):
            alerts.append(("Dor próxima ao ouvido", "Resposta positiva"))
        return alerts

    def _create_general_health_section(self, data: Dict[str, Any]) -> list:
        questions: List[Tuple[str, Any, Any, str]] = [
            ("Está ou esteve recentemente em tratamento médico?", data.get("q1"), data.get("q1_motivo"), "Motivo"),
            ("Está tomando algum medicamento?", data.get("q2"), data.get("q2_quais"), "Medicamentos"),
            ("Está grávida?", data.get("q3"), data.get("q3_mes"), "Meses de gestação"),
            ("Tem alergia a algum medicamento?", data.get("q4"), data.get("q4_quais"), "Medicamentos"),
            ("Já foi operado?", data.get("q5"), None, ""),
            ("Teve alguma reação à anestesia?", data.get("q6"), None, ""),
            ("Já teve hemorragia?", data.get("q7"), None, ""),
            ("Sua cicatrização é normal?", data.get("q8"), None, ""),
            ("Fuma?", data.get("q11"), None, ""),
            ("Consome bebidas alcoólicas com frequência?", data.get("q12"), None, ""),
            ("Pratica atividade física regularmente?", data.get("q13"), None, ""),
            ("Está amamentando?", data.get("q14"), None, ""),
        ]

        elements = [
            CondPageBreak(36 * mm),
            self._section_title("Saúde geral"),
            Paragraph("Respostas declaradas no questionário de saúde.", self.styles["SectionHint"]),
            self._question_table(questions),
            Spacer(1, 2 * mm),
            self._disease_table(data),
        ]
        return elements

    def _disease_table(self, data: Dict[str, Any]) -> Table:
        selected = set(data.get("doencas") or [])
        cells = []
        for key, label in self.DISEASE_LABELS.items():
            informed = key in selected
            status = "INFORMADA" if informed else "NÃO INFORMADA"
            status_color = self.ALERT_TEXT if informed and key != "nenhuma" else self.MUTED
            cells.append(Paragraph(
                f'<font color="{status_color.hexval()}"><b>{status}</b></font><br/>{escape(label)}',
                self.styles["Small"],
            ))

        while len(cells) % 3:
            cells.append("")
        rows = [
            [Paragraph("CONDIÇÕES DE SAÚDE", self.styles["DocumentEyebrow"]), "", ""],
            *[cells[index:index + 3] for index in range(0, len(cells), 3)],
        ]
        if self._clean(data.get("outras_doencas")):
            rows.append([self._field("Outras condições", data.get("outras_doencas")), "", ""])

        table = Table(rows, colWidths=[58 * mm, 58 * mm, 58 * mm], hAlign="LEFT")
        styles = [
            ("SPAN", (0, 0), (2, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), self.SURFACE_ALT),
            ("BOX", (0, 0), (-1, -1), 0.7, self.BORDER),
            ("INNERGRID", (0, 1), (-1, -1), 0.35, self.SOFT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        if self._clean(data.get("outras_doencas")):
            styles.append(("SPAN", (0, -1), (2, -1)))
        table.setStyle(TableStyle(styles))
        return table

    def _create_oral_health_section(self, data: Dict[str, Any]) -> list:
        questions: List[Tuple[str, Any, Any, str]] = [
            ("Suas gengivas sangram facilmente?", data.get("q15"), data.get("q15_motivo"), "Observação"),
            ("Sente sensibilidade nos dentes?", data.get("q16"), None, ""),
            ("Range os dentes?", data.get("q17"), None, ""),
            ("Morde lábios, bochechas ou objetos?", data.get("morde_labios"), None, ""),
            ("Já fez tratamento ortodôntico?", data.get("q18"), None, ""),
            ("Está satisfeito com a aparência dos dentes?", data.get("q19"), None, ""),
            ("Sente dor no ouvido ou próximo dele?", data.get("dor_ouvido"), None, ""),
            ("Outros problemas de saúde bucal", data.get("outros_problemas"), None, ""),
        ]
        return [
            CondPageBreak(34 * mm),
            self._section_title("Saúde bucal"),
            Paragraph("Hábitos, sintomas e histórico odontológico informados.", self.styles["SectionHint"]),
            self._question_table(questions),
        ]

    def _question_table(self, questions: Sequence[Tuple[str, Any, Any, str]]) -> Table:
        rows = [[
            Paragraph("PERGUNTA", self.styles["DocumentEyebrow"]),
            Paragraph("RESPOSTA", self.styles["DocumentEyebrow"]),
        ]]
        for question, answer, detail, detail_label in questions:
            answer_text = f"<b>{escape(self._display_value(answer))}</b>"
            if self._clean(detail):
                answer_text += f'<br/><font color="{self.MUTED.hexval()}">{escape(detail_label)}: {escape(self._display_value(detail))}</font>'
            rows.append([
                Paragraph(escape(question), self.styles["Question"]),
                Paragraph(answer_text, self.styles["Answer"]),
            ])

        table = Table(rows, colWidths=[119 * mm, 55 * mm], repeatRows=1, splitByRow=1, hAlign="LEFT")
        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), self.SURFACE_ALT),
            ("BOX", (0, 0), (-1, -1), 0.7, self.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, self.SOFT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
        ]
        for row_index in range(2, len(rows), 2):
            style_commands.append(("BACKGROUND", (0, row_index), (-1, row_index), self.SURFACE))
        table.setStyle(TableStyle(style_commands))
        return table

    def _create_observations_section(self, observations: str) -> list:
        table = Table(
            [[Paragraph(escape(self._display_value(observations)), self.styles["Answer"])]],
            colWidths=[174 * mm],
            hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.SURFACE),
            ("BOX", (0, 0), (-1, -1), 0.7, self.BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return [CondPageBreak(28 * mm), self._section_title("Observações do profissional"), table]

    def _create_signatures_section(self, data: Dict[str, Any]) -> list:
        elements = [CondPageBreak(54 * mm), self._section_title("Declaração e assinaturas")]
        if self.doc_data.get("dependente_nome"):
            declaration = (
                f"Declaro que as informações prestadas sobre {self.doc_data.get('dependente_nome')} são verdadeiras "
                "e assumo responsabilidade pela omissão de informações que possam interferir no planejamento "
                "ou tratamento odontológico do dependente."
            )
        else:
            declaration = (
                "Declaro que as informações prestadas são verdadeiras e assumo responsabilidade pela omissão "
                "de informações que possam interferir no planejamento ou tratamento odontológico."
            )

        declaration_table = Table(
            [[Paragraph(escape(declaration), self.styles["Declaration"])]],
            colWidths=[174 * mm],
            hAlign="LEFT",
        )
        declaration_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.SURFACE),
            ("BOX", (0, 0), (-1, -1), 0.7, self.BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.extend([declaration_table, Spacer(1, 4 * mm)])

        if self.assinaturas:
            for signature in self.assinaturas:
                elements.append(self._digital_signature_block(signature))
                elements.append(Spacer(1, 3 * mm))
        else:
            signed_at = self._format_datetime(data.get("signed_at"))
            if data.get("signed_at"):
                elements.append(Paragraph(f"Registro de assinatura: {escape(signed_at)}", self.styles["Small"]))
                elements.append(Spacer(1, 5 * mm))
            elements.append(self._traditional_signature_block())

        return elements

    def _digital_signature_block(self, signature: Dict[str, Any]) -> KeepTogether:
        signed_at = self._format_datetime(signature.get("created_at"))
        metadata = Table([
            [
                self._field("Tipo", str(signature.get("tipo") or "Assinante").title()),
                self._field("Nome", signature.get("nome")),
                self._field("CPF", signature.get("cpf")),
                self._field("Data", signed_at),
            ]
        ], colWidths=[32 * mm, 65 * mm, 38 * mm, 39 * mm], hAlign="LEFT")
        metadata.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.SURFACE_ALT),
            ("BOX", (0, 0), (-1, -1), 0.7, self.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, self.SOFT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        photo = self._process_base64_image(signature.get("foto_selfie"), 46 * mm, 42 * mm)
        signed_image = self._process_base64_image(signature.get("assinatura_digital"), 72 * mm, 34 * mm)
        photo_cell = [Paragraph("SELFIE DE VALIDAÇÃO", self.styles["DocumentEyebrow"]), photo or Paragraph("Imagem não disponível", self.styles["Small"])]
        signature_cell = [Paragraph("ASSINATURA DIGITAL", self.styles["DocumentEyebrow"]), signed_image or Paragraph("Imagem não disponível", self.styles["Small"])]
        images = Table([[photo_cell, signature_cell]], colWidths=[67 * mm, 107 * mm], hAlign="LEFT")
        images.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.7, self.BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, self.SOFT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return KeepTogether([metadata, images])

    def _traditional_signature_block(self) -> Table:
        signer_label = "Assinatura do responsável" if self.doc_data.get("dependente_nome") else "Assinatura do paciente"
        table = Table(
            [["", ""], [Paragraph(signer_label, self.styles["Small"]), Paragraph("Assinatura do profissional", self.styles["Small"])]],
            colWidths=[82 * mm, 82 * mm],
            rowHeights=[16 * mm, 7 * mm],
            hAlign="CENTER",
        )
        table.setStyle(TableStyle([
            ("LINEABOVE", (0, 1), (-1, 1), 0.7, self.TEXT),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        return table

    def _draw_page_frame(self, canvas, doc):
        canvas.saveState()
        width, height = A4
        document_id = f"#{self.doc_data.get('id')}" if self.doc_data.get("id") else ""
        beneficiary = self._clean(
            self.doc_data.get("dependente_nome")
            or self.doc_data.get("beneficiario_nome")
            or self.doc_data.get("paciente_nome")
        )

        canvas.setStrokeColor(self.BORDER)
        canvas.setLineWidth(0.45)
        canvas.line(18 * mm, height - 16 * mm, width - 18 * mm, height - 16 * mm)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(self.MUTED)
        canvas.drawString(18 * mm, height - 12.5 * mm, "FICHA DE ANAMNESE")
        if document_id:
            canvas.setFont("Helvetica", 7)
            canvas.drawRightString(width - 18 * mm, height - 12.5 * mm, f"Documento {document_id}")

        canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
        canvas.setFont("Helvetica", 6.8)
        canvas.setFillColor(self.MUTED)
        footer_name = beneficiary[:62] if beneficiary else "Documento clínico"
        canvas.drawString(18 * mm, 8.8 * mm, footer_name)
        emitted = self.generated_at.strftime("Emitido em %d/%m/%Y às %H:%M")
        canvas.drawCentredString(width / 2, 8.8 * mm, emitted)
        canvas.drawRightString(width - 18 * mm, 8.8 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    def _section_title(self, text: str) -> KeepTogether:
        line = Table([[""]], colWidths=[174 * mm], rowHeights=[0.6 * mm], hAlign="LEFT")
        line.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), self.INK)]))
        return KeepTogether([Paragraph(escape(text), self.styles["SectionTitle"]), line, Spacer(1, 1.5 * mm)])

    def _field(self, label: str, value: Any) -> list:
        return [self._label(label.upper()), self._value(value)]

    def _label(self, value: Any) -> Paragraph:
        return Paragraph(escape(self._display_value(value, fallback="")), self.styles["Label"])

    def _value(self, value: Any) -> Paragraph:
        return Paragraph(escape(self._display_value(value)), self.styles["Value"])

    def _display_value(self, value: Any, fallback: str = "Não informado") -> str:
        if value is None:
            return fallback
        if isinstance(value, (list, tuple, set)):
            values = [self._display_value(item, fallback="") for item in value]
            return ", ".join(filter(None, values)) or fallback
        normalized = str(value).strip()
        if not normalized:
            return fallback
        return self.ANSWER_LABELS.get(normalized.lower(), normalized)

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    def _format_datetime(self, value: Any) -> str:
        if not value:
            return "Não informado"
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y às %H:%M")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.strftime("%d/%m/%Y às %H:%M")
        except (TypeError, ValueError):
            return self._display_value(value)

    def _format_date(self, value: Any) -> str:
        if not value:
            return "Não informado"
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        normalized = str(value).strip()
        for parser in (
            lambda item: datetime.fromisoformat(item.replace("Z", "+00:00")),
            lambda item: datetime.strptime(item, "%d/%m/%Y"),
        ):
            try:
                return parser(normalized).strftime("%d/%m/%Y")
            except (TypeError, ValueError):
                continue
        return normalized or "Não informado"

    def _load_signatures(self, anamnese_id: Optional[int]):
        """Carrega evidências de assinatura, quando a anamnese está persistida."""
        if not anamnese_id:
            return

        try:
            from app.database.db import DatabaseConnection

            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                        SELECT tipo_assinatura, nome_assinante, cpf_assinante,
                               foto_selfie, assinatura_digital, created_at
                        FROM anamnese_assinaturas
                        WHERE anamnese_id = %s
                        ORDER BY created_at
                    """,
                    (anamnese_id,),
                )
                self.assinaturas = [
                    {
                        "tipo": row[0],
                        "nome": row[1],
                        "cpf": row[2],
                        "foto_selfie": row[3],
                        "assinatura_digital": row[4],
                        "created_at": row[5],
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as exc:
            logger.error("Erro ao carregar assinaturas: %s", exc)
            self.assinaturas = []

    def _process_base64_image(
        self,
        base64_data: Optional[str],
        max_width: float = 60 * mm,
        max_height: float = 60 * mm,
    ) -> Optional[Image]:
        """Converte uma imagem base64 preservando sua proporção."""
        try:
            if not base64_data:
                return None
            encoded = base64_data.split(",", 1)[1] if "," in base64_data else base64_data
            image_data = base64.b64decode(encoded)
            pil_image = PILImage.open(io.BytesIO(image_data))
            width, height = pil_image.size
            if not width or not height:
                return None

            scale = min(max_width / width, max_height / height)
            rendered_width = width * scale
            rendered_height = height * scale
            image_buffer = io.BytesIO()
            pil_image.save(image_buffer, format="PNG")
            image_buffer.seek(0)
            return Image(image_buffer, width=rendered_width, height=rendered_height)
        except Exception as exc:
            logger.error("Erro ao processar imagem base64: %s", exc)
            return None
