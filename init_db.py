import mysql.connector
import os
import re

def run():
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "railway")
    )
    cursor = conn.cursor()

    with open("mobiledb3.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    # Remove CREATE DATABASE and USE statements — Railway manages the DB
    sql = re.sub(r'CREATE DATABASE[^;]+;', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'USE\s+`?[^`;]+`?\s*;', '', sql, flags=re.IGNORECASE)

    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            try:
                cursor.execute(statement)
                conn.commit()
            except Exception as e:
                print(f"Skipped: {e}")

    cursor.close()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    run()
