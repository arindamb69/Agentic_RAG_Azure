import pyodbc
import os
import sys
import struct
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

def log(msg):
    print(msg)
    with open("sql_test_output.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def test_connection():
    # Clear log file
    with open("sql_test_output.txt", "w", encoding="utf-8") as f:
        f.write("Starting SQL Connection Test (Token Auth)...\n")

    conn_str_env = os.getenv("SQL_CONNECTION_STRING")
    if not conn_str_env:
        log("Error: SQL_CONNECTION_STRING not found in environment.")
        return False
        
    # Extract Server and Database from the string manually or assume standard format
    # Simpler: just construct a clean connection string for token auth
    try:
        parts = {p.split('=')[0]: p.split('=')[1] for p in conn_str_env.split(';') if '=' in p}
        server = parts.get("Server")
        database = parts.get("Database")
        driver = parts.get("Driver", "{ODBC Driver 18 for SQL Server}")
    except Exception:
        log("Could not parse existing connection string. Using fallback values.")
        server = "tcp:agentragsql.database.windows.net,1433"
        database = "agentragsql"
        driver = "{ODBC Driver 18 for SQL Server}"

    log(f"Target Server: {server}")
    log(f"Target Database: {database}")
    
    try:
        log("Acquiring Access Token via DefaultAzureCredential...")
        credential = DefaultAzureCredential()
        # Scope for Azure SQL Database
        token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
        token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
        
        # Build Connection String without Authentication keyword
        # We pass the token via the attrs_before argument
        conn_string = f"Driver={driver};Server={server};Database={database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        
        log("Attempting to connect with Access Token...")
        # SQL_COPT_SS_ACCESS_TOKEN = 1256
        conn = pyodbc.connect(conn_string, attrs_before={1256: token_struct})
        
        log("Connection successful!")
        
        cursor = conn.cursor()
        log("Executing query: SELECT @@VERSION")
        cursor.execute("SELECT @@VERSION")
        row = cursor.fetchone()
        if row:
            log(f"SQL Server Version: {row[0]}")
            
        cursor.close()
        conn.close()
        log("Test completed successfully.")
        return True
    except Exception as e:
        log(f"\nCONNECTION FAILED: {str(e)}")
        log("Troubleshooting tips:")
        log("1. Ensure you are logged in via 'az login' and the session is active.")
        log("2. Ensure your user is an Active Directory Admin on the SQL Server.")
        return False

if __name__ == "__main__":
    test_connection()
