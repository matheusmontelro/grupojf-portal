"""Cifragem Fernet da apiKey de subcontas Asaas.

A apiKey de cada subconta Asaas (PF ou empresa) e secreta: ela nunca deve ser
logada, retornada em leituras de API ou commitada. Este modulo fornece
``encrypt_api_key``/``decrypt_api_key`` que cifram/decifram o plaintext usando
uma chave Fernet lida da variavel de ambiente ``ASAAS_ACCOUNT_API_KEY_SECRET``.

A chave Fernet deve ser gerada uma unica vez e armazenada como segredo de
operacao, fornecido ao processo por variavel de ambiente, nunca no repositorio.
Exemplo de geracao::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Seguranca:
  * O import do ``cryptography`` e lazy: so acontece quando uma funcao e
    chamada, evitando falhar o import do pacote quando a dependencia nao esta
    instalada em ambientes que nao usam Asaas.
  * A chave e validada apenas em runtime de escrita/leitura, nunca no import.
  * Falhar fechado: se o segredo estiver ausente ou a chave for invalida, a
    excecao ``AsaasAccountSecretError`` e levantada; nada e retornado nem
    logado.
  * As funcoes sao puras e nao imprimem o plaintext.
"""

from __future__ import annotations

import os
from typing import Any

_SECRET_ENV_VAR = "ASAAS_ACCOUNT_API_KEY_SECRET"


class AsaasAccountSecretError(RuntimeError):
    """Falha de configuracao/uso da chave Fernet de subcontas Asaas.

    Nunca carrega o valor da chave nem o plaintext da apiKey.
    """


def _load_fernet() -> Any:
    """Le ``ASAAS_ACCOUNT_API_KEY_SECRET`` e devolve um ``Fernet`` valido.

    Importa ``cryptography`` de forma lazy e valida a chave em runtime. Levanta
    ``AsaasAccountSecretError`` se a variavel estiver ausente/vazia ou se a
    chave nao for compativel com Fernet.
    """
    raw_secret = os.getenv(_SECRET_ENV_VAR, "")
    if not raw_secret or not raw_secret.strip():
        raise AsaasAccountSecretError(
            f"{_SECRET_ENV_VAR} ausente ou vazio; configure a chave Fernet."
        )
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise AsaasAccountSecretError(
            "biblioteca cryptography indisponivel no ambiente"
        ) from exc
    try:
        return Fernet(raw_secret.encode("utf-8"))
    except Exception as exc:
        raise AsaasAccountSecretError(
            f"{_SECRET_ENV_VAR} nao e uma chave Fernet valida"
        ) from exc


def encrypt_api_key(plain: str) -> str:
    """Cifra uma apiKey de subconta Asaas e devolve o token Fernet (str).

    Nunca loga o plaintext. Levanta ``AsaasAccountSecretError`` se a chave
    Fernet estiver ausente ou invalida.
    """
    if plain is None:
        raise AsaasAccountSecretError("apiKey plaintext nao pode ser None")
    if not isinstance(plain, str) or not plain:
        raise AsaasAccountSecretError("apiKey plaintext nao pode ser vazio")
    fernet = _load_fernet()
    return fernet.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_api_key(token: str) -> str:
    """Decifra um token Fernet e devolve a apiKey plaintext (str).

    Nunca loga o plaintext. Levanta ``AsaasAccountSecretError`` se a chave
    Fernet estiver ausente/invalida ou se o token for invalido/expirado.
    """
    if token is None:
        raise AsaasAccountSecretError("token cifrado nao pode ser None")
    if not isinstance(token, str) or not token:
        raise AsaasAccountSecretError("token cifrado nao pode ser vazio")
    fernet = _load_fernet()
    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise AsaasAccountSecretError("falha ao decifrar apiKey de subconta") from exc
