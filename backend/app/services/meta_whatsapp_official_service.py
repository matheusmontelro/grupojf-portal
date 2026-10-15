import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

import requests


logger = logging.getLogger(__name__)

AUTHENTICATION_TEMPLATE_NAME = "codigo_redefinicao_senha"
ANAMNESIS_TEMPLATE_NAME = "link_anamnese_digital"
CONTRACT_TEMPLATE_NAME = "link_contrato_digital"
TEMPLATE_LANGUAGE = "pt_BR"


class WhatsAppConfigurationError(RuntimeError):
    """Configuração oficial da Meta incompleta."""


class WhatsAppDeliveryError(RuntimeError):
    """A Meta não aceitou o envio da mensagem."""


@dataclass(frozen=True)
class WhatsAppSender:
    unit_key: str
    phone_number_id: str


_UNIT_ENV = {
    "Nova Iguaçu 1": "META_WHATSAPP_NI_PHONE_NUMBER_ID",
    "São João de Meriti": "META_WHATSAPP_SJM_PHONE_NUMBER_ID",
    "Vilar dos Teles": "META_WHATSAPP_VILAR_PHONE_NUMBER_ID",
}

_UNIT_DISPLAY_NAME = {
    "Nova Iguaçu 1": "Odontocompany Nova Iguaçu",
    "São João de Meriti": "Odontocompany São João de Meriti",
    "Vilar dos Teles": "Odontocompany Vilar dos Teles",
}


def resolve_sender_unit(
    role: Optional[str],
    unit: Optional[str],
    recovery_unit: Optional[str] = None,
) -> Optional[str]:
    normalized_role = (role or "").strip().casefold()
    if normalized_role in {"master", "administrador", "admin"}:
        return "Nova Iguaçu 1"

    if unit in _UNIT_ENV:
        return unit
    if recovery_unit in _UNIT_ENV:
        return recovery_unit
    return None


def get_sender(unit_key: str) -> WhatsAppSender:
    env_name = _UNIT_ENV.get(unit_key)
    if not env_name:
        raise WhatsAppConfigurationError("Unidade sem remetente oficial configurado")

    phone_number_id = os.getenv(env_name, "").strip()
    if not phone_number_id:
        raise WhatsAppConfigurationError("Phone Number ID não configurado")
    return WhatsAppSender(unit_key=unit_key, phone_number_id=phone_number_id)


def get_unit_display_name(unit_key: str) -> str:
    display_name = _UNIT_DISPLAY_NAME.get(unit_key)
    if not display_name:
        raise WhatsAppConfigurationError("Unidade sem nome de clínica configurado")
    return display_name


def normalize_recipient_phone(country_code: str, area_code: str, number: str) -> str:
    return normalize_recipient_value(f"{country_code}{area_code}{number}")


def normalize_recipient_value(value: str, default_country_code: str = "55") -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) in {10, 11}:
        digits = f"{default_country_code}{digits}"
    if not 10 <= len(digits) <= 15:
        raise WhatsAppConfigurationError("Telefone cadastrado inválido")
    return digits


def _send_template_message(
    *,
    recipient: str,
    sender_unit: str,
    template_name: str,
    body_parameters: list[str],
    button_parameter: str,
) -> str:
    token = os.getenv("META_WHATSAPP_ACCESS_TOKEN", "").strip()
    version = os.getenv("META_WHATSAPP_GRAPH_API_VERSION", "v23.0").strip()
    if not token:
        raise WhatsAppConfigurationError("Token oficial da Meta não configurado")

    sender = get_sender(sender_unit)
    url = f"https://graph.facebook.com/{version}/{sender.phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": TEMPLATE_LANGUAGE},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": value}
                        for value in body_parameters
                    ],
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": button_parameter}],
                },
            ],
        },
    }

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise WhatsAppDeliveryError("Falha de conexão com a Meta") from exc

    if response.status_code >= 400:
        logger.warning(
            "Meta recusou template (status=%s, unidade=%s, template=%s)",
            response.status_code,
            sender_unit,
            template_name,
        )
        raise WhatsAppDeliveryError("Meta recusou a mensagem")

    try:
        return response.json()["messages"][0]["id"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise WhatsAppDeliveryError("Resposta inesperada da Meta") from exc


def send_authentication_code(recipient: str, code: str, sender_unit: str) -> str:
    return _send_template_message(
        recipient=recipient,
        sender_unit=sender_unit,
        template_name=AUTHENTICATION_TEMPLATE_NAME,
        body_parameters=[code],
        button_parameter=code,
    )


def send_anamnesis_link(
    recipient: str,
    recipient_name: str,
    beneficiary_name: str,
    token: str,
    sender_unit: str,
) -> str:
    return _send_template_message(
        recipient=recipient,
        sender_unit=sender_unit,
        template_name=ANAMNESIS_TEMPLATE_NAME,
        body_parameters=[
            recipient_name,
            beneficiary_name,
            get_unit_display_name(sender_unit),
        ],
        button_parameter=token,
    )


def send_contract_link(
    recipient: str,
    recipient_name: str,
    beneficiary_name: str,
    token: str,
    sender_unit: str,
) -> str:
    return _send_template_message(
        recipient=recipient,
        sender_unit=sender_unit,
        template_name=CONTRACT_TEMPLATE_NAME,
        body_parameters=[
            recipient_name,
            beneficiary_name,
            get_unit_display_name(sender_unit),
        ],
        button_parameter=token,
    )
