# ER Ready

A health wallet app for self-transport ER patients. When someone calls 911,
the hospital gets advance notice from EMS. When someone drives themselves
in, the hospital gets nothing until they walk through the door. ER Ready
closes that gap: patients store their medical info once, generate a
structured intake summary on the way to the ER in seconds, and share it
ahead — by QR code at check-in or by text to a family member.

## Features

- **Multi-profile health wallet** — manage separate profiles (e.g.
  yourself, a child, a parent) from one app, each with their own saved
  medical info, in the sidebar profile selector.
- **Multiple symptoms + chronic conditions** — captures a fuller clinical
  picture than a single symptom field (e.g. diabetes, heart disease,
  asthma), which matters for how ER staff triage.
- **Voice input** — record a short voice note instead of typing, useful
  if your hands are injured (this app was partly inspired by a broken
  elbow). Requires an internet connection to transcribe; typing always
  works as a fallback.
- **Photo attachment** — attach a photo of a visible injury to the
  intake summary.
- **Multi-hospital selection** — choose which ER you're headed to,
  rather than assuming the nearest one.
- **Clear my data** — delete a profile's stored data entirely, from the
  sidebar.
- **ER dashboard** — a simulated hospital-side view showing incoming
  patients sorted by urgency and estimated arrival time, filterable by
  hospital. Not connected to any real hospital system — it's a demo of
  the concept.

Both views (patient app and ER dashboard) read/write a shared SQLite
database (`data/er_ready.db`) so you can demo the full loop: fill out a
wallet, generate a summary, hit "Send ahead," then switch to the ER
dashboard in the sidebar to see the patient appear in the queue. SQLite
handles multiple people using the deployed app at the same time
correctly, unlike the earlier prototype's single shared JSON file.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

### Voice input

Uses the free Google Web Speech API through the `SpeechRecognition`
library, which needs an internet connection at runtime. If transcription
fails (no connection, unclear audio), the app shows a warning and the
patient can just type the note instead — nothing is blocked by it.

## Notes on scope

- The priority label on the ER dashboard is a simple, transparent
  symptom+pain heuristic for demo purposes — not a clinical triage tool.
  A real deployment would never auto-triage; a nurse always makes that
  call. This only pre-fills what the nurse sees.
- Voice transcription is a best-effort read, never a source of truth —
  the patient always reviews it before anything is saved or sent.
- Hospital distances/ETA are mocked. A real version would use device GPS
  plus a maps/directions API.
- Wallet and queue data are stored in a local SQLite file for this
  prototype. A real version would need encryption at rest and, for
  anything sent off-device, HIPAA-compliant infrastructure.
