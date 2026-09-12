from flask import Flask, request, jsonify
from flask_cors import CORS
from ai_agent import analyze_student
import sqlite3

app = Flask(__name__)
CORS(app)

DB_NAME = "learnintelli.db"

DEMO_STUDENTS = [
    "Krishna",
    "Srushti",
    "Manali",
    "Harshada",
    "Tanishka",
    "Khushi"
]


# =========================================================
# DATABASE HELPERS
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(cursor, table, column, definition):
    columns = [
        row["name"]
        for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()
    ]

    if column not in columns:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            concept TEXT DEFAULT 'Photosynthesis',
            quiz_score REAL,
            concept_score REAL,
            visualization_score REAL,
            application_score REAL,
            mastery REAL,
            learning_gap TEXT,
            recommended_action TEXT
        )
    """)

    ensure_column(cursor, "students", "quiz_attempted", "INTEGER DEFAULT 0")
    ensure_column(cursor, "students", "visual_completed", "INTEGER DEFAULT 0")
    ensure_column(cursor, "students", "mission_attempted", "INTEGER DEFAULT 0")
    ensure_column(cursor, "students", "mission_completed", "INTEGER DEFAULT 0")
    ensure_column(cursor, "students", "teach_back_score", "REAL")
    ensure_column(cursor, "students", "teach_back_completed", "INTEGER DEFAULT 0")
    ensure_column(cursor, "students", "mission_xp", "INTEGER DEFAULT 0")
    ensure_column(cursor, "students", "completion_percent", "REAL DEFAULT 0")
    ensure_column(cursor, "students", "completed_activities", "INTEGER DEFAULT 0")
    ensure_column(cursor, "students", "last_activity", "TEXT")
    ensure_column(cursor, "students", "ai_reason", "TEXT")

    # Remove duplicate demo students, keeping the oldest record.
    for name in DEMO_STUDENTS:
        rows = cursor.execute(
            "SELECT id FROM students WHERE LOWER(name)=LOWER(?) ORDER BY id",
            (name,)
        ).fetchall()

        if len(rows) > 1:
            keep_id = rows[0]["id"]
            cursor.execute(
                "DELETE FROM students WHERE LOWER(name)=LOWER(?) AND id<>?",
                (name, keep_id)
            )

    # Clear old prototype hard-coded scores only when no real activity
    # has been recorded for that student.
    cursor.execute("""
        UPDATE students
        SET
            quiz_score = NULL,
            concept_score = NULL,
            visualization_score = NULL,
            application_score = NULL,
            mastery = NULL,
            learning_gap = NULL,
            recommended_action = NULL,
            quiz_attempted = 0,
            visual_completed = 0,
            mission_attempted = 0,
            mission_completed = 0,
            teach_back_score = NULL,
            teach_back_completed = 0,
            mission_xp = 0,
            completion_percent = 0,
            completed_activities = 0,
            last_activity = NULL,
            ai_reason = NULL
        WHERE
            quiz_attempted = 0
            AND visual_completed = 0
            AND mission_attempted = 0
            AND teach_back_completed = 0
            AND (
                quiz_score IS NOT NULL
                OR concept_score IS NOT NULL
                OR visualization_score IS NOT NULL
                OR application_score IS NOT NULL
                OR mastery IS NOT NULL
            )
    """)

    # Demo classroom roster. Names are fixed for the prototype;
    # scores and completion are NOT fixed.
    for name in DEMO_STUDENTS:
        exists = cursor.execute(
            "SELECT id FROM students WHERE LOWER(name)=LOWER(?)",
            (name,)
        ).fetchone()

        if not exists:
            cursor.execute("""
                INSERT INTO students (name, concept)
                VALUES (?, 'Photosynthesis')
            """, (name,))

    conn.commit()
    conn.close()


# =========================================================
# CALCULATIONS
# =========================================================

def calculate_metrics(student):

    score_fields = [
        ("quiz_score", "quiz_attempted"),
        ("visualization_score", "visual_completed"),
        ("application_score", "mission_attempted"),
        ("teach_back_score", "teach_back_completed")
    ]

    scores = []

    for score_field, attempted_field in score_fields:
        if bool(student[attempted_field]) and student[score_field] is not None:
            scores.append(float(student[score_field]))

    mastery = round(sum(scores) / len(scores)) if scores else None

    completed_activities = sum(
        1
        for _, attempted_field in score_fields
        if bool(student[attempted_field])
    )

    completion_percent = round((completed_activities / 4) * 100)

    return mastery, completion_percent, completed_activities


def fetch_student(conn, student_id=None, student_name=None):

    if student_id:
        student = conn.execute(
            "SELECT * FROM students WHERE id=?",
            (student_id,)
        ).fetchone()

        if student:
            return student

    if student_name:
        return conn.execute(
            """
            SELECT * FROM students
            WHERE LOWER(name)=LOWER(?)
            ORDER BY id
            LIMIT 1
            """,
            (student_name,)
        ).fetchone()

    return None


def update_student_metrics(conn, student_id):

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (student_id,)
    ).fetchone()

    mastery, completion_percent, completed_activities = calculate_metrics(
        student
    )

    conn.execute("""
        UPDATE students
        SET mastery=?,
            completion_percent=?,
            completed_activities=?
        WHERE id=?
    """, (
        mastery,
        completion_percent,
        completed_activities,
        student_id
    ))

    return conn.execute(
        "SELECT * FROM students WHERE id=?",
        (student_id,)
    ).fetchone()


# =========================================================
# AI AGENT - STUDENT ANALYSIS
# =========================================================

@app.route("/api/ai-agent/analyze", methods=["POST"])
def analyze():

    data = request.json or {}

    student_id = data.get("student_id")
    student_name = data.get("student_name", "Krishna")
    concept = data.get("concept", "Photosynthesis")
    activity_type = data.get("activity_type")

    conn = get_connection()

    student = fetch_student(
        conn,
        student_id=student_id,
        student_name=student_name
    )

    if not student:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (name, concept) VALUES (?, ?)",
            (student_name, concept)
        )
        conn.commit()
        student = fetch_student(conn, student_name=student_name)

    actual_id = student["id"]

    # Record ONLY the activity that really happened.
    if activity_type == "quiz":

        quiz_score = data.get("quiz_score")

        if quiz_score is not None:
            quiz_score = max(0, min(100, float(quiz_score)))

            conn.execute("""
                UPDATE students
                SET quiz_score=?,
                    concept_score=?,
                    quiz_attempted=1,
                    last_activity='Quiz'
                WHERE id=?
            """, (
                quiz_score,
                quiz_score,
                actual_id
            ))

    elif activity_type == "visual":

        conn.execute("""
            UPDATE students
            SET visualization_score=100,
                visual_completed=1,
                last_activity='Visual Learning'
            WHERE id=?
        """, (actual_id,))

    elif activity_type == "mission":

        mission_score = data.get("application_score")

        if mission_score is not None:
            mission_score = max(0, min(100, float(mission_score)))

            mission_completed = 1 if mission_score >= 100 else 0

            conn.execute("""
                UPDATE students
                SET application_score=?,
                    mission_attempted=1,
                    mission_completed=?,
                    mission_xp=?,
                    last_activity='Smart Mission'
                WHERE id=?
            """, (
                mission_score,
                mission_completed,
                int(data.get("mission_xp", 0)),
                actual_id
            ))

    elif activity_type == "teach_back":

        teach_score = data.get("teach_back_score")

        if teach_score is not None:
            teach_score = max(0, min(100, float(teach_score)))

            conn.execute("""
                UPDATE students
                SET teach_back_score=?,
                    teach_back_completed=1,
                    last_activity='Teach It Back'
                WHERE id=?
            """, (
                teach_score,
                actual_id
            ))

    student = update_student_metrics(conn, actual_id)

    # AI receives ACTUAL database activity state.
    ai_input = {
        "quiz_score": student["quiz_score"],
        "concept_score": student["concept_score"],
        "visualization_score": student["visualization_score"],
        "application_score": student["application_score"],
        "teach_back_score": student["teach_back_score"],
        "quiz_attempted": bool(student["quiz_attempted"]),
        "visual_completed": bool(student["visual_completed"]),
        "mission_attempted": bool(student["mission_attempted"]),
        "mission_completed": bool(student["mission_completed"]),
        "teach_back_completed": bool(student["teach_back_completed"])
    }

    result = analyze_student(ai_input)

    conn.execute("""
        UPDATE students
        SET learning_gap=?,
            recommended_action=?,
            ai_reason=?
        WHERE id=?
    """, (
        result["learning_gap"],
        result["recommended_action"],
        result.get("reason", ""),
        actual_id
    ))

    conn.commit()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (actual_id,)
    ).fetchone()

    conn.close()

    return jsonify({
        "status": "success",
        "student_id": actual_id,
        "agent_result": result,
        "student": dict(student)
    })


# =========================================================
# TEACH IT BACK
# =========================================================

@app.route("/api/ai-agent/teach-back", methods=["POST"])
def teach_back():

    data = request.json or {}

    student_id = data.get("student_id")
    student_name = data.get("student_name", "Krishna")
    concept = data.get("concept", "Photosynthesis")
    explanation = data.get("explanation", "").strip().lower()

    if not explanation:
        return jsonify({
            "status": "error",
            "message": "Explanation is required."
        }), 400

    keywords = [
        "sunlight",
        "carbon dioxide",
        "water",
        "glucose",
        "oxygen",
        "chlorophyll"
    ]

    found_keywords = [
        word for word in keywords
        if word in explanation
    ]

    coverage = round(
        (len(found_keywords) / len(keywords)) * 100
    )

    if coverage >= 80:
        understanding = "Strong Understanding"
        feedback = (
            "Excellent! Your explanation covers most of the "
            "important concepts of photosynthesis."
        )
        learning_gap = "No Major Gap"
        recommended_action = "Continue"

    elif coverage >= 50:
        understanding = "Developing Understanding"
        feedback = (
            "Good start. Your explanation is partly correct, "
            "but some important concepts are still missing."
        )
        learning_gap = "Conceptual Gap"
        recommended_action = "Visual Learning"

    else:
        understanding = "Needs Improvement"
        feedback = (
            "Your explanation is missing several important concepts. "
            "Review the visual explanation and try again."
        )
        learning_gap = "Conceptual Gap"
        recommended_action = "Visual Learning"

    missing = [
        word for word in keywords
        if word not in found_keywords
    ]

    if missing:
        feedback += " Consider reviewing: " + ", ".join(missing) + "."

    conn = get_connection()

    student = fetch_student(
        conn,
        student_id=student_id,
        student_name=student_name
    )

    if not student:
        conn.execute(
            "INSERT INTO students (name, concept) VALUES (?, ?)",
            (student_name, concept)
        )
        conn.commit()
        student = fetch_student(conn, student_name=student_name)

    actual_id = student["id"]

    conn.execute("""
        UPDATE students
        SET teach_back_score=?,
            teach_back_completed=1,
            learning_gap=?,
            recommended_action=?,
            ai_reason=?,
            last_activity='Teach It Back'
        WHERE id=?
    """, (
        coverage,
        learning_gap,
        recommended_action,
        feedback,
        actual_id
    ))

    update_student_metrics(conn, actual_id)
    conn.commit()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (actual_id,)
    ).fetchone()

    conn.close()

    result = {
        "understanding": understanding,
        "feedback": feedback,
        "learning_gap": learning_gap,
        "recommended_action": recommended_action,
        "coverage": coverage
    }

    return jsonify({
        "status": "success",
        "student_id": actual_id,
        "agent_result": result,
        "student": dict(student)
    })


# =========================================================
# TEACHER DASHBOARD
# =========================================================

@app.route("/api/teacher/students", methods=["GET"])
def get_students():

    conn = get_connection()

    students = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM students ORDER BY id"
        ).fetchall()
    ]

    conn.close()

    return jsonify({
        "status": "success",
        "students": students
    })


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":
    init_database()
    app.run(debug=True)