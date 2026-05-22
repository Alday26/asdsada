import mysql.connector
import os

def run():
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        port=int(os.environ.get("DB_PORT", 3306))
    )
    cursor = conn.cursor()

    with open("mobiledb3.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    # Split and execute each statement
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            try:
                cursor.execute(statement)
            except Exception as e:
                print(f"Skipped: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    run()
