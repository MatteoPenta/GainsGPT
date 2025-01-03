import streamlit as st
import sqlite3
from datetime import datetime
import json
import os
import requests

###############################################################################
# 1) Hugging Face Inference API Configuration
###############################################################################
# Change MODEL_ID or HF_API_KEY as needed
MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"  
HF_API_KEY = os.getenv("HF_TOKEN", "YOUR_HF_API_TOKEN")
HF_API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"

def call_hf_inference_api(prompt: str, max_tokens=1024, temperature=0.1) -> str:
    """
    Calls the Hugging Face Inference API for text generation.
    Returns the model's generated text.
    """
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "do_sample": False,
            "return_full_text": False
        }
    }
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        output = response.json()
        if isinstance(output, list) and len(output) > 0:
            return output[0].get("generated_text", "")
        elif isinstance(output, dict) and "generated_text" in output:
            return output["generated_text"]
        else:
            return ""
    except Exception as e:
        print("Error calling HF Inference API:", e)
        return ""

###############################################################################
# 2) Database Setup and Functions
###############################################################################
def init_db():
    conn = sqlite3.connect('workout_app.db')
    cursor = conn.cursor()
    
    # Tables creation
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS workout_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_name TEXT,
        date TEXT,
        raw_text TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise_name TEXT UNIQUE
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exercise_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_log_id INTEGER,
        exercise_id INTEGER,
        sets INTEGER,
        reps INTEGER,
        weight REAL,
        FOREIGN KEY(workout_log_id) REFERENCES workout_logs(id),
        FOREIGN KEY(exercise_id) REFERENCES exercises(id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_log_id INTEGER,
        exercise_id INTEGER,
        note_text TEXT,
        category TEXT,
        sentiment TEXT,
        FOREIGN KEY(workout_log_id) REFERENCES workout_logs(id),
        FOREIGN KEY(exercise_id) REFERENCES exercises(id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_log_id INTEGER,
        metric_name TEXT,
        metric_value TEXT,
        sentiment TEXT,
        FOREIGN KEY(workout_log_id) REFERENCES workout_logs(id)
    )
    ''')
    
    conn.commit()
    conn.close()

def insert_workout_log(session_name: str, date_str: str, raw_text: str):
    conn = sqlite3.connect('workout_app.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO workout_logs (session_name, date, raw_text)
        VALUES (?, ?, ?)
    ''', (session_name, date_str, raw_text))
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    return log_id

def get_exercise_id(exercise_name: str):
    conn = sqlite3.connect('workout_app.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM exercises WHERE exercise_name = ?', (exercise_name,))
    result = cursor.fetchone()
    if not result:
        cursor.execute('INSERT INTO exercises (exercise_name) VALUES (?)', (exercise_name,))
        conn.commit()
        exercise_id = cursor.lastrowid
    else:
        exercise_id = result[0]
    conn.close()
    return exercise_id

def insert_exercise_data(workout_log_id: int, exercise_id: int, sets: int, reps: int, weight: float):
    conn = sqlite3.connect('workout_app.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO exercise_data (workout_log_id, exercise_id, sets, reps, weight)
        VALUES (?, ?, ?, ?, ?)
    ''', (workout_log_id, exercise_id, sets, reps, weight))
    conn.commit()
    conn.close()

def insert_note(workout_log_id: int, exercise_id: int, note_text: str, category: str, sentiment: str):
    conn = sqlite3.connect('workout_app.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO notes (workout_log_id, exercise_id, note_text, category, sentiment)
        VALUES (?, ?, ?, ?, ?)
    ''', (workout_log_id, exercise_id if exercise_id else None, note_text, category, sentiment))
    conn.commit()
    conn.close()

def insert_daily_metric(workout_log_id: int, metric_name: str, metric_value: str, sentiment: str):
    conn = sqlite3.connect('workout_app.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO daily_metrics (workout_log_id, metric_name, metric_value, sentiment)
        VALUES (?, ?, ?, ?)
    ''', (workout_log_id, metric_name, metric_value, sentiment))
    conn.commit()
    conn.close()

###############################################################################
# 3) Prompt Building & Parsing Logic
###############################################################################
def build_system_prompt_with_examples() -> str:
    example_input_1 = """
Prior notes:
- Pretty tired after three nights of bad sleep.
Pull ups
- 6x4 15kg
Inclined Bench press
- 3xRPE 10 50kg 9-7-6
- AMRAP 40kg 7reps
- Notes: left shoulder felt fine
"""
    example_output_1 = {
        "metrics": [
            {"metric_name": "SleepQuality", "metric_value": "poor (3 nights bad sleep)", "sentiment": "negative"}
        ],
        "exercises": [
            {
                "exercise_name": "Pull ups",
                "sets": 6,
                "reps": 4,
                "weight": 15.0,
                "notes": []
            },
            {
                "exercise_name": "Inclined Bench press",
                "sets": 3,
                "reps": None,
                "weight": 50.0,
                "notes": [
                    {"note_text": "AMRAP 40kg for 7 reps", "sentiment": "neutral"},
                    {"note_text": "left shoulder felt fine", "sentiment": "positive"}
                ]
            }
        ],
        "general_notes": []
    }

    example_input_2 = """
Prior notes:
- Body state: left shoulder less inflamed, left trap pain
Military press
- 6x6 50kg
- Notes: felt good. Last set @8.5
Pull ups
- 6x4 +12.5kg
"""
    example_output_2 = {
        "metrics": [
            {"metric_name": "ShoulderInflammation", "metric_value": "less inflamed", "sentiment": "improving"},
            {"metric_name": "TrapPain", "metric_value": "present", "sentiment": "neutral"}
        ],
        "exercises": [
            {
                "exercise_name": "Military press",
                "sets": 6,
                "reps": 6,
                "weight": 50.0,
                "notes": [
                    {"note_text": "felt good, last set @8.5", "sentiment": "positive"}
                ]
            },
            {
                "exercise_name": "Pull ups",
                "sets": 6,
                "reps": 4,
                "weight": 12.5,
                "notes": []
            }
        ],
        "general_notes": []
    }

    system_str = f"""
You are a helpful assistant that extracts structured workout information from text logs.
We want valid JSON with keys: "metrics", "exercises", "general_notes".
- "metrics": daily metrics (sleep, pain, energy, etc.).
- "exercises": parse sets, reps, weight, plus any notes relevant to that exercise.
- "general_notes": additional remarks not tied to a specific exercise.

## EXAMPLE 1
Input:
{example_input_1}
Output (JSON):
{json.dumps(example_output_1, indent=2)}

## EXAMPLE 2
Input:
{example_input_2}
Output (JSON):
{json.dumps(example_output_2, indent=2)}

Now parse the following text. Respond with valid JSON only. DO NOT include the input text or the examples above in your response.
"""
    return system_str

def categorize_and_extract_features(raw_text: str) -> dict:
    """
    Build the final prompt, call the HF Inference API, parse out JSON, return structured data.
    """
    system_prompt = build_system_prompt_with_examples()
    prompt_text = f"""{system_prompt}\nNEW INPUT:\n\"\"\"{raw_text}\"\"\"\n"""

    generated_text = call_hf_inference_api(prompt_text)
    
    # DEBUG
    print("Generated Text:", generated_text)
    
    # Attempt to extract JSON from the text
    start_idx = generated_text.find("{")
    end_idx = generated_text.rfind("}")
    if start_idx == -1 or end_idx == -1:
        return {
            "metrics": [],
            "exercises": [],
            "general_notes": []
        }

    json_str = generated_text[start_idx:end_idx+1]
    try:
        structured_data = json.loads(json_str)
    except:
        structured_data = {
            "metrics": [],
            "exercises": [],
            "general_notes": []
        }
    return structured_data

###############################################################################
# 4) Edit / Delete Functions
###############################################################################
def delete_workout_log(log_id: int):
    """
    Deletes all associated data (notes, metrics, exercises_data) for the workout,
    then removes the workout_log entry itself.
    """
    conn = sqlite3.connect('workout_app.db')
    cursor = conn.cursor()
    
    # Remove data from child tables
    cursor.execute("DELETE FROM daily_metrics WHERE workout_log_id = ?", (log_id,))
    cursor.execute("DELETE FROM exercise_data WHERE workout_log_id = ?", (log_id,))
    cursor.execute("DELETE FROM notes WHERE workout_log_id = ?", (log_id,))
    
    # Finally remove the workout_log
    cursor.execute("DELETE FROM workout_logs WHERE id = ?", (log_id,))
    
    conn.commit()
    conn.close()

def edit_workout_log(log_id: int, new_session_name: str, new_date_str: str, new_raw_text: str):
    """
    1) Remove old child data for this workout (metrics, exercise_data, notes).
    2) Update the workout_log with new data.
    3) Re-parse the raw text with the LLM to generate new structured data.
    4) Insert newly parsed data into the child tables.
    """
    conn = sqlite3.connect('workout_app.db')
    cursor = conn.cursor()
    
    # Delete old references
    cursor.execute("DELETE FROM daily_metrics WHERE workout_log_id = ?", (log_id,))
    cursor.execute("DELETE FROM exercise_data WHERE workout_log_id = ?", (log_id,))
    cursor.execute("DELETE FROM notes WHERE workout_log_id = ?", (log_id,))
    
    # Update the workout_logs entry
    cursor.execute("""
        UPDATE workout_logs
        SET session_name = ?, date = ?, raw_text = ?
        WHERE id = ?
    """, (new_session_name, new_date_str, new_raw_text, log_id))
    conn.commit()
    conn.close()

    # Re-run parsing for the updated text
    structured_data = categorize_and_extract_features(new_raw_text)
    
    # Insert newly parsed data
    # (We do it the same way as in process_workout_entry, but referencing our existing log_id)
    for metric in structured_data.get("metrics", []):
        metric_name = metric.get("metric_name", "")
        metric_value = metric.get("metric_value", "")
        sentiment = metric.get("sentiment", "")
        insert_daily_metric(log_id, metric_name, metric_value, sentiment)
    
    for exercise in structured_data.get("exercises", []):
        exercise_name = exercise.get("exercise_name", "")
        sets_ = exercise.get("sets", 0)
        reps_ = exercise.get("reps", 0)
        weight_ = exercise.get("weight", 0.0)
        
        exercise_id = get_exercise_id(exercise_name)
        insert_exercise_data(log_id, exercise_id, sets_, reps_, weight_)
        
        for note in exercise.get("notes", []):
            note_text = note.get("note_text", "")
            note_sentiment = note.get("sentiment", "")
            insert_note(log_id, exercise_id, note_text, "exercise_note", note_sentiment)
    
    for note in structured_data.get("general_notes", []):
        note_text = note.get("note_text", "")
        category = note.get("category", "")
        sentiment = note.get("sentiment", "")
        insert_note(log_id, None, note_text, category, sentiment)

###############################################################################
# 5) Core process function for new logs
###############################################################################
def process_workout_entry(session_name: str, date_str: str, raw_text: str):
    log_id = insert_workout_log(session_name, date_str, raw_text)
    structured_data = categorize_and_extract_features(raw_text)
    
    # DEBUG
    print("Structured Data:", structured_data)
    
    # If structured_data contains empty objects, issue a warning to the user
    if not structured_data.get("metrics") and not structured_data.get("exercises") and not structured_data.get("general_notes"):
        st.warning("The AI model could not extract any structured data from your workout notes.")
        return

    # Store metrics
    for metric in structured_data.get("metrics", []):
        metric_name = metric.get("metric_name", "")
        metric_value = metric.get("metric_value", "")
        sentiment = metric.get("sentiment", "")
        insert_daily_metric(log_id, metric_name, metric_value, sentiment)
    
    # Store exercises
    for exercise in structured_data.get("exercises", []):
        exercise_name = exercise.get("exercise_name", "")
        sets_ = exercise.get("sets", 0)
        reps_ = exercise.get("reps", 0)
        weight_ = exercise.get("weight", 0.0)
        
        exercise_id = get_exercise_id(exercise_name)
        insert_exercise_data(log_id, exercise_id, sets_, reps_, weight_)
        
        for note in exercise.get("notes", []):
            note_text = note.get("note_text", "")
            note_sentiment = note.get("sentiment", "")
            insert_note(log_id, exercise_id, note_text, "exercise_note", note_sentiment)
    
    # Store general notes
    for note in structured_data.get("general_notes", []):
        note_text = note.get("note_text", "")
        category = note.get("category", "")
        sentiment = note.get("sentiment", "")
        insert_note(log_id, None, note_text, category, sentiment)

###############################################################################
# 6) Streamlit App with Edit/Delete in the "Log" section
###############################################################################
def main():
    st.title("GainsGPT")
    st.write("A workout log and exercise tracker powered by AI.")
    
    init_db()
    
    page = st.sidebar.selectbox("Navigation", ["Log", "Exercises", "Tracking"])
    
    if page == "Log":
        st.subheader("Add a New Workout Log")
        
        session_name = st.text_input("Session Name", "")
        date_val = st.date_input("Date")
        date_str = date_val.strftime("%Y-%m-%d")
        
        raw_text = st.text_area("Write your workout notes here:")
        
        if st.button("Submit Workout Log"):
            if session_name and raw_text:
                with st.spinner("Parsing your log via Hugging Face Inference API..."):
                    process_workout_entry(session_name, date_str, raw_text)
                st.success("Workout log submitted successfully!")
            else:
                st.warning("Please provide both a session name and some notes.")
        
        # Existing Logs
        st.subheader("Existing Logs")
        conn = sqlite3.connect('workout_app.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, session_name, date, raw_text FROM workout_logs ORDER BY id DESC")
        logs = cursor.fetchall()
        for log in logs:
           log_id, s_name, dt, text = log
           with st.expander(f"Log ID: {log_id} - {s_name} ({dt})"):
              st.write(text)
              
              # EDIT Section
              edit_button = st.button(f"Edit Log {log_id}", key=f"edit_{log_id}")
              delete_button = st.button(f"Delete Log {log_id}", key=f"delete_{log_id}")
              if edit_button:
                    st.info("Edit the workout below, then press 'Update'")
                    new_session_name = st.text_input("Session Name", value=s_name, key=f"ses_{log_id}")
                    new_date_val = st.date_input("Date", value=datetime.strptime(dt, "%Y-%m-%d"), key=f"dat_{log_id}")
                    new_date_str = new_date_val.strftime("%Y-%m-%d")
                    new_raw_text = st.text_area("Workout Notes", value=text, key=f"raw_{log_id}")
                    if st.button("Update", key=f"update_{log_id}"):
                       with st.spinner("Re-parsing and updating..."):
                          edit_workout_log(log_id, new_session_name, new_date_str, new_raw_text)
                       st.success("Workout updated successfully!")
                       st.rerun()  # Refresh the page to show updated data
              # Deletion logic without st.confirm_dialog
              if delete_button:
                    # st.warning(f"Are you sure you want to delete log {log_id}? This action cannot be undone.")
                    # if f"confirm_delete_{log_id}" not in st.session_state:
                    #     st.session_state[f"confirm_delete_{log_id}"] = False

                    # if st.button(f"Yes, delete log {log_id}", key=f"confirm_delete_{log_id}"):
                    #     st.session_state[f"confirm_delete_{log_id}"] = True

                    # if st.session_state[f"confirm_delete_{log_id}"]:
                    with st.spinner(f"Deleting log {log_id}..."):
                        delete_workout_log(log_id)
                    st.warning(f"Log {log_id} has been deleted.")
                    # st.session_state[f"confirm_delete_{log_id}"] = False
                    st.rerun()  # Refresh the page
                    
        conn.close()
    
    elif page == "Exercises":
        st.subheader("Exercises Database")
        conn = sqlite3.connect('workout_app.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, exercise_name FROM exercises ORDER BY exercise_name")
        exercises_list = cursor.fetchall()
        
        if exercises_list:
            exercise_names = [ex[1] for ex in exercises_list]
            selected_exercise = st.selectbox("Select an exercise:", exercise_names)
            
            # Find exercise_id
            exercise_id = None
            for ex in exercises_list:
                if ex[1] == selected_exercise:
                    exercise_id = ex[0]
                    break
            
            if exercise_id:
                # Show sets/reps/weight data
                cursor.execute('''
                    SELECT w.date, ed.sets, ed.reps, ed.weight
                    FROM exercise_data ed
                    JOIN workout_logs w ON ed.workout_log_id = w.id
                    WHERE ed.exercise_id = ?
                    ORDER BY w.date
                ''', (exercise_id,))
                data_rows = cursor.fetchall()
                
                st.write(f"**Tracking data for {selected_exercise}:**")
                if data_rows:
                    for row in data_rows:
                        workout_date, sets_, reps_, weight_ = row
                        st.write(f"- **Date**: {workout_date}, Sets: {sets_}, Reps: {reps_}, Weight: {weight_}")
                else:
                    st.write("No data for this exercise yet.")
                
                st.write("---")
                st.write(f"**Notes for {selected_exercise}:**")
                cursor.execute('''
                    SELECT w.date, n.note_text, n.sentiment
                    FROM notes n
                    JOIN workout_logs w ON n.workout_log_id = w.id
                    WHERE n.exercise_id = ?
                    ORDER BY w.date
                ''', (exercise_id,))
                note_rows = cursor.fetchall()
                if note_rows:
                    for row in note_rows:
                        nd, note_text, senti = row
                        st.write(f"- **Date**: {nd}, **Note**: {note_text}, **Sentiment**: {senti}")
                else:
                    st.write("No notes for this exercise yet.")
        else:
            st.write("No exercises tracked yet.")
        
        conn.close()
    
    elif page == "Tracking":
        st.subheader("Tracked Metrics")
        conn = sqlite3.connect('workout_app.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT w.date, d.metric_name, d.metric_value, d.sentiment
            FROM daily_metrics d
            JOIN workout_logs w ON d.workout_log_id = w.id
            ORDER BY w.date
        ''')
        metrics_rows = cursor.fetchall()
        
        if metrics_rows:
            for row in metrics_rows:
                dt, m_name, m_val, senti = row
                st.write(f"- **Date**: {dt} | **Metric**: {m_name} | **Value**: {m_val} | **Sentiment**: {senti}")
        else:
            st.write("No metrics recorded yet.")
        
        conn.close()

if __name__ == "__main__":
    main()