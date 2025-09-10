import pymysql
import os
from dotenv import load_dotenv

load_dotenv()
DB_NAME = os.getenv("DB_NAME", "routes_db")

def create_schema():
    conn = pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=int(os.getenv("DB_PORT", 3306))
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`;")
            print(f"Database `{DB_NAME}` checked/created.")
        conn.commit()
    finally:
        conn.close()

    from route_db_connect import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Drop route table first to clear FKs
        cursor.execute("DROP TABLE IF EXISTS Routes;")
                

        # Drop all location tables
        for i in range(10, 0, -1):
            cursor.execute(f"DROP TABLE IF EXISTS SubLocationsLv{i};")
        cursor.execute("DROP TABLE IF EXISTS State;")

        # Create State table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS State (
            state_id BIGINT PRIMARY KEY,
            state VARCHAR(255)
        );
        """)

        # Create SubLocationsLv1–10
        for i in range(1, 11):
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS SubLocationsLv{i} (
                location_id BIGINT PRIMARY KEY,
                location_name VARCHAR(255),
                parent_id BIGINT,
                coordinates POINT
            );
            """)

        # Create Routes table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Routes (
            route_id BIGINT PRIMARY KEY,
            route_name VARCHAR(255),
            parent_id BIGINT,
            rating VARCHAR(50)
        );
        """)

        conn.commit()
        print("Schema created successfully.")

        cursor.execute("SHOW TABLES;")
        rows = cursor.fetchall()
        if rows and isinstance(rows[0], dict):
            tables = [list(row.values())[0] for row in rows]
        else:
            tables = [row[0] for row in rows]
        print("Tables in DB:", tables)

    except Exception as e:
        print("Error creating schema:", repr(e))

if __name__ == "__main__":
    create_schema()
