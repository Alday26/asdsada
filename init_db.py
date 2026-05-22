import mysql.connector
import os
import re

def run():
    host = os.environ.get("MYSQLHOST") or os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("MYSQLPORT") or os.environ.get("DB_PORT", 3306))
    user = os.environ.get("MYSQLUSER") or os.environ.get("DB_USER", "root")
    password = os.environ.get("MYSQLPASSWORD") or os.environ.get("DB_PASSWORD", "")
    database = os.environ.get("MYSQLDATABASE") or os.environ.get("DB_NAME", "railway")

    print(f"init_db: Connecting to {host}:{port} db={database} user={user}")

    conn = mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
    cursor = conn.cursor()

    with open("mobiledb3.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    # Remove CREATE DATABASE and USE statements
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
