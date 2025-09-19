import streamlit as st
import sqlite3
import bcrypt
import json
from fpdf import FPDF
from datetime import datetime
import os
from groq import Groq

# -------------------------
# CONFIG
# -------------------------
GROQ_API_KEY = "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"  # replace with your Groq key
DB_NAME = "qa_app.sqlite"

client = Groq(api_key=GROQ_API_KEY)


# -------------------------
# DATABASE SETUP
# -------------------------
def get_db_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

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


# -------------------------
# AUTH HELPERS
# -------------------------
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
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                       (username, hash_password(password)))
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
    cursor.execute(
        'INSERT INTO inspections (user_id, machine_id, shift, date, measurements, status) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, machine_id, shift, datetime.now().date().isoformat(), json.dumps(measurements), status)
    )
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


# -------------------------
# AI HELPERS (Groq)
# -------------------------
def generate_inspection_suggestions(measurements, status):
    """
    Use Groq to generate AI suggestions for inspection.
    """
    user_prompt = f"""
    The inspection status is {status}.
    Measurements:
    {json.dumps(measurements, indent=2)}
    Give short actionable QA improvement suggestions.
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.3,
        max_tokens=250,
    )
    return response.choices[0].message.content.strip()


def get_chatbot_response(user_input):
    """
    Restricted chatbot: only MachineryQA project-related.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a digital quality assurance assistant for the MachineryQA project. "
                "You ONLY answer questions related to machine inspection, QA processes, "
                "and this project. If asked about unrelated topics, respond with: "
                "'I can only help with MachineryQA-related queries.'"
            )
        },
        {"role": "user", "content": user_input},
    ]

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.2,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


# -------------------------
# PDF GENERATION
# -------------------------
def generate_pdf(inspection_id, measurements, status, machine_name, shift, suggestions=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Machinery QA Inspection Report", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Machine: {machine_name}", ln=True)
    pdf.cell(200, 10, txt=f"Shift: {shift}", ln=True)
    pdf.cell(200, 10, txt=f"Date: {datetime.now().date()}", ln=True)
    pdf.cell(200, 10, txt=f"Status: {status}", ln=True)
    pdf.cell(200, 10, txt="", ln=True)

    for param in measurements:
        value = param['value']
        min_val = param['min']
        max_val = param['max']
        if min_val <= value <= max_val:
            color = (0, 255, 0)  # Green
        elif (min_val - 0.1*abs(min_val)) <= value < min_val or max_val < value <= (max_val + 0.1*abs(max_val)):
            color = (255, 255, 0)  # Yellow
        else:
            color = (255, 0, 0)  # Red
        pdf.set_fill_color(*color)
        pdf.cell(10, 10, '', ln=0, border=1, fill=True)
        pdf.cell(0, 10, txt=f"{param['name']}: {value} (Spec: {min_val}-{max_val})", ln=True)

    pdf.cell(200, 10, txt="", ln=True)
    pdf.cell(200, 10, txt="AI Inspection Suggestions:", ln=True)
    if suggestions:
        for line in suggestions.split('\n'):
            pdf.cell(200, 10, txt=line, ln=True)
    else:
        pdf.cell(200, 10, txt="(No suggestions available)", ln=True)

    pdf.output(f"report_{inspection_id}.pdf")


# -------------------------
# STREAMLIT UI
# -------------------------
init_db()

if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'page' not in st.session_state:
    st.session_state.page = 'login'
if 'status' not in st.session_state:
    st.session_state.status = None
if 'reaction' not in st.session_state:
    st.session_state.reaction = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def chatbot_ui():
    st.header("🤖 QA Chatbot")
    user_input = st.text_input("Ask your QA assistant:")

    if st.button("Send") and user_input:
        reply = get_chatbot_response(user_input)
        st.session_state.chat_history.append(("You", user_input))
        st.session_state.chat_history.append(("QA Bot", reply))

    for speaker, msg in st.session_state.chat_history:
        st.markdown(f"**{speaker}:** {msg}")


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

        params = json.loads([m[2] for m in machines if m[0] == machine_id][0])
        measurements = []
        for param in params:
            value = st.number_input(f"{param['name']} (Spec: {param['min']}-{param['max']})", min_value=0.0)
            measurements.append({**param, 'value': value})

        if st.button("Evaluate"):
            st.session_state.status = "Pass"
            for m in measurements:
                if not (m['min'] <= m['value'] <= m['max']):
                    st.session_state.status = "Fail"
                    break
            st.write(f"Status: {st.session_state.status}")
            if st.session_state.status == "Pass":
                st.success("All measurements within spec")
            else:
                st.error("Some measurements out of spec")
                st.session_state.reaction = st.text_area("Reaction/Comments")

        if st.button("Save Inspection"):
            if not st.session_state.status:
                st.error("Please click 'Evaluate' before saving.")
            else:
                inspection_id = save_inspection(
                    st.session_state.user_id, machine_id, shift, measurements, st.session_state.status
                )
                if st.session_state.reaction:
                    save_reaction(inspection_id, st.session_state.reaction)

                suggestions = generate_inspection_suggestions(measurements, st.session_state.status)
                generate_pdf(inspection_id, measurements, st.session_state.status, machine_name, shift, suggestions)

                pdf_path = f"report_{inspection_id}.pdf"
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.success("Inspection saved and PDF generated!")
                st.download_button(
                    label="Download Inspection Report PDF",
                    data=pdf_bytes,
                    file_name=pdf_path,
                    mime="application/pdf"
                )
                st.write("### PDF Preview")
                st.components.v1.iframe(pdf_path, height=600)

        st.write("---")
        chatbot_ui()

        if st.button("Logout"):
            st.session_state.user_id = None
            st.session_state.page = 'login'
            st.rerun()


if __name__ == "__main__":
    main()
