import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# USERS TABLE
cursor.execute("""
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
""")

# DISASTER TYPES TABLE
cursor.execute("""
CREATE TABLE disasters (
    disaster_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disaster_name TEXT NOT NULL
)
""")

# REPORTS TABLE
cursor.execute("""
CREATE TABLE reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    disaster_id INTEGER,
    location TEXT,
    description TEXT,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (disaster_id) REFERENCES disasters(disaster_id)
)
""")




# Insert disaster types
cursor.execute("INSERT INTO disasters (disaster_name) VALUES ('Flood')")
cursor.execute("INSERT INTO disasters (disaster_name) VALUES ('Earthquake')")
cursor.execute("INSERT INTO disasters (disaster_name) VALUES ('Fire')")
cursor.execute("INSERT INTO disasters (disaster_name) VALUES ('Landslide')")

conn.commit()
conn.close()

print("Database created successfully")