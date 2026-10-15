"""Testes da cifra Fernet da apiKey de subcontas Asaas.

Cobre ``app.security.asaas_account_secret``:

* segredo ausente/vazio -> ``AsaasAccountSecretError`` (fail closed);
* segredo que nao e chave Fernet valida -> erro;
* round-trip de apiKey curta/longa (idempotencia da cifra);
* decrypt de token invalido/corrompido -> erro (nunca devolve garbage);
* decrypt com segredo DIFERENTE do que cifrou -> erro (nao decripta
  silenciosamente -- garante que a chave e o segredo de operacao);
* encrypt de string vazia/None -> erro.

Importante para o Hardening: estes testes protegem dinheiro -- a apiKey
cifrada permite operar a subconta Asaas; uma decriptacao silenciosa com a
chave errada devolveria garbage que poderia passar por credencial.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.security import asaas_account_secret as secret
from app.security.asaas_account_secret import (
    AsaasAccountSecretError,
    decrypt_api_key,
    encrypt_api_key,
)


SECRET_ENV = "ASAAS_ACCOUNT_API_KEY_SECRET"


@pytest.fixture
def fernet_secret(monkeypatch):
    """Garante uma chave Fernet valida e isolada por teste."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv(SECRET_ENV, key)
    return key


# ---------------------------------------------------------------------------
# Segredo ausente / invalido -> fail closed.
# ---------------------------------------------------------------------------


def test_encrypt_com_segredo_ausente_falha_fechado(monkeypatch):
    monkeypatch.delenv(SECRET_ENV, raising=False)
    with pytest.raises(AsaasAccountSecretError) as raised:
        encrypt_api_key("qualquer-apikey")
    assert SECRET_ENV in str(raised.value)


def test_decrypt_com_segredo_ausente_falha_fechado(monkeypatch):
    monkeypatch.delenv(SECRET_ENV, raising=False)
    with pytest.raises(AsaasAccountSecretError):
        decrypt_api_key("algum-token")


def test_segredo_que_nao_e_chave_fernet_falha_fechado(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, "isto-nao-e-uma-chave-fernet-valida")
    with pytest.raises(AsaasAccountSecretError):
        encrypt_api_key("k")
    with pytest.raises(AsaasAccountSecretError):
        decrypt_api_key("t")


def test_segredo_apenas_espacos_falha_fechado(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, "   ")
    with pytest.raises(AsaasAccountSecretError):
        encrypt_api_key("k")


# ---------------------------------------------------------------------------
# Round-trip curto / longo.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "plain",
    [
        "a",  # 1 char
        "asaas-key-123",  # tipico
        "x" * 500,  # apiKey longa
    ],
)
def test_round_trip_encrypt_decrypt_preserva_plaintext(fernet_secret, plain):
    token = encrypt_api_key(plain)
    assert token != plain, "token cifrado nao pode igualar o plaintext"
    assert decrypt_api_key(token) == plain


def test_token_cifrado_e_diferente_por_chamada(fernet_secret):
    """Fernet inclui timestamp/IV: cifrar a mesma apiKey duas vezes gera
    tokens distintos -- protege contra deteccao de repeticao no storage.
    """
    a = encrypt_api_key("mesma-key")
    b = encrypt_api_key("mesma-key")
    assert a != b
    assert decrypt_api_key(a) == "mesma-key"
    assert decrypt_api_key(b) == "mesma-key"


# ---------------------------------------------------------------------------
# Decrypt de garbage / chave errada -> erro, nunca garbage.
# ---------------------------------------------------------------------------


def test_decrypt_token_corrompido_falha_fechado(fernet_secret):
    with pytest.raises(AsaasAccountSecretError):
        decrypt_api_key("nao-e-um-token-fernet-valido==")


def test_decrypt_token_truncado_falha_fechado(fernet_secret):
    token = encrypt_api_key("k")
    # Trunca o token: deve falhar ao decifrar, nao devolver parcial.
    with pytest.raises(AsaasAccountSecretError):
        decrypt_api_key(token[:-4])


def test_decrypt_com_segredo_diferente_falha_fechado(monkeypatch):
    """Cifra com a chave A e tenta decifrar com a chave B: o Fernet rejeita
    (assinatura invalida) -- garante que a chave de operacao e unica fonte
    de verdade. Mutante que ignore a validacao de assinatura seria detectado.
    """
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()
    monkeypatch.setenv(SECRET_ENV, key_a)
    token = encrypt_api_key("segredo-da-subconta")
    monkeypatch.setenv(SECRET_ENV, key_b)
    with pytest.raises(AsaasAccountSecretError):
        decrypt_api_key(token)


# ---------------------------------------------------------------------------
# Entradas invalidas de plaintext/token.
# ---------------------------------------------------------------------------


def test_encrypt_none_falha(fernet_secret):
    with pytest.raises(AsaasAccountSecretError):
        encrypt_api_key(None)  # type: ignore[arg-type]


def test_encrypt_string_vazia_falha(fernet_secret):
    with pytest.raises(AsaasAccountSecretError):
        encrypt_api_key("")


def test_encrypt_nao_str_falha(fernet_secret):
    with pytest.raises(AsaasAccountSecretError):
        encrypt_api_key(12345)  # type: ignore[arg-type]


def test_decrypt_none_falha(fernet_secret):
    with pytest.raises(AsaasAccountSecretError):
        decrypt_api_key(None)  # type: ignore[arg-type]


def test_decrypt_string_vazia_falha(fernet_secret):
    with pytest.raises(AsaasAccountSecretError):
        decrypt_api_key("")


# ---------------------------------------------------------------------------
# Garantia de que a excecao interna do Fernet e envelopada.
# ---------------------------------------------------------------------------


def test_excecao_interna_do_fernet_nao_vaza_para_o_caller(fernet_secret):
    """InvalidToken (do cryptography) nao deve chegar ao caller: sempre vira
    AsaasAccountSecretError sem carregar o plaintext.
    """
    with pytest.raises(AsaasAccountSecretError) as raised:
        decrypt_api_key("garbage-not-fernet")
    assert not isinstance(raised.value, InvalidToken)
    assert "plaintext" not in str(raised.value).lower()
