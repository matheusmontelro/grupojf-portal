"""SDK para integração com Delta - Fatura Recorrente"""
from .sdk import DeltaRecorrenteSDK
from .customer_manager import CustomerManager
from .split_manager import SplitManager

__all__ = ['DeltaRecorrenteSDK', 'CustomerManager', 'SplitManager']