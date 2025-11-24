from db_helper import PostgresDB
from typing import Tuple



class DBQueryHelper:
    def __init__(self):
        #Initialize the database connection
        self.db = PostgresDB()
        self.db.connect()
        # Initialize queries with proper schema formatting
        self.initialize_queries()
        self.transaction_type_map = {
            "debit": "expense",
            "credit": "income"
        }

    def initialize_queries(self):
        self.main_category_query = f"""
            SELECT mc.main_category
            FROM {self.db.schema}.merchants mer
                JOIN {self.db.schema}.main_categories mc
                    ON mc.id = mer.main_category_id
	            WHERE mer.id = %s;
        """
        self.sub_category_query = f"""
            SELECT sc.sub_category
            FROM {self.db.schema}.merchants mer
                JOIN {self.db.schema}.sub_categories sc
                    ON sc.id = mer.sub_category_id
	            WHERE mer.id = %s;
        """
        # Since transaction_type is from rules, the string will match exactly.
        self.get_all_main_categories_query = f"""
            SELECT DISTINCT id, main_category FROM {self.db.schema}.main_categories WHERE type = %s
        """
        self.get_sub_category_by_main_category_query = f"""
            SELECT sc.id, sc.sub_category
            FROM {self.db.schema}.category_map cm
                JOIN {self.db.schema}.sub_categories sc
                    ON cm.sub_category_id = sc.id
	            WHERE cm.main_category_id = %s;
        """
        self.get_categories_by_merchant_id_query = f"""
            SELECT mc.main_category
            FROM {self.db.schema}.merchants mer
                JOIN {self.db.schema}.main_categories mc
                    ON mc.id = mer.main_category_id
	            WHERE mer.id = %s;
        """
        self.alike_merchant_names_query = f"""
            SELECT 
                id, 
                merchant_name,
                similarity(LOWER(merchant_name), LOWER(%s)) AS score
            FROM {self.db.schema}.merchants
            WHERE LOWER(merchant_name) %% LOWER(%s)
            ORDER BY score DESC
            LIMIT 10;
        """
    #Close the database connection
    def close_db_connection(self):
        self.db.close()

    def get_sms_by_id(self, sms_id):
        try:
            # TODO: App inserts sms and app calls the pipeline.
            # TODO: SMS is directly passed to the pipeline.
            query = f"SELECT * FROM {self.db.schema}.sms WHERE id = %s"
            self.db.execute_query(query, (sms_id,))
            return self.db.cursor.fetchone()
        except Exception as e:
            raise e
    

    def get_all_main_categories(self, transaction_type: str) -> str:
        try:
            result = self.db.execute_query(self.get_all_main_categories_query, (self.transaction_type_map[transaction_type],))
            print(f"Main categories query result: {result}")
            return result
        except Exception as e:
            raise e

    def get_sub_category_by_main_category(self, main_category: str) -> list:
        try:
            result = self.db.execute_query(self.get_sub_category_by_main_category_query, (main_category,))
            return result
        except Exception as e:
            raise e

    def get_categories_by_merchant_id(self, merchant_id: int) -> list:
        try:
            main_category = self.db.execute_query(self.main_category_query, (merchant_id,))
            if main_category:
                # Get the sub category
                sub_category = self.db.execute_query(self.sub_category_query, (merchant_id,))
                if sub_category:
                    # Both are present
                    return (main_category[0]["main_category"], sub_category[0]["sub_category"])
                else:
                    # Only main category is present
                    return (main_category[0]["main_category"], "None")
            else:
                # No category is present
                return ("None", "None")
        except Exception as e:
            raise e 

    def test_category_retrieval(self):
        try:
            query = f"""
            SELECT sc.sub_category
            FROM {self.db.schema}.merchants mer
                JOIN {self.db.schema}.sub_categories sc
                    ON sc.id = mer.sub_category_id
	            WHERE mer.id = 1;
            """
            result = self.db.execute_query(query)
            print("None" if not result else result[0]["sub_category"])
        except Exception as e:
            raise e

    def convert_None_to_empty_string(self, value: str) -> str:
        return None if value == "" else value
    
    # Get the alike merchant names from the database.
    def get_alike_merchant_names(self, merchant_name: str) -> str:
        try:
            # Ensure connection is established
            self.db.connect()
            print(f"Searching for merchants similar to: {merchant_name}")
            result = self.db.execute_query(self.alike_merchant_names_query, (merchant_name,merchant_name))
            print(f"Result: {result}")
            return result or []
        except Exception as e:
            print(f"Error in get_alike_merchant_names: {e}")
            return [] 

    def get_sms_by_phone_number(self, phone_number: str) -> list:
        try:
            query = f"SELECT * FROM {self.db.schema}.sms WHERE phone_number = %s"
            self.db.execute_query(query, (phone_number,))
            return self.db.cursor.fetchall()
        except Exception as e:
            raise e

helper = DBQueryHelper()
helper.test_category_retrieval()