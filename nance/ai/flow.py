from langchain_core.runnables import RunnableLambda
from prompt_templates import (
    NORMALIZE_PROMPT, 
    MAP_PROMPT, 
    SCRAPE_SUMMARIZE_PROMPT, 
    MAIN_CATEGORIZATION_PROMPT, 
    SUB_CATEGORY_PROMPT, 
    KNOWN_SUMMARIZE_PROMPT
)
from llm import llm, safe_extract_json
from bert_helper import run_bert
from db_query_helper import DBQueryHelper
from tavily_helper import TavilyHelper
from rule_extract import SMSExtractor
from typing import Literal, List, Optional, Union, Dict, Any
from dataclasses import dataclass, field, asdict
import warnings

warnings.filterwarnings("ignore")


@dataclass
class MerchantData:
    """Data class for merchant information and transaction details."""
    is_transaction: bool = False
    transaction_type: str = "unknown"
    amount: Optional[float] = None
    payment_mode: str = "OTHERS"
    transaction_date: Optional[str] = None
    transaction_time: Optional[str] = None
    candidates_list: List[str] = field(default_factory=list)
    normalized_account_name: Optional[str] = None
    confidence_score: float = 0.0
    main_category: str = ""
    sub_category: str = ""
    main_category_id: Optional[int] = None
    sub_category_id: Optional[int] = None
    context: str = ""
    web_search_context: str = ""
    matched_merchants: List[Dict[str, Any]] = field(default_factory=list)
    merchant_name: str = ""
    is_matched: bool = False
    merchant_id: Optional[int] = None
    content_type: str = ""
    is_business: bool = False
    main_categories: List[Dict[str, Any]] = field(default_factory=list)
    sub_categories: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to dictionary."""
        # First convert any DictRow objects to regular dictionaries
        self._convert_dict_rows()
        return asdict(self)
    
    def _convert_dict_rows(self) -> None:
        """Convert any DictRow objects to regular dictionaries to make them serializable."""
        # Check if matched_merchants contains DictRow objects
        if hasattr(self, 'matched_merchants') and self.matched_merchants:
            try:
                # Convert DictRow objects to regular dictionaries
                converted_merchants = []
                for merchant in self.matched_merchants:
                    if hasattr(merchant, 'keys'):  # Check if it's a DictRow-like object
                        converted_merchants.append(dict(merchant))
                    else:
                        converted_merchants.append(merchant)
                self.matched_merchants = converted_merchants
            except Exception as e:
                print(f"Warning: Could not convert DictRow objects: {e}")
                # Fallback: convert to empty list if conversion fails
                self.matched_merchants = []
        
        # Check other list fields that might contain DictRow objects
        for field_name in ['main_categories', 'sub_categories']:
            if hasattr(self, field_name) and getattr(self, field_name):
                try:
                    field_value = getattr(self, field_name)
                    if isinstance(field_value, list):
                        converted_items = []
                        for item in field_value:
                            if hasattr(item, 'keys'):  # Check if it's a DictRow-like object
                                converted_items.append(dict(item))
                            else:
                                converted_items.append(item)
                        setattr(self, field_name, converted_items)
                except Exception as e:
                    print(f"Warning: Could not convert DictRow objects in {field_name}: {e}")
                    setattr(self, field_name, [])

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update fields from a dictionary, only updating existing fields."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


class SMSMerchantCategorizer:
    """Main class for categorizing SMS merchants and transactions."""
    
    def __init__(self):
        self.merchant_data = MerchantData()
        self.db_query_helper = DBQueryHelper()
        self.tavily_helper = TavilyHelper()
        self.sms_extractor = SMSExtractor()

    def get_sms_details(self, sms: str) -> None:
        """Extract SMS details and update merchant data."""
        try:
            sms_details = self.sms_extractor.extract_details(sms)
            if sms_details:
                self.merchant_data.update_from_dict(sms_details)
        except Exception as e:
            print(f"Error extracting SMS details: {e}")

    def categorization_flow(self, content: str, content_type: str) -> Dict[str, Any]:
        """Main categorization flow for processing content."""
        try:
            # Reset merchant data for new content
            self.merchant_data = MerchantData()
            self.merchant_data.content_type = content_type
            
            # Extract details from SMS if applicable
            if content_type == "SMS":
                self.get_sms_details(content)
                
                # Early return if SMS is not a transaction
                if not self.merchant_data.is_transaction:
                    print("SMS is not a transaction ⚠️")
                    return self.merchant_data.to_dict()

            # Extract candidates using BERT
            candidates = run_bert(content)
            self.merchant_data.candidates_list = candidates if candidates else []
            
            if not self.merchant_data.candidates_list:
                print("No candidates found ⚠️")
                return self.merchant_data.to_dict()

            print(f"Candidates list: {self.merchant_data.candidates_list}")
            
            # Normalize account name
            response_json = self._run_normalize_chain()
            if response_json:
                self.merchant_data.update_from_dict(response_json)
            
            print(f"Merchant data: {self.merchant_data.to_dict()}")
            
            # Check if business account
            self._convert_bool_field("is_business")
            if not self.merchant_data.is_business:
                print(f"Normalized account name: {self.merchant_data.normalized_account_name}")
                print("Account name is not a merchant ⚠️")
                return self.merchant_data.to_dict()

            if not self.merchant_data.normalized_account_name:
                print("No account name found ⚠️")
                return self.merchant_data.to_dict()

            # Get matched merchants from database
            self._process_matched_merchants()
            
            # Process merchant matching
            self._convert_bool_field("is_matched")
            if self.merchant_data.is_matched:
                self._process_merchant_categories()
                return self.merchant_data.to_dict()

            # Handle unknown merchants
            if self.merchant_data.confidence_score < 75:
                self._process_unknown_merchant()
            
            else:
                response_json = self._run_known_summarize_chain()
                self.merchant_data.context = response_json.get("summary", "")
            
            # Get main categories based on transaction type
            self._get_main_categories()
            
            if not self.merchant_data.main_categories:
                print("No main categories found ⚠️")
                return self.merchant_data.to_dict()

            print("Main categories found ✅")
            
            # Categorize to main category
            response_json = self._run_main_categorization_chain()
            self.merchant_data.main_category = response_json.get("main_category", "")
            self.merchant_data.main_category_id = response_json.get("main_category_id")
            
            if not self.merchant_data.main_category or self.merchant_data.main_category == "None":
                print("No main category found ⚠️")
                return self.merchant_data.to_dict()

            print(f"Main category: {self.merchant_data.main_category}")
            print(f"Main category ID: {self.merchant_data.main_category_id}")
            
            # Process sub-categories
            self._process_sub_categories()
            
            return self.merchant_data.to_dict()
            
        except Exception as e:
            print(f"Error running flow: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return {}

    def _process_matched_merchants(self) -> None:
        """Process matched merchants from database."""
        try:
            matched_merchants = self.db_query_helper.get_alike_merchant_names(
                self.merchant_data.normalized_account_name
            )
            print("Alike merchants:", matched_merchants)
            
            if matched_merchants:
                print("Matched merchants found ✅")
                self.merchant_data.matched_merchants = matched_merchants
                response_json = self._run_map_chain()
                print("Mapped merchant to DB ✅")
                
                if response_json:
                    self.merchant_data.update_from_dict(response_json)
            else:
                print("No matched merchants found ⚠️")
                self.merchant_data.matched_merchants = []
                self.merchant_data.merchant_name = self.merchant_data.normalized_account_name
                self.merchant_data.is_matched = False
                self.merchant_data.merchant_id = None
                
        except Exception as e:
            print(f"Database query error: {e}")
            self.merchant_data.matched_merchants = []
            self.merchant_data.is_matched = False
            self.merchant_data.merchant_id = None

    def _process_merchant_categories(self) -> None:
        """Process merchant categories for matched merchants."""
        try:
            merchant_category = self.db_query_helper.get_categories_by_merchant_id(
                self.merchant_data.merchant_id
            )
            if merchant_category and len(merchant_category) >= 2:
                self.merchant_data.main_category = merchant_category[0]
                self.merchant_data.sub_category = merchant_category[1]
            else:
                print("Invalid merchant category data")
                self.merchant_data.is_matched = False
        except Exception as e:
            print(f"Error getting merchant categories: {e}")
            self.merchant_data.is_matched = False

    def _process_unknown_merchant(self) -> None:
        """Process unknown merchants by getting context."""
        self.merchant_data.context = ""
        # Get merchant context by summarizing web searches
        merchant_context = self.tavily_helper.handle_web_search(
            self.merchant_data.merchant_name
        )
        self.merchant_data.web_search_context = merchant_context
        
        response_json = self._run_web_search_summarize_chain()
        self.merchant_data.context = response_json.get("summary", "")
        # TODO: Insert merchant name and description as new row in table
        # TODO: Insert merchant's category and sub-category to DB

    def _get_main_categories(self) -> None:
        """Get main categories based on transaction type."""
        if self.merchant_data.transaction_type.lower() != "unknown":
            self.merchant_data.main_categories = self.db_query_helper.get_all_main_categories(
                self.merchant_data.transaction_type.lower()
            )
        else:
            self.merchant_data.main_categories = []

    def _process_sub_categories(self) -> None:
        """Process sub-categories for the identified main category."""
        sub_categories = self.db_query_helper.get_sub_category_by_main_category(
            self.merchant_data.main_category_id
        )
        self.merchant_data.sub_categories = sub_categories if sub_categories else []
        
        response_json = self._run_sub_category_chain()
        self.merchant_data.sub_category = response_json.get("sub_category", "")
        self.merchant_data.sub_category_id = response_json.get("sub_category_id")

    def _run_main_categorization_chain(self) -> Dict[str, Any]:
        """Run the main categorization chain."""
        try:
            main_categorization_chain = (
                MAIN_CATEGORIZATION_PROMPT | 
                llm | 
                RunnableLambda(lambda x: safe_extract_json(x.content))
            )
            response_json = main_categorization_chain.invoke({
                "merchant_name": self.merchant_data.merchant_name,
                "merchant_context": (
                    self.merchant_data.context 
                    if self.merchant_data.confidence_score < 50 
                    else ""
                ),
                "categories": self.merchant_data.main_categories,
                "transaction_type": self.merchant_data.transaction_type
            })
            return response_json or {}
        except Exception as e:
            print(f"Error in main categorization chain: {e}")
            return {}

    def _run_sub_category_chain(self) -> Dict[str, Any]:
        """Run the sub-category chain."""
        try:
            sub_category_chain = (
                SUB_CATEGORY_PROMPT | 
                llm | 
                RunnableLambda(lambda x: safe_extract_json(x.content))
            )
            response_json = sub_category_chain.invoke({
                "merchant_name": self.merchant_data.merchant_name,
                "merchant_context": self.merchant_data.context,
                "main_category": self.merchant_data.main_category,
                "sub_categories": self.merchant_data.sub_categories,
                "transaction_type": self.merchant_data.transaction_type
            })
            return response_json or {}
        except Exception as e:
            print(f"Error in sub category chain: {e}")
            return {}

    def _run_web_search_summarize_chain(self) -> Dict[str, Any]:
        """Run the web search summarize chain."""
        try:
            summarize_chain = (
                SCRAPE_SUMMARIZE_PROMPT | 
                llm | 
                RunnableLambda(lambda x: safe_extract_json(x.content))
            )
            response_json = summarize_chain.invoke({
                "merchant_name": self.merchant_data.merchant_name,
                "merchant_context": self.merchant_data.web_search_context
            })
            return response_json or {}
        except Exception as e:
            print(f"Error in web search summarize chain: {e}")
            return {}
        
    def _run_known_summarize_chain(self) -> Dict[str, Any]:
        """Run the known summarize chain."""
        try:
            summarize_chain = (
                KNOWN_SUMMARIZE_PROMPT | 
                llm | 
                RunnableLambda(lambda x: safe_extract_json(x.content))
            )
            prompt_str = KNOWN_SUMMARIZE_PROMPT.format_prompt(
                merchant_name=self.merchant_data.merchant_name
            ).to_string()
            print("Final Prompt:\n", prompt_str)
            response_json = summarize_chain.invoke({
                "merchant_name": self.merchant_data.merchant_name,
            })
            return response_json or {}
        except Exception as e:
            print(f"Error in known summarize chain: {e}")
            return {}

    def _convert_bool_field(self, key: str) -> None:
        """Convert string boolean fields to actual boolean values."""
        if hasattr(self.merchant_data, key):
            value = getattr(self.merchant_data, key)
            if isinstance(value, str):
                if value.lower() == "true":
                    setattr(self.merchant_data, key, True)
                elif value.lower() == "false":
                    setattr(self.merchant_data, key, False)

    def _run_map_chain(self) -> Dict[str, Any]:
        """Run the map chain."""
        try:
            map_chain = (
                MAP_PROMPT | 
                llm | 
                RunnableLambda(lambda x: safe_extract_json(x.content))
            )
            response_json = map_chain.invoke({
                "merchant_name": self.merchant_data.normalized_account_name,
                "matched_merchants": self.merchant_data.matched_merchants
            })
            return response_json or {}
        except Exception as e:
            print(f"Error in map chain: {e}")
            return {}

    def _run_normalize_chain(self) -> Dict[str, Any]:
        """Run the normalize chain."""
        try:
            normalize_chain = (
                NORMALIZE_PROMPT | 
                llm | 
                RunnableLambda(lambda x: safe_extract_json(x.content))
            )
            response_json = normalize_chain.invoke({
                "candidates_list": self.merchant_data.candidates_list
            })
            return response_json or {}
        except Exception as e:
            print(f"Error in normalize chain: {e}")
            return {}


if __name__ == "__main__":
    categorizer = SMSMerchantCategorizer()
    # categorizer.categorization_flow("I paid 1000 to Amazon for groceries")