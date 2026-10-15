# app/models/bempaggo_webhooks.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class BempaggoBase(BaseModel):
    request_timestamp: datetime

class BempaggoCreate(BempaggoBase):
    token: Optional[str] = None
    order_status: Optional[str] = None
    last_charge_status: Optional[str] = None
    body: Optional[str] = None

class BempaggoUpdate(BaseModel):
    token: Optional[str] = None
    order_status: Optional[str] = None
    last_charge_status: Optional[str] = None
    body: Optional[str] = None

class BempaggoRead(BempaggoBase):
    id: int
    token: Optional[str]
    order_status: Optional[str]
    last_charge_status: Optional[str]
    body: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True

class BempaggoWebhook(Base):
    __tablename__ = 'bempaggo_webhooks'

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), nullable=True)
    order_status = Column(String(50), nullable=True)
    last_charge_status = Column(String(50), nullable=True)
    body = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)  # Adicionar esta linha
    request_timestamp = Column(DateTime, nullable=False)  # Se esta coluna existir no banco