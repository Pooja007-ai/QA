import streamlit as st # pyright: ignore[reportMissingImports]
import sqlite3
import bcrypt # pyright: ignore[reportMissingImports]
import json
from fpdf import FPDF # pyright: ignore[reportMissingModuleSource]
from datetime import datetime
import os
from dotenv import load_dotenv # pyright: ignore[reportMissingImports]

load_dotenv()

# Database configuration
DB_TYPE = os.getenv('DB_TYPE', 'sqlite')
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_NAME = os.getenv('DB_NAME', 'qa_app.sqlite')
DB_PORT = os.getenv('DB_PORT')

def get_db_connection():
    if DB_TYPE == 'mysql':
        import mysql.connector # pyright: ignore[reportMissingImports]
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT
        )
    else:
        return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    if DB_TYPE == 'mysql':
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE,
                password_hash VARCHAR(255)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS machines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                params TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspections (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                machine_id INT,
                shift VARCHAR(50),
                date DATE,
                measurements TEXT,
                status VARCHAR(50),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (machine_id) REFERENCES machines(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                inspection_id INT,
                reaction TEXT,
                FOREIGN KEY (inspection_id) REFERENCES inspections(id)
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS machines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                params TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                machine_id INTEGER,
                shift TEXT,
                date TEXT,
                measurements TEXT,
                status TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (machine_id) REFERENCES machines(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_id INTEGER,
                reaction TEXT,
                FOREIGN KEY (inspection_id) REFERENCES inspections(id)
            )
        ''')
    # Insert sample machine if not exists
    cursor.execute('SELECT COUNT(*) FROM machines')
    if cursor.fetchone()[0] == 0:
        sample_params = json.dumps([
            {'name': 'Temperature', 'min': 20, 'max': 30},
            {'name': 'Pressure', 'min': 100, 'max': 200},
            {'name': 'Vibration', 'min': 0, 'max': 5}
        ])
        cursor.execute('INSERT INTO machines (name, params) VALUES (?, ?)', ('Machine A', sample_params))
    conn.commit()
    conn.close()

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def login_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    if user and check_password(password, user[1]):
        return user[0]
    return None

def register_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, hash_password(password)))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except:
        conn.close()
        return None

def get_machines():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, params FROM machines')
    machines = cursor.fetchall()
    conn.close()
    return machines

def save_inspection(user_id, machine_id, shift, measurements, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO inspections (user_id, machine_id, shift, date, measurements, status) VALUES (?, ?, ?, ?, ?, ?)',
                   (user_id, machine_id, shift, datetime.now().date().isoformat(), json.dumps(measurements), status))
    inspection_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return inspection_id

def save_reaction(inspection_id, reaction):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO reactions (inspection_id, reaction) VALUES (?, ?)', (inspection_id, reaction))
    conn.commit()
    conn.close()

from fpdf import FPDF
from datetime import datetime

def generate_pdf(inspection_id, measurements, status, machine_name, shift):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Machinery QA Inspection Report", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Machine: {machine_name}", ln=True)
    pdf.cell(200, 10, txt=f"Shift: {shift}", ln=True)
    pdf.cell(200, 10, txt=f"Date: {datetime.now().date()}", ln=True)
    pdf.cell(200, 10, txt=f"Status: {status}", ln=True)
    pdf.cell(200, 10, txt="", ln=True)

    # Add color-coded lights based on measurement values
    for param in measurements:
        value = param['value']
        min_val = param['min']
        max_val = param['max']
        # Determine color: green if within spec, yellow if near boundary, red if out of spec
        if min_val <= value <= max_val:
            color = (0, 255, 0)  # Green
        elif (min_val - 0.1*abs(min_val)) <= value < min_val or max_val < value <= (max_val + 0.1*abs(max_val)):
            color = (255, 255, 0)  # Yellow
        else:
            color = (255, 0, 0)  # Red

        # Set fill color
        pdf.set_fill_color(*color)
        # Draw a small rectangle as light indicator
        pdf.cell(10, 10, '', ln=0, border=1, fill=True)
        # Write parameter text next to the light
        pdf.cell(0, 10, txt=f"{param['name']}: {value} (Spec: {min_val}-{max_val})", ln=True)

    # Placeholder for AI suggestions (to be added later)
    pdf.cell(200, 10, txt="", ln=True)
    pdf.cell(200, 10, txt="AI Inspection Suggestions:", ln=True)
    pdf.cell(200, 10, txt="(Suggestions will be added here)", ln=True)

    pdf.output(f"report_{inspection_id}.pdf")

# Initialize DB
init_db()

# Session state
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'page' not in st.session_state:
    st.session_state.page = 'login'

def main():
    st.title("Machinery QA App")

    if st.session_state.page == 'login':
        st.header("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user_id = login_user(username, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.page = 'main'
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid credentials")
        if st.button("Register"):
            st.session_state.page = 'register'
            st.rerun()

    elif st.session_state.page == 'register':
        st.header("Register")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Register"):
            user_id = register_user(username, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.page = 'main'
                st.success("Registered and logged in!")
                st.rerun()
            else:
                st.error("Username already exists")
        if st.button("Back to Login"):
            st.session_state.page = 'login'
            st.rerun()

    elif st.session_state.page == 'main':
        st.header("Inspection Form")
        machines = get_machines()
        machine_options = {m[1]: m[0] for m in machines}
        machine_name = st.selectbox("Select Machine", list(machine_options.keys()))
        machine_id = machine_options[machine_name]
        shift = st.selectbox("Shift", ["Morning", "Afternoon", "Night"])

        # Get params
        params = json.loads([m[2] for m in machines if m[0] == machine_id][0])
        measurements = []
        for param in params:
            value = st.number_input(f"{param['name']} (Spec: {param['min']}-{param['max']})", min_value=0.0)
            measurements.append({**param, 'value': value})

        if st.button("Evaluate"):
            status = "Pass"
            for m in measurements:
                if not (m['min'] <= m['value'] <= m['max']):
                    status = "Fail"
                    break
            st.write(f"Status: {status}")
            if status == "Pass":
                st.success("All measurements within spec")
            else:
                st.error("Some measurements out of spec")
                reaction = st.text_area("Reaction/Comments")
                if st.button("Save Inspection"):
                    inspection_id = save_inspection(st.session_state.user_id, machine_id, shift, measurements, status)
                    if reaction:
                        save_reaction(inspection_id, reaction)
                    generate_pdf(inspection_id, measurements, status, machine_name, shift)
                    st.success("Inspection saved and PDF generated!")

        if st.button("Logout"):
            st.session_state.user_id = None
            st.session_state.page = 'login'
            st.rerun()

if __name__ == "__main__":
    main()
