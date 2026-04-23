# create_schema.py
# ---------------------------------------------------------------------------
# Script to create the database schema for storing climbing routes and locations.
#
# reset=False (default): safe initialisation — creates tables only if they don't exist.
# reset=True            : drops and recreates all tables (destructive — use with caution).
#
# The database itself must already exist (managed services like Neon create it for you).
# ---------------------------------------------------------------------------

from dotenv import load_dotenv

load_dotenv()


def create_schema(reset: bool = False):
    from route_db_connect import get_connection
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if reset:
            print("Resetting schema — dropping all existing tables and views.")
            cursor.execute("DROP VIEW IF EXISTS all_areas;")
            cursor.execute("DROP TABLE IF EXISTS Routes;")
            for i in range(10, 0, -1):
                cursor.execute(f"DROP TABLE IF EXISTS SubLocationsLv{i};")
            cursor.execute("DROP TABLE IF EXISTS State;")

        # State table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS State (
            state_id BIGINT PRIMARY KEY,
            state    VARCHAR(255)
        );
        """)

        # SubLocationsLv1–10 (lat/lng stored as plain floats — no spatial extension required)
        for i in range(1, 11):
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS SubLocationsLv{i} (
                location_id   BIGINT PRIMARY KEY,
                location_name VARCHAR(255),
                parent_id     BIGINT,
                latitude      DOUBLE PRECISION,
                longitude     DOUBLE PRECISION
            );
            """)

        # Routes table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Routes (
            route_id   BIGINT PRIMARY KEY,
            route_name VARCHAR(255),
            parent_id  BIGINT,
            rating     VARCHAR(50)
        );
        """)

        # Convenience view that unions all location levels into a single queryable relation
        unions = [
            "SELECT 0 AS level, state_id AS area_id, state AS area_name, "
            "NULL::BIGINT AS parent_id, NULL::DOUBLE PRECISION AS latitude, "
            "NULL::DOUBLE PRECISION AS longitude FROM State"
        ]
        for i in range(1, 11):
            unions.append(
                f"SELECT {i} AS level, location_id, location_name, "
                f"parent_id, latitude, longitude FROM SubLocationsLv{i}"
            )
        cursor.execute(
            "CREATE OR REPLACE VIEW all_areas AS " + " UNION ALL ".join(unions) + ";"
        )

        conn.commit()
        print("Schema created successfully.")

        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
        )
        rows = cursor.fetchall()
        tables = [row["tablename"] for row in rows]
        print("Tables in DB:", tables)

    except Exception as e:
        conn.rollback()
        print("Error creating schema:", repr(e))
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    reset_flag = "--reset" in sys.argv
    if reset_flag:
        print("WARNING: --reset flag detected. All existing data will be dropped.")
    create_schema(reset=reset_flag)
