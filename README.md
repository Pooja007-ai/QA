# Machinery QA Streamlit App

This is a Streamlit-based web application for machinery quality assurance inspections.

## Features

- User registration and login with bcrypt password hashing
- Supports MySQL (via environment variables) or SQLite (default) for database
- Load machine parameters and fill inspection forms for multiple shifts/time slots
- Evaluate measurements against specifications with color-coded status
- Generate PDF reports matching inspection sheet layout
- Save inspection data and reaction records

## Setup

1. Create a virtual environment and activate it:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. (Optional) Configure MySQL database by setting environment variables:
   - DB_HOST
   - DB_USER
   - DB_PASS
   - DB_NAME
   - DB_PORT

4. Run the app:
   ```
   streamlit run app.py
   ```

## Notes

- By default, the app uses SQLite database `qa_app.sqlite` in the working directory.
- For production use, configure MySQL and set environment variables accordingly.
