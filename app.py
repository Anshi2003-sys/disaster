import os
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.utils import secure_filename

import spacy
# Load NLP model (run only once when app starts)
nlp = spacy.load("en_core_web_sm")

app = Flask(__name__)
app.secret_key = "disaster_secret_key"
DATABASE = "database.db"

# Upload config
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- DATABASE CONNECTION ----------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- CREATE TABLES ----------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    # ALERTS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read INTEGER DEFAULT 0
    )
    """)

    # DISASTER TYPES TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS disasters (
        disaster_id INTEGER PRIMARY KEY AUTOINCREMENT,
        disaster_name TEXT NOT NULL
    )
    """)

    # ADMIN REPORT TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_reports (
    admin_report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disaster_id INTEGER,
    district TEXT,
    area TEXT,
    description TEXT,
    reported_by TEXT DEFAULT 'Admin',
    status TEXT DEFAULT 'Confirmed by Admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (disaster_id) REFERENCES disasters(disaster_id)
    )
    """)

    # REPORTS TABLE (UPDATED)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        disaster_id INTEGER,
        location TEXT,
        description TEXT,
        latitude REAL,
        longitude REAL,
        reported_by TEXT,
        status TEXT DEFAULT 'Pending',  
        image TEXT,
        severity TEXT,
        keywords TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (disaster_id) REFERENCES disasters(disaster_id)
    )
    """)

    conn.commit()

    # Insert disaster types if table empty
    cursor.execute("SELECT COUNT(*) FROM disasters")
    count = cursor.fetchone()[0]

    if count == 0:
        disasters = [("Flood",), ("Earthquake",), ("Fire",), ("Landslide",)]
        cursor.executemany("INSERT INTO disasters (disaster_name) VALUES (?)", disasters)

    conn.commit()
    conn.close()


# Run database initialization
init_db()


# ---------------- AI NLP FUNCTION ----------------
def analyze_description(text):
    doc = nlp(text.lower())

    keywords = [token.text for token in doc if token.is_alpha and not token.is_stop]

    high_words = ["dead", "trapped", "urgent", "help", "collapsed", "flooded", "critical"]
    medium_words = ["damage", "water", "fire", "injured", "crack","awmlo"]

    severity = "Low"

    # 🔥 FIXED LOGIC
    text_lower = text.lower()

    if any(word in text_lower for word in high_words):
        severity = "High"
    elif any(word in text_lower for word in medium_words):
        severity = "Medium"

    return severity, keywords


# ---------------- HOME PAGE ----------------
@app.route("/")
def home():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    reports = conn.execute("""
        SELECT users.name, disasters.disaster_name, reports.location
        FROM reports
        JOIN users ON reports.user_id = users.user_id
        JOIN disasters ON reports.disaster_id = disasters.disaster_id
        ORDER BY reports.report_id DESC
        LIMIT 5
    """).fetchall()

    # COUNT ONLY UNREAD NOTIFICATIONS
    notification_count = conn.execute("""
        SELECT COUNT(*) FROM notifications
        WHERE is_read = 0
    """).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        reports=reports,
        notification_count=notification_count
    )



#----------------------notification delete and edit-------------------------------------------------
@app.route("/delete_alert/<int:id>")
def delete_alert(id):

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("database.db")

    conn.execute(
    "DELETE FROM notifications WHERE id=?",
    (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/notifications")


@app.route("/edit_alert/<int:id>", methods=["GET", "POST"])
def edit_alert(id):

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    if request.method == "POST":

        title = request.form["title"]
        message = request.form["message"]

        conn.execute("""
        UPDATE notifications
        SET title=?, message=?
        WHERE id=?
        """, (title, message, id))

        conn.commit()
        conn.close()

        return redirect("/notifications")

    alert = conn.execute("""
    SELECT * FROM notifications
    WHERE id=?
    """, (id,)).fetchone()

    conn.close()

    return render_template(
        "edit_alert.html",
        alert=alert
    )


# ---------------- USER REGISTER ----------------
@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")

        conn.execute(
        "INSERT INTO users (name,email,password) VALUES (?,?,?)",
        (name,email,password)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")



# ---------------- Notification by Admin----------------
@app.route("/post_alert", methods=["GET", "POST"])
def post_alert():

    if "admin" not in session:
        return redirect("/admin_login")

    if request.method == "POST":

        title = request.form["title"]
        message = request.form["message"]

        conn = sqlite3.connect("database.db")

        conn.execute("""
        INSERT INTO notifications (title, message,is_read)
        VALUES (?, ?, 0)
        """, (title, message))

        conn.commit()
        conn.close()

        return redirect("/admin_dashboard")

    return render_template("post_alert.html")


# ---------------- Notification icon ----------------
@app.route("/notifications")
def notifications():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    # MARK ALL NOTIFICATIONS AS READ
    conn.execute("""
    UPDATE notifications
    SET is_read = 1
    WHERE is_read = 0
    """)

    conn.commit()

    notifications = conn.execute("""
    SELECT * FROM notifications
    ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "notifications.html",
        notifications=notifications
    )

# ---------------- LIVE NOTIFICATION COUNT API ----------------
@app.route("/get_notification_count")
def get_notification_count():

    conn = sqlite3.connect("database.db")

    unread = conn.execute("""
    SELECT COUNT(*) FROM notifications
    WHERE is_read = 0
    """).fetchone()[0]

    conn.close()

    return {"count": unread}

# ---------------- USER LOGIN ----------------
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row

        user = conn.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email,password)
        ).fetchone()

        conn.close()

        if user:

            session["user_id"] = user["user_id"]
            session["user_name"] = user["name"]

            return redirect("/")

        else:
            return "Invalid Login"

    return render_template("login.html")


# ---------------- USER LOGOUT ----------------
@app.route("/user_logout")
def user_logout():

    session.pop("user_id", None)
    session.pop("user_name", None)

    return redirect("/")


# ---------------- REPORT DISASTER ----------------
@app.route("/report", methods=["GET", "POST"])
def report():

    conn = get_db_connection()

    if "user_id" not in session:
        return redirect("/login")

    disasters = conn.execute("SELECT * FROM disasters").fetchall()

    if request.method == "POST":
        user_id = session["user_id"]
        location = request.form["location"]
        disaster = request.form["disaster"]
        description = request.form["description"]
        latitude = request.form["latitude"]
        longitude = request.form["longitude"]

        # 🤖 AI NLP ANALYSIS
        severity, keywords = analyze_description(description)

        # IMAGE HANDLING
        image = request.files['image']
        filename = None
        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Get disaster id
        cursor.execute(
            "SELECT disaster_id FROM disasters WHERE disaster_name=?",
            (disaster,)
        )
        result = cursor.fetchone()

        if result:
            disaster_id = result[0]
        else:
            return "Disaster type not found in database"

        # Insert report (UPDATED)
        cursor.execute("""
        INSERT INTO reports 
        (user_id, disaster_id, location, description, latitude, longitude, reported_by, image, severity, keywords)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, disaster_id, location, description, latitude, longitude, "User", filename, severity, ", ".join(keywords)))
       
       
        # INSERT NOTIFICATION
        title = "New Disaster Report"
        message = f"""
        A new {disaster} report has been submitted by a user at {location}.
       Authorities will verify the report soon.
        """
        cursor.execute("""
        INSERT INTO notifications(title, message, is_read)VALUES (?, ?, 0)""", (title, message))

        conn.commit()
        conn.close()
        return redirect(url_for("home"))

    conn.close()
    return render_template("report.html", disasters=disasters)


# ---------------- ALERTS PAGE ----------------
@app.route("/alerts")
def alerts():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    # =========================
    # USER REPORTS
    # =========================
    user_reports = conn.execute("""
        SELECT reports.*, disasters.disaster_name, users.name
        FROM reports
        LEFT JOIN users ON reports.user_id = users.user_id
        JOIN disasters ON reports.disaster_id = disasters.disaster_id
        ORDER BY reports.report_id DESC
    """).fetchall()

    # =========================
    # ADMIN REPORTS
    # =========================
    admin_reports = conn.execute("""
        SELECT admin_reports.*, disasters.disaster_name
        FROM admin_reports
        JOIN disasters ON admin_reports.disaster_id = disasters.disaster_id
        ORDER BY admin_report_id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "alerts.html",
        reports=user_reports,
        admin_reports=admin_reports
    )


# ---------------- ABOUT PAGE ----------------
@app.route("/about")
def about():
    return render_template("about.html")


# ---------------- MAP PAGE ----------------
@app.route("/map")
def map_page():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
    SELECT reports.report_id,
       users.name,
       disasters.disaster_name,
       reports.location,
       reports.description,
       reports.latitude,
       reports.longitude,
       reports.reported_by,
       reports.severity                 
    FROM reports
    LEFT JOIN users ON reports.user_id = users.user_id
    JOIN disasters ON reports.disaster_id = disasters.disaster_id
    """).fetchall()

    conn.close()
    
    reports = [dict(row) for row in rows]
    return render_template("map.html", reports=reports)


# ---------------- ADMIN LOGIN ----------------
@app.route("/admin_login", methods=["GET","POST"])
def admin_login():

    if request.method == "POST":

        admin_id = request.form["admin_id"]
        password = request.form["password"]

        if admin_id == "admin" and password == "1234":
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

        else:
            return "Invalid Admin Credentials"

    return render_template("admin_login.html")


# ---------------- ADMIN LOGOUT ----------------
@app.route("/logout")
def logout():

    session.pop("admin", None)
    return redirect(url_for("admin_login"))


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    total_reports = conn.execute(
    "SELECT COUNT(*) FROM reports").fetchone()[0]

    pending_reports = conn.execute(
    "SELECT COUNT(*) FROM reports WHERE status='Pending'").fetchone()[0]

    approved_reports = conn.execute(
    "SELECT COUNT(*) FROM reports WHERE status='Approved'").fetchone()[0]

    reports = conn.execute("""
    SELECT reports.*, disasters.disaster_name
    FROM reports
    JOIN disasters
    ON reports.disaster_id = disasters.disaster_id
    ORDER BY 
                            CASE
        WHEN reports.status = 'Pending' THEN 1
        WHEN reports.status = 'Confirmed by Admin' THEN 2
        WHEN reports.status = 'Rejected by Admin' THEN 3
        ELSE 4
    END,

    reports.report_id DESC

    """).fetchall()

    admin_reports = conn.execute("""
    SELECT admin_reports.*, disasters.disaster_name
    FROM admin_reports
    JOIN disasters ON admin_reports.disaster_id = disasters.disaster_id
    ORDER BY admin_reports.admin_report_id DESC
    LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
    "admin_dashboard.html",
    total_reports=total_reports,
    pending_reports=pending_reports,
    approved_reports=approved_reports,
    reports=reports,
    admin_reports=admin_reports
    )

# ---------------- ADMIN REPORT ----------------
@app.route("/admin_report", methods=["GET", "POST"])
def admin_report():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    disasters = conn.execute("SELECT * FROM disasters").fetchall()

    if request.method == "POST":

        disaster_id = request.form["disaster_id"]
        district = request.form["district"]
        area = request.form["area"]
        description = request.form["description"]

        conn.execute("""
        INSERT INTO admin_reports
        (disaster_id, district, area, description)
        VALUES (?, ?, ?, ?)
        """, (disaster_id, district, area, description))

        disaster_data = conn.execute("""
         SELECT disaster_name
        FROM disasters
         WHERE disaster_id=?
        """, (disaster_id,)).fetchone()

       # CREATE NOTIFICATION

        title = "Emergency Alert Published"

        message = f"""
Admin published a {disaster_data['disaster_name']} alert
for {district}, {area}.
Please stay alert and follow safety guidelines.
"""

        conn.execute("""

INSERT INTO notifications
(title, message, is_read)

        VALUES (?, ?, 0)

        """, (title, message))

        conn.commit()
        conn.close()

        return redirect("/admin_dashboard")

    conn.close()
    return render_template("admin_report.html", disasters=disasters)


#Reported by admin
@app.route('/delete_admin_report/<int:id>')
def delete_admin_report(id):

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect('database.db')

    conn.execute("""
    DELETE FROM admin_reports
    WHERE admin_report_id=?
    """, (id,))

    conn.commit()
    conn.close()

    return redirect('/admin_dashboard')


# ---------------- DELETE REPORT by admin----------------
@app.route("/delete/<int:id>")
def delete(id):

    conn = sqlite3.connect("database.db")
    conn.execute("DELETE FROM reports WHERE report_id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

# ---------------- Approve REPORT ----------------
@app.route("/approve/<int:id>")
def approve(id):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    # UPDATE REPORT STATUS
    conn.execute("""
    UPDATE reports
    SET status='Confirmed by Admin'
    WHERE report_id=?
    """, (id,))

    # GET REPORT DETAILS
    report = conn.execute("""
    SELECT reports.location,
           disasters.disaster_name
    FROM reports
    JOIN disasters
    ON reports.disaster_id = disasters.disaster_id
    WHERE reports.report_id=?
    """, (id,)).fetchone()

    # CREATE NOTIFICATION
    title = "Disaster Verified"

    message = f"""
Admin verified a {report['disaster_name']} report at {report['location']}.
Please stay alert and follow safety instructions.
"""

    conn.execute("""
    INSERT INTO notifications (title, message, is_read)
    VALUES (?, ?, 0)
    """, (title, message))

    conn.commit()
    conn.close()

    return redirect("/admin_dashboard")


# ---------------- Reject REPORT ----------------
@app.route("/reject/<int:id>")
def reject(id):

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    # GET REPORT DETAILS BEFORE DELETE
    report = conn.execute("""
    SELECT reports.location,
           disasters.disaster_name
    FROM reports
    JOIN disasters
    ON reports.disaster_id = disasters.disaster_id
    WHERE reports.report_id=?
    """, (id,)).fetchone()

    # CREATE REJECTION NOTIFICATION
    title = "False Disaster Alert Removed"

    message = f"""
A reported {report['disaster_name']} alert at {report['location']}
was rejected by admin after verification due to invalid or false information.
"""

    conn.execute("""
    INSERT INTO notifications (title, message, is_read)
    VALUES (?, ?, 0)
    """, (title, message))

    # DELETE REJECTED REPORT
    conn.execute("""
    DELETE FROM reports
    WHERE report_id=?
    """, (id,))

    conn.commit()
    conn.close()

    return redirect("/admin_dashboard")



# ---------------- ANALYTICS ----------------
@app.route("/analytics")
def analytics():

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    data = conn.execute("""

        SELECT disaster_name, COUNT(*) as total
        FROM (

            SELECT disasters.disaster_name
            FROM reports
            JOIN disasters
            ON reports.disaster_id = disasters.disaster_id

            UNION ALL

            SELECT disasters.disaster_name
            FROM admin_reports
            JOIN disasters
            ON admin_reports.disaster_id = disasters.disaster_id

        )

        GROUP BY disaster_name

    """).fetchall()

    conn.close()

    labels = [row["disaster_name"] for row in data]
    values = [row["total"] for row in data]

    return render_template(
        "analytics.html",
        labels=labels,
        values=values
    )


# ---------------- Emergency ----------------
@app.route('/emergency')
def emergency():
    return render_template('emergency.html')



# ---------------- AI CHATBOT ----------------
@app.route("/chat")
def chat():
    return render_template("chatbot.html")


# ---------------- AI CHATBOT ----------------
@app.route("/chatbot", methods=["POST"])
def chatbot():
    user_msg = request.json.get("message", "").lower()

    response = ""

    # 🌊 FLOOD
    if any(word in user_msg for word in ["flood", "water", "rain", "overflow"]):
        response = """🌊 Flood Safety:
• Move to higher ground immediately
• Avoid walking/driving in water
• Turn off electricity
📞 Helpline: 1070"""

    # 🔥 FIRE
    elif any(word in user_msg for word in ["fire", "burn", "smoke"]):
        response = """🔥 Fire Emergency:
• Evacuate immediately
• Use stairs (not lift)
• Cover nose with cloth
📞 Fire: 101"""

    # 🌍 EARTHQUAKE
    elif any(word in user_msg for word in ["earthquake", "tremor", "shake"]):
        response = """🌍 Earthquake Safety:
• Drop, Cover, Hold
• Stay away from windows
• Do not run outside during shaking
📞 Emergency: 112"""

    # ⛰ LANDSLIDE
    elif any(word in user_msg for word in ["landslide", "hill", "mud"]):
        response = """⛰ Landslide Alert:
• Move away from slopes
• Watch for falling rocks
• Stay alert during heavy rain
📞 Helpline: 1078"""

    # 🚨 EMERGENCY CONTACTS
    elif any(word in user_msg for word in ["help", "emergency", "contact", "number"]):
        response = """🚨 Emergency Contacts:
Police: 100
Ambulance: 102
Disaster: 112
Flood: 1070"""

    # 🏠 SHELTER / SAFETY
    elif any(word in user_msg for word in ["shelter", "safe place", "relief"]):
        response = """🏠 Shelter Info:
• Move to nearest relief camp
• Follow government instructions
• Avoid unsafe buildings"""

    # 📍 LOCATION / REPORT
    elif any(word in user_msg for word in ["report", "complain", "incident"]):
        response = """📍 Reporting Help:
• Go to 'Report Disaster' page
• Add location, description, and image
• Your report helps authorities respond faster"""

    # 🤖 DEFAULT
    else:
        response = """ I can help you with:
• Flood, Fire, Earthquake, Landslide
• Emergency contacts
• Safety tips
Type your question!"""

    return {"reply": response}

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)