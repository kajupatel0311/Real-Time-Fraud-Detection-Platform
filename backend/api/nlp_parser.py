"""
Parser for extracting transaction parameters from natural language inputs.
"""
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def parse_transaction_message(message: str) -> Dict[str, Any]:
    """
    Parses conversational messages into structured transaction data using regex.
    """
    text = message.lower()
    
    # Extract amount
    amount = 0.0
    amount_match = re.search(r'(?:₹|rs\.?|usd|\$)?\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|million)?', text)
    if amount_match:
        try:
            val = float(amount_match.group(1).replace(',', ''))
            suffix = amount_match.group(2)
            if suffix == 'k': val *= 1000
            elif suffix == 'lakh': val *= 100000
            elif suffix == 'million': val *= 1000000
            amount = val
        except (ValueError, AttributeError):
            pass

    # Extract account identifiers
    sender = "C_UNKNOWN"
    receiver = "M_UNKNOWN"
    
    sender_match = re.search(r'(?:from|sender|orig(?:in)?)\s+([cm][a-z0-9]+)', text)
    if sender_match:
        sender = sender_match.group(1).upper()
    else:
        ids = re.findall(r'([cm][0-9]{5,})', text)
        if ids: sender = ids[0].upper()

    receiver_match = re.search(r'(?:to|receiver|dest(?:ination)?|merchant)\s+([cm][a-z0-9]+)', text)
    if receiver_match:
        receiver = receiver_match.group(1).upper()
    else:
        ids = re.findall(r'([cm][0-9]{5,})', text)
        if len(ids) > 1: receiver = ids[1].upper()

    # Determine transaction type
    txn_type = "TRANSFER"
    if any(kw in text for kw in ["payment", "paid"]): txn_type = "PAYMENT"
    elif any(kw in text for kw in ["cash out", "withdraw"]): txn_type = "CASH_OUT"
    elif any(kw in text for kw in ["cash in", "deposit"]): txn_type = "CASH_IN"
    elif "debit" in text: txn_type = "DEBIT"

    # Extract optional balance information
    balance = 0.0
    balance_match = re.search(r'(?:bal(?:ance)?|amt)\s+(?:of|is)?\s*([\d,]+(?:\.\d+)?)', text)
    if balance_match:
        try:
            balance = float(balance_match.group(1).replace(',', ''))
        except (ValueError, AttributeError):
            pass

    # Extract optional behavioral intents
    intents = []
    if any(kw in text for kw in ["urgent", "quickly", "asap", "emergency"]): intents.append("urgency")
    if any(kw in text for kw in ["all", "entire", "empty", "depletion"]): intents.append("depletion")
    if any(kw in text for kw in ["multiple", "repeated", "several"]): intents.append("frequency")

    return {
        "step": 1,
        "amount": amount,
        "type": txn_type,
        "oldbalanceOrg": balance,
        "newbalanceOrig": max(0.0, balance - amount),
        "oldbalanceDest": 0.0,
        "newbalanceDest": amount,
        "nameOrig": sender,
        "nameDest": receiver,
        "behavioral_intents": intents
    }
