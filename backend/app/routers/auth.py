import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.database.db import get_user_id_by_email, verify_user
from app.security.passwords import PasswordPolicyError
from app.security.tokens import create_access_token
from app.services.account_recovery_service import (
    InvalidRecoveryCode,
    InvalidResetToken,
    RecoveryUnavailable,
    complete_password_reset,
    confirm_phone_verification,
    deliver_pending_code,
    get_account_security_status,
    request_password_reset,
    request_phone_verification,
    verify_password_reset_code,
)


router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

GENERIC_REQUEST_MESSAGE = (
    "Se houver uma conta elegível, enviaremos um código para o WhatsApp cadastrado."
)


class LoginPayload(BaseModel):
    email: EmailStr
    senha: str


class PasswordResetRequestPayload(BaseModel):
    email: EmailStr


class PasswordResetVerifyPayload(BaseModel):
    request_id: str
    code: str = Field(..., pattern=r"^[0-9]{6}$")


class PasswordResetCompletePayload(BaseModel):
    reset_token: str = Field(..., min_length=32, max_length=256)
    new_password: str


class PhoneVerificationConfirmPayload(BaseModel):
    request_id: str
    code: str = Field(..., pattern=r"^[0-9]{6}$")


def _requester_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _current_user_id(request: Request) -> int:
    payload = getattr(request.state, "user", {}) or {}
    user_id = payload.get("user_id")
    if user_id is not None:
        return int(user_id)

    email = payload.get("sub")
    if email:
        resolved_id = get_user_id_by_email(email)
        if resolved_id is not None:
            return int(resolved_id)
    raise HTTPException(status_code=401, detail="Sessão inválida")


@router.post("/login")
def login(payload: LoginPayload):
    user_dict = verify_user(str(payload.email), payload.senha)
    if not user_dict:
        logger.warning("Falha de login por credenciais inválidas")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    encoded_jwt = create_access_token(
        {
            "sub": user_dict["email"],
            "user_id": user_dict["id"],
            "role": user_dict["role"],
            "nome": user_dict["nome"],
            "unidade": user_dict["unidade"],
            "auth_version": user_dict.get("auth_version", 0),
        }
    )
    logger.info("Login concluído (user_id=%s)", user_dict["id"])

    return {
        "access_token": encoded_jwt,
        "token_type": "bearer",
        "user": {
            "id": user_dict["id"],
            "nome": user_dict["nome"],
            "email": user_dict["email"],
            "role": user_dict["role"],
            "unidade": user_dict["unidade"],
        },
    }


@router.post(
    "/auth/password-reset/request",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_password_reset_request(
    payload: PasswordResetRequestPayload,
    request: Request,
    background_tasks: BackgroundTasks,
):
    result = request_password_reset(str(payload.email), _requester_key(request))
    if result.delivery:
        background_tasks.add_task(deliver_pending_code, result.delivery)
    return {
        "message": GENERIC_REQUEST_MESSAGE,
        "request_id": result.request_id,
        "resend_after_seconds": 60,
    }


@router.post("/auth/password-reset/verify")
def verify_password_reset(payload: PasswordResetVerifyPayload):
    try:
        reset_token = verify_password_reset_code(payload.request_id, payload.code)
    except InvalidRecoveryCode as exc:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado") from exc
    except Exception as exc:
        logger.error("Falha ao validar código (%s)", type(exc).__name__)
        raise HTTPException(status_code=400, detail="Código inválido ou expirado") from exc
    return {"reset_token": reset_token, "expires_in_seconds": 300}


@router.post("/auth/password-reset/complete", status_code=status.HTTP_204_NO_CONTENT)
def finish_password_reset(payload: PasswordResetCompletePayload):
    try:
        complete_password_reset(payload.reset_token, payload.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidResetToken as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Falha ao concluir redefinição (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Não foi possível redefinir a senha agora.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/account-security")
def account_security(request: Request):
    try:
        security_status = get_account_security_status(_current_user_id(request))
    except RecoveryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "phone_masked": security_status.phone_masked,
        "phone_verified": security_status.phone_verified,
        "sender_unit": security_status.sender_unit,
    }


@router.post(
    "/auth/phone-verification/request",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_phone_verification_request(
    request: Request,
    background_tasks: BackgroundTasks,
):
    try:
        result = request_phone_verification(
            _current_user_id(request),
            _requester_key(request),
        )
    except RecoveryUnavailable as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.delivery:
        background_tasks.add_task(deliver_pending_code, result.delivery)
    return {
        "request_id": result.request_id,
        "resend_after_seconds": 60,
    }


@router.post(
    "/auth/phone-verification/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
)
def verify_phone(payload: PhoneVerificationConfirmPayload, request: Request):
    try:
        confirm_phone_verification(
            _current_user_id(request),
            payload.request_id,
            payload.code,
        )
    except InvalidRecoveryCode as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
