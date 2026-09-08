"""
ER Ready — a health wallet app for self-transport ER patients.

Run with:  streamlit run app.py
"""

import io
import uuid
from datetime import datetime
from pathlib import Path

import json
import qrcode
import streamlit as st
from PIL import Image

import db

try:
    import speech_recognition as sr
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Storage: SQLite (see db.py). Photos still live on local disk, referenced
# by path — fine for a single-instance demo deployment.
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
PHOTO_DIR = DATA_DIR / "photos"
DATA_DIR.mkdir(exist_ok=True)
PHOTO_DIR.mkdir(exist_ok=True)

db.init_db()

SYMPTOMS = [
    "Chest pain",
    "Breathing difficulty",
    "Injury / fracture",
    "Bleeding",
    "Allergic reaction",
    "Severe headache",
    "Fever",
    "Abdominal pain",
    "Dizziness / fainting",
    "Other",
]

CHRONIC_CONDITIONS = [
    "Diabetes",
    "High blood pressure",
    "Heart disease",
    "Asthma / COPD",
    "Kidney disease",
    "Seizure disorder",
    "Prior stroke",
    "Immunocompromised",
]

# Mocked hospital options — a real version would pull nearby ERs from a
# maps/directions API based on live device location.
HOSPITALS = [
    {"name": "Mercy General ER", "distance_miles": 4.2, "avg_speed_mph": 28},
    {"name": "Sutter Medical Center ER", "distance_miles": 6.8, "avg_speed_mph": 30},
    {"name": "UC Davis Medical Center ER", "distance_miles": 9.1, "avg_speed_mph": 32},
]

HIGH_RISK_SYMPTOMS = {"Chest pain", "Breathing difficulty", "Bleeding", "Allergic reaction", "Dizziness / fainting"}
PRIORITY_ORDER = {"Priority": 0, "Standard": 1, "Low": 2}


def estimate_eta_minutes(distance_miles: float, avg_speed_mph: float) -> int:
    hours = distance_miles / avg_speed_mph
    return max(1, round(hours * 60))


def priority_from_symptoms_and_pain(symptoms: list, pain: int) -> str:
    """Simple, transparent priority heuristic for the demo dashboard —
    NOT a clinical triage tool. A real deployment would never auto-triage;
    a nurse always makes that call. This only pre-fills what the nurse sees.
    """
    has_high_risk = any(s in HIGH_RISK_SYMPTOMS for s in symptoms)
    if has_high_risk and pain >= 6:
        return "Priority"
    if pain >= 6 or has_high_risk:
        return "Standard"
    return "Low"


def transcribe_audio(audio_bytes: bytes) -> str:
    """Best-effort speech-to-text. Requires an internet connection at
    runtime (uses a free online recognition service). Always falls back
    gracefully — the patient can type instead if this doesn't work."""
    if not VOICE_AVAILABLE:
        return ""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio)
    except Exception:
        return ""


def make_qr_image(payload: dict):
    # Keep the QR payload light — photos are referenced by id, not embedded.
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def new_profile_id() -> str:
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

st.set_page_config(page_title="ER Ready", page_icon="🩺", layout="centered")

profiles = db.get_all_profiles()
queue = db.get_queue()

view = st.sidebar.radio(
    "View",
    ["Patient app", "ER dashboard (hospital side)"],
    help="Patient app is what the user carries. ER dashboard simulates what hospital staff would see.",
)

# ---------------------------------------------------------------------------
# PATIENT APP
# ---------------------------------------------------------------------------
if view == "Patient app":
    st.title("ER Ready")
    st.caption("A health wallet for the ER — because when you drive yourself in, the hospital doesn't know you're coming.")

    # --- Profile selector (multi-profile support) ---------------------------
    st.sidebar.divider()
    st.sidebar.subheader("Profile")
    profile_names = {pid: p["name"] for pid, p in profiles.items() if p.get("name")}

    if "active_profile" not in st.session_state or st.session_state["active_profile"] not in profiles:
        st.session_state["active_profile"] = next(iter(profile_names), None)

    options = list(profile_names.keys()) + ["__new__"]
    labels = {**profile_names, "__new__": "+ Add new profile"}

    default_index = options.index(st.session_state["active_profile"]) if st.session_state["active_profile"] in options else len(options) - 1
    selected = st.sidebar.selectbox(
        "Managing wallet for",
        options,
        format_func=lambda pid: labels.get(pid, pid),
        index=default_index,
    )

    if selected == "__new__":
        new_name = st.sidebar.text_input("New profile name", key="new_profile_name")
        if st.sidebar.button("Create profile") and new_name.strip():
            pid = new_profile_id()
            db.save_profile(pid, {"name": new_name.strip()})
            st.session_state["active_profile"] = pid
            st.rerun()
        st.info("Add a name and click 'Create profile' to get started.")
        st.stop()
    else:
        st.session_state["active_profile"] = selected

    active_id = st.session_state["active_profile"]
    wallet = profiles.get(active_id, {"name": profile_names.get(active_id, "")})

    if st.sidebar.button("🗑️ Clear this profile's data"):
        st.session_state["confirm_clear"] = True

    if st.session_state.get("confirm_clear"):
        st.sidebar.warning(f"Delete all data for **{wallet.get('name', 'this profile')}**? This can't be undone.")
        c1, c2 = st.sidebar.columns(2)
        if c1.button("Yes, delete"):
            db.delete_profile(active_id)
            st.session_state.pop("active_profile", None)
            st.session_state.pop("confirm_clear", None)
            st.rerun()
        if c2.button("Cancel"):
            st.session_state.pop("confirm_clear", None)
            st.rerun()

    tab_wallet, tab_send, tab_summary = st.tabs(["1. Health wallet", "2. Heading to ER", "3. Intake summary"])

    # --- Tab 1: Wallet setup -------------------------------------------------
    with tab_wallet:
        st.subheader(f"Health wallet — {wallet.get('name', '')}")
        st.write("Stored on this device. Filled out once, reused every time.")

        with st.form("wallet_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full name", value=wallet.get("name", ""))
                dob = st.text_input("Date of birth", value=wallet.get("dob", ""), placeholder="MM/DD/YYYY")
                emergency_contact = st.text_input("Emergency contact", value=wallet.get("emergency_contact", ""))
                allergies = st.text_input("Allergies", value=wallet.get("allergies", "None known"))
                medications = st.text_input("Medications", value=wallet.get("medications", "None"))
            with col2:
                st.markdown("**Insurance**")
                insurance = st.text_input("Provider", value=wallet.get("insurance", ""))
                member_id = st.text_input("Member ID", value=wallet.get("member_id", ""))
                group_number = st.text_input("Group number", value=wallet.get("group_number", ""))

            chronic_conditions = st.multiselect(
                "Chronic conditions (if any)",
                CHRONIC_CONDITIONS,
                default=wallet.get("chronic_conditions", []),
            )

            submitted = st.form_submit_button("Save wallet")
            if submitted:
                wallet = {
                    "name": name,
                    "dob": dob,
                    "emergency_contact": emergency_contact,
                    "allergies": allergies,
                    "medications": medications,
                    "chronic_conditions": chronic_conditions,
                    "insurance": insurance,
                    "member_id": member_id,
                    "group_number": group_number,
                }
                db.save_profile(active_id, wallet)
                st.success("Wallet saved.")

        if wallet.get("name"):
            st.info(f"Wallet ready for **{wallet['name']}**. Go to the next tab when you need to head to the ER.")

    # --- Tab 2: Heading to ER ------------------------------------------------
    with tab_send:
        st.subheader("Heading to ER")

        if not wallet.get("allergies") and not wallet.get("insurance"):
            st.warning("Fill out the health wallet first (tab 1).")
        else:
            symptoms = st.multiselect("Symptoms (select all that apply)", SYMPTOMS)
            pain = st.slider("Pain level", min_value=1, max_value=10, value=5)

            hospital_names = [h["name"] for h in HOSPITALS]
            hospital_choice = st.selectbox("Which ER are you headed to?", hospital_names)
            hospital = next(h for h in HOSPITALS if h["name"] == hospital_choice)

            st.markdown("**Describe what's wrong**")
            note = st.text_area("Type a note (optional)", placeholder="Anything else useful for the ER to know", key="typed_note")

            if VOICE_AVAILABLE:
                st.caption("Or record instead of typing — useful if your hands are injured.")
                audio = st.audio_input("Record a voice note", key="voice_note")
                if audio is not None and st.button("Transcribe recording"):
                    with st.spinner("Transcribing..."):
                        text = transcribe_audio(audio.getvalue())
                    if text:
                        st.session_state["voice_transcript"] = text
                        st.success("Transcribed — added below.")
                    else:
                        st.warning("Couldn't transcribe that. Check your connection, or just type the note above instead.")

            transcript = st.session_state.get("voice_transcript", "")
            if transcript:
                st.text_area("Transcribed voice note", value=transcript, key="voice_note_display", disabled=True)

            st.markdown("**Photo of visible injury (optional)**")
            photo_col1, photo_col2 = st.columns(2)
            with photo_col1:
                injury_camera = st.camera_input("Take a photo", key="injury_camera")
            with photo_col2:
                injury_upload = st.file_uploader("...or upload one", type=["png", "jpg", "jpeg"], key="injury_upload")
            injury_photo = injury_camera or injury_upload

            if st.button("Generate intake summary", type="primary"):
                if not symptoms:
                    st.error("Select at least one symptom.")
                else:
                    eta = estimate_eta_minutes(hospital["distance_miles"], hospital["avg_speed_mph"])
                    priority = priority_from_symptoms_and_pain(symptoms, pain)
                    combined_note = "  ".join(filter(None, [note, transcript]))

                    entry_id = str(uuid.uuid4())[:8]
                    photo_path = ""
                    if injury_photo is not None:
                        photo_path = str(PHOTO_DIR / f"{entry_id}.jpg")
                        Image.open(injury_photo).convert("RGB").save(photo_path)

                    entry = {
                        "id": entry_id,
                        "profile_id": active_id,
                        "name": wallet.get("name", ""),
                        "dob": wallet.get("dob", ""),
                        "allergies": wallet.get("allergies", ""),
                        "medications": wallet.get("medications", ""),
                        "chronic_conditions": wallet.get("chronic_conditions", []),
                        "insurance": wallet.get("insurance", ""),
                        "member_id": wallet.get("member_id", ""),
                        "group_number": wallet.get("group_number", ""),
                        "emergency_contact": wallet.get("emergency_contact", ""),
                        "symptoms": symptoms,
                        "pain": pain,
                        "note": combined_note,
                        "priority": priority,
                        "hospital": hospital["name"],
                        "eta_minutes": eta,
                        "photo_path": photo_path,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    st.session_state["last_entry"] = entry
                    st.session_state.pop("voice_transcript", None)
                    st.success("Intake summary generated — see the next tab.")

    # --- Tab 3: Summary + share ----------------------------------------------
    with tab_summary:
        st.subheader("Intake summary")
        entry = st.session_state.get("last_entry")

        if not entry:
            st.info("Generate a summary from the 'Heading to ER' tab first.")
        else:
            st.markdown(f"**{entry['name']}**  ·  DOB {entry['dob'] or '—'}")
            st.markdown(f"**Symptoms:** {', '.join(entry['symptoms'])}  ·  **Pain:** {entry['pain']}/10")
            st.markdown(f"**Allergies:** {entry['allergies']}  ·  **Medications:** {entry['medications']}")
            if entry.get("chronic_conditions"):
                st.markdown(f"**Chronic conditions:** {', '.join(entry['chronic_conditions'])}")

            insurance_line = entry['insurance'] or '—'
            if entry.get('member_id'):
                insurance_line += f"  ·  Member ID: {entry['member_id']}"
            if entry.get('group_number'):
                insurance_line += f"  ·  Group: {entry['group_number']}"
            st.markdown(f"**Insurance:** {insurance_line}")
            st.markdown(f"**Heading to:** {entry['hospital']}  ·  **Estimated arrival:** ~{entry['eta_minutes']} min")
            if entry["note"]:
                st.markdown(f"**Note:** {entry['note']}")
            if entry.get("photo_path") and Path(entry["photo_path"]).exists():
                st.image(entry["photo_path"], caption="Attached photo", width=250)

            qr_payload = {k: v for k, v in entry.items() if k != "photo_path"}
            qr_img = make_qr_image(qr_payload)
            qr_path = DATA_DIR / f"qr_{entry['id']}.png"
            qr_img.save(qr_path)
            st.image(str(qr_path), caption="Scan at ER check-in", width=200)

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Send ahead to ER"):
                    db.add_to_queue(entry)
                    st.success(f"Sent to {entry['hospital']}. Switch to 'ER dashboard' in the sidebar to see it arrive.")
            with col_b:
                share_text = (
                    f"{entry['name']} en route to {entry['hospital']} — "
                    f"{', '.join(entry['symptoms'])}, pain {entry['pain']}/10, ETA ~{entry['eta_minutes']} min. "
                    f"Allergies: {entry['allergies']}."
                )
                st.text_area("Text to a family member", value=share_text, height=80)

# ---------------------------------------------------------------------------
# ER DASHBOARD (hospital side — simulated)
# ---------------------------------------------------------------------------
else:
    st.title("ER dashboard")
    st.caption("Simulates what hospital staff would see — not connected to a real EHR.")

    if st.button("Refresh"):
        st.rerun()

    queue = db.get_queue()
    hospital_filter = st.selectbox("Hospital", ["All"] + [h["name"] for h in HOSPITALS])
    if hospital_filter != "All":
        queue = [q for q in queue if q.get("hospital") == hospital_filter]

    queue_sorted = sorted(queue, key=lambda q: (PRIORITY_ORDER.get(q["priority"], 3), q["eta_minutes"]))

    if not queue_sorted:
        st.info("No patients en route yet. Send a summary from the patient app.")
    else:
        st.write(f"**{len(queue_sorted)} incoming**")
        for q in queue_sorted:
            color = {"Priority": "🔴", "Standard": "🟠", "Low": "⚪"}[q["priority"]]
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"{color} **{q['name']}**, DOB {q['dob'] or '—'} → {q.get('hospital', '—')}")
                    st.caption(f"{', '.join(q.get('symptoms', []))} · pain {q['pain']}/10 · ETA ~{q['eta_minutes']} min")
                    st.caption(f"Allergies: {q['allergies']} · Meds: {q['medications']}")
                    if q.get("chronic_conditions"):
                        st.caption(f"Chronic conditions: {', '.join(q['chronic_conditions'])}")
                    if q.get("note"):
                        st.caption(f"Note: {q['note']}")
                    if q.get("photo_path") and Path(q["photo_path"]).exists():
                        st.image(q["photo_path"], width=150)
                with c2:
                    st.markdown(f"**{q['priority']}**")

        if st.button("Clear queue (demo reset)"):
            db.clear_queue()
            st.rerun()
