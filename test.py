import oracledb

# Database connection details
DB_USER = "expense_app"
DB_PASSWORD = "test123"
DB_DSN = "localhost:1521/ORCLPDB1"

def show_users():
    try:
        conn = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        print(" | ".join(columns))
        print("-" * 50)
        for row in rows:
            print(" | ".join(str(item) for item in row))
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    show_users()