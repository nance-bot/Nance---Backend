import psycopg2
from psycopg2.extras import DictCursor

class PostgresDB:
    def __init__(self, dbname="Nance", user="postgres", password="2003", host="localhost", port="5432"):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None
        self.cursor = None
        self.schema = "nance_init"

    def connect(self):
        try:
            if self.conn is None or self.conn.closed:
                self.conn = psycopg2.connect(
                    dbname=self.dbname,
                    user=self.user,
                    password=self.password,
                    host=self.host,
                    port=self.port
                )
                print("Connection established to the DB ✅")
            self.cursor = self.conn.cursor(cursor_factory=DictCursor)
            print("Cursor created ✅")
            return self.conn, self.cursor
        except Exception as e:
            raise e
        
    def execute_query(self, query, params=None):
        try:
        # Ensure DB connection
            if self.conn is None or self.conn.closed:
                self.connect()

            # Execute query
            if params:
                print(f"Executing query with params: {params}")
                self.cursor.execute(query, params)
            else:
                print("Executing query without params")
                self.cursor.execute(query)

            # Check if query produced rows (SELECT or RETURNING)
            if self.cursor.description:  
                result = self.cursor.fetchall()
                print(f"Query returned {len(result)} rows")
                return result

            # For INSERT/UPDATE/DELETE without returning rows
            self.conn.commit()
            return None
        except Exception as e:
            print(f"Database error: {e}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            raise e

    def close(self):
        try:
            if self.conn and not self.conn.closed:
                self.conn.close()
                print("Connection closed to the DB ✅")
        except Exception as e:
            raise e