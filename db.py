"""
db.py — SQLite storage for ER Ready.

Replaces the earlier local-JSON-file storage. Two tables:
  - profiles: one row per health wallet profile
  - queue: one row per "sent ahead" intake summary

SQLite's built into Python (no extra service to run), and handles
concurrent readers/writers safely enough for a small demo deployment —
which matters now that the app is public and more than one person can
use it at the same time.
"""

import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "data" / "er_ready.db"
DB_PATH.parent.mkdir(exist_ok=True)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                dob TEXT DEFAULT '',
                emergency_contact TEXT DEFAULT '',
                allergies TEXT DEFAULT '',
                medications TEXT DEFAULT '',
                chronic_conditions TEXT DEFAULT '[]',
                insurance TEXT DEFAULT '',
                member_id TEXT DEFAULT '',
                group_number TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id TEXT PRIMARY KEY,
                profile_id TEXT,
                name TEXT,
                dob TEXT,
                allergies TEXT,
                medications TEXT,
                chronic_conditions TEXT DEFAULT '[]',
                insurance TEXT,
                member_id TEXT,
                group_number TEXT,
                emergency_contact TEXT,
                symptoms TEXT DEFAULT '[]',
                pain INTEGER,
                note TEXT,
                priority TEXT,
                hospital TEXT,
                eta_minutes INTEGER,
                photo_path TEXT DEFAULT '',
                created_at TEXT
            )
        """)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def get_all_profiles() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM profiles").fetchall()
    return {row["id"]: _profile_row_to_dict(row) for row in rows}


def get_profile(profile_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return _profile_row_to_dict(row) if row else None


def save_profile(profile_id: str, data: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO profiles (id, name, dob, emergency_contact, allergies, medications,
                                   chronic_conditions, insurance, member_id, group_number)
            VALUES (:id, :name, :dob, :emergency_contact, :allergies, :medications,
                    :chronic_conditions, :insurance, :member_id, :group_number)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, dob=excluded.dob, emergency_contact=excluded.emergency_contact,
                allergies=excluded.allergies, medications=excluded.medications,
                chronic_conditions=excluded.chronic_conditions, insurance=excluded.insurance,
                member_id=excluded.member_id, group_number=excluded.group_number
        """, {
            "id": profile_id,
            "name": data.get("name", ""),
            "dob": data.get("dob", ""),
            "emergency_contact": data.get("emergency_contact", ""),
            "allergies": data.get("allergies", ""),
            "medications": data.get("medications", ""),
            "chronic_conditions": json.dumps(data.get("chronic_conditions", [])),
            "insurance": data.get("insurance", ""),
            "member_id": data.get("member_id", ""),
            "group_number": data.get("group_number", ""),
        })


def delete_profile(profile_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))


def _profile_row_to_dict(row) -> dict:
    d = dict(row)
    d["chronic_conditions"] = json.loads(d.get("chronic_conditions") or "[]")
    return d


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

def get_queue(hospital: str = None) -> list:
    with get_conn() as conn:
        if hospital:
            rows = conn.execute("SELECT * FROM queue WHERE hospital = ?", (hospital,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM queue").fetchall()
    return [_queue_row_to_dict(row) for row in rows]


def add_to_queue(entry: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO queue (id, profile_id, name, dob, allergies, medications, chronic_conditions,
                                insurance, member_id, group_number, emergency_contact, symptoms, pain,
                                note, priority, hospital, eta_minutes, photo_path, created_at)
            VALUES (:id, :profile_id, :name, :dob, :allergies, :medications, :chronic_conditions,
                    :insurance, :member_id, :group_number, :emergency_contact, :symptoms, :pain,
                    :note, :priority, :hospital, :eta_minutes, :photo_path, :created_at)
            ON CONFLICT(id) DO UPDATE SET
                profile_id=excluded.profile_id, name=excluded.name, dob=excluded.dob,
                allergies=excluded.allergies, medications=excluded.medications,
                chronic_conditions=excluded.chronic_conditions, insurance=excluded.insurance,
                member_id=excluded.member_id, group_number=excluded.group_number,
                emergency_contact=excluded.emergency_contact, symptoms=excluded.symptoms,
                pain=excluded.pain, note=excluded.note, priority=excluded.priority,
                hospital=excluded.hospital, eta_minutes=excluded.eta_minutes,
                photo_path=excluded.photo_path, created_at=excluded.created_at
        """, {
            **entry,
            "chronic_conditions": json.dumps(entry.get("chronic_conditions", [])),
            "symptoms": json.dumps(entry.get("symptoms", [])),
        })


def clear_queue():
    with get_conn() as conn:
        conn.execute("DELETE FROM queue")


def _queue_row_to_dict(row) -> dict:
    d = dict(row)
    d["chronic_conditions"] = json.loads(d.get("chronic_conditions") or "[]")
    d["symptoms"] = json.loads(d.get("symptoms") or "[]")
    return d
