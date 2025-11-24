import re
from typing import Dict, Optional, List, Tuple, Literal, Any, Union
from datetime import datetime


class SMSExtractor:
    """
    A class for extracting transaction details from SMS messages.
    
    This class provides methods to identify and extract various transaction-related
    information from SMS messages including transaction type, amount, and payment mode.
    """
    
    def __init__(self):
        """Initialize the SMSExtractor with predefined keyword lists."""
        self.transaction_keywords = [
            "debited", "credited", "spent", "withdrawn", "purchase", 
            "deposited", "sent", "transferred", "received", "neft", 
            "cr", "txn", "transaction", "paid"
        ]
        
        self.debit_keywords = [
            "debited", "spent", "withdrawn", "purchase", 
            "transferred", "paid", "sent"
        ]
        
        self.credit_keywords = [
            "credited", "deposited", "received", "cr"
        ]
        
        self.payment_mode_patterns = {
            "UPI": ["upi", "paytm", "gpay", "bhim", "bhimupi", "phonepe"],
            "ATM": ["atm"],
            "BANK TRANSFER": ["neft", "rtgs", "imps"],
            "CARD": ["debit card", "card ending"]
        }

    
    def is_transaction(self, sms: str) -> bool:
        """
        Determine if an SMS contains transaction information.
        
        Args:
            sms (str): The SMS message to analyze
            
        Returns:
            bool: True if transaction keywords are found, False otherwise
            
        Raises:
            ValueError: If SMS is not a string
        """
        try:
            return True if any(kw in sms.lower() for kw in self.transaction_keywords) else False
        except Exception as e:
            print(f"Error in is_transaction: {e}")
            raise e
    
    def get_transaction_type(self, sms: str) -> str:
        """
        Determine the type of transaction (debit/credit/unknown).
        
        Args:
            sms (str): The SMS message to analyze
            
        Returns:
            str: "debit", "credit", or "unknown"
        """
        try:
            sms_lower = sms.lower()
            
            # High-confidence override
            if "neft" in sms_lower:
                return "credit"
            
            has_debit = any(word in sms_lower for word in self.debit_keywords)
            has_credit = any(word in sms_lower for word in self.credit_keywords)
            
            if has_debit:
                return "debit"
            if has_credit:
                return "credit"
            return "unknown" # if no keywords are found
        except Exception as e:
            print(f"Error in get_transaction_type: {e}")
            raise e
    
    def extract_amount(self, sms: str) -> Optional[str]:
        """
        Extract the transaction amount from the SMS.
        
        Args:
            sms (str): The SMS message to analyze
            
        Returns:
            Optional[str]: The extracted amount as string, or None if not found
        """
        try:
            # Extract transaction amount using regex
            amount_match = re.search(r'(?:rs\.?|inr)[\s:.]*([\d,]+(?:\.\d{1,2})?)', sms.lower())
            if amount_match:
                return float(amount_match.group(1).replace(",", ""))
            return None
        except Exception as e:
            print(f"Error in extract_amount: {e}")
            raise e
    
    def get_payment_mode(self, sms: str) -> Literal["UPI", "ATM", "BANK TRANSFER", "CARD", "OTHERS"]:
        """
        Identify the payment mode used in the transaction.
        
        Args:
            sms (str): The SMS message to analyze
            
        Returns:
            Literal["UPI", "ATM", "BANK TRANSFER", "CARD", "OTHERS"]: The payment mode
        """
        try:
            sms_lower = sms.lower()
            
            for mode, patterns in self.payment_mode_patterns.items():
                if any(pattern in sms_lower for pattern in patterns):
                    return mode
            
            return "OTHERS"
        except Exception as e:
            print(f"Error in get_payment_mode: {e}")
            raise e
    
    def extract_details(self, sms: str) -> Dict[str, Any]:
        """
        Extract all transaction details from an SMS message.
        
        Args:
            sms (str): The SMS message to analyze
            
        Returns:
            Dict[str, Any]: Dictionary containing extracted details:
                - is_transaction: True or False
                - transaction_type: "debit", "credit", or "unknown"
                - amount: Transaction amount or None
                - payment_mode: Payment mode (UPI, ATM, BANK TRANSFER, CARD, OTHERS)
                - transaction_date: Transaction date or None
                - transaction_time: Transaction time or None
        """
        try:
            transaction_date, transaction_time = self.extract_transaction_date_and_time(sms)
            result = {
                "is_transaction": self.is_transaction(sms)
            }
            if self.is_transaction(sms):
                result["transaction_type"] = self.get_transaction_type(sms)
                result["amount"] = self.extract_amount(sms)
                result["payment_mode"] = self.get_payment_mode(sms)
                result["transaction_date"] = transaction_date
                result["transaction_time"] = transaction_time
            
            print("Details extracted successfully ✅")
            return result
        except Exception as e:
            print(f"Error in extracting details ❌: {e}")
            raise e
    
    def extract_transaction_date_and_time(self, sms: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract the transaction date and time from the SMS.

        Args:
            sms (str): The SMS message to analyze

        Returns:
            Tuple[Optional[str], Optional[str]]: The extracted date and time
        """
        sms = sms.lower()

        # --- DATE Patterns ---
        date_patterns = [
            # Represents different date formats
            (r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", ["%d-%m-%y", "%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y"]),
            (r"(\d{1,2})[/-]([a-z]{3})[/-](\d{2,4})", ["%d-%b-%y", "%d-%b-%Y", "%d/%b/%y", "%d/%b/%Y"])
        ]

        # --- TIME Pattern (with optional seconds and AM/PM) ---
        time_regex = r"(\d{1,2}:\d{2}(?::\d{2})?) ?(am|pm)?"

        extracted_date = None
        extracted_time = None

        for date_pattern, formats in date_patterns:
            match = re.search(date_pattern, sms)
            if match:
                day, month, year = match.groups()
                # Try all the formats
                for fmt in formats:
                    try:
                        y = year
                        if len(y) == 2 and "%Y" in fmt:
                            y = str(datetime.now().year)[:2] + y
                        date_str = f"{day}-{month}-{y}"
                        dt = datetime.strptime(date_str, fmt)
                        extracted_date = dt.strftime("%Y-%m-%d")

                        # Look for time near the matched date
                        # From the patterns observed if time occurs, it seems to be appearing closer to the date.
                        start = max(match.start() - 5, 0)
                        end = min(match.end() + 5, len(sms))
                        nearby_text = sms[start:end]

                        time_match = re.search(time_regex, nearby_text)
                        if time_match:
                            time_val, meridian = time_match.groups()
                            if meridian:
                                fmt = "%I:%M:%S %p" if time_val.count(":") == 2 else "%I:%M %p"
                                time_dt = datetime.strptime(f"{time_val} {meridian}", fmt)
                            else:
                                fmt = "%H:%M:%S" if time_val.count(":") == 2 else "%H:%M"
                                time_dt = datetime.strptime(time_val, fmt)
                            extracted_time = time_dt.strftime("%H:%M")
                        break
                    except:
                        continue
            if extracted_date:
                break

        return extracted_date, extracted_time

# Backward compatibility functions
def is_transaction(sms: str) -> str:
    """Backward compatibility function."""
    extractor = SMSExtractor()
    return extractor.is_transaction(sms)


def transaction_type(sms: str) -> str:
    """Backward compatibility function."""
    extractor = SMSExtractor()
    return extractor.get_transaction_type(sms)


def amount(sms: str) -> str:
    """Backward compatibility function."""
    extractor = SMSExtractor()
    return extractor.extract_amount(sms)


def payment_mode(sms: str) -> str:
    """Backward compatibility function."""
    extractor = SMSExtractor()
    return extractor.get_payment_mode(sms)


def extract_details(sms: str) -> dict:
    """Backward compatibility function."""
    extractor = SMSExtractor()
    return extractor.extract_details(sms)

