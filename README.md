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
- **Multilingual voice input** — record a voice note in any of 10
  supported languages (the patient speaks whatever they're most
  comfortable with, especially useful under stress or if typing is hard
  due to an injury). The app transcribes it, then machine-translates it
  to English for the ER — the intake summary shows both the original
  and the English version, so nothing is lost in translation and the
  patient can verify accuracy. Requires an internet connection; typing
  in English always works as a fallback.
- **Photo attachment** — attach a photo of a visible injury to the
  intake summary.
- **Real location + ETA** — with permission, the app uses your browser's
  location to calculate actual distance and estimated arrival time to
  each hospital, sorted nearest first. Falls back to default distances
  if location isn't shared.
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

### Voice input & translation

Uses the free Google Web Speech API through the `SpeechRecognition`
library for transcription. For translation to English, it tries
`deep-translator`'s Google backend first, and falls back automatically
to MyMemory (a different free translation API) if that fails — Google's
free backend works by scraping its web page rather than a real API, so
it breaks intermittently (e.g. "No translation was found..." errors),
and having a second backend makes the feature meaningfully more
reliable. Both need an internet connection at runtime. If transcription
fails, the app shows a warning and the patient can type instead. If
transcription succeeds but both translators fail, the app keeps the
original-language transcript and shows the underlying error message
(for debugging) rather than silently losing the note.

**Important:** this is machine translation, not verified for medical
accuracy. It's meant to get the gist of what's wrong to the ER faster
than no information at all — not to replace a professional interpreter
for anything nuanced. The original-language text is always kept and
shown alongside the English translation so nothing is silently lost or
misrepresented.

### Location + ETA

Uses the `streamlit-geolocation` component, which asks the browser for
permission the first time. Distance to each hospital is calculated with
the haversine formula (straight-line distance) and adjusted by a fixed
factor to approximate real driving distance, since this doesn't use a
paid maps/directions API. If location access is denied or unavailable,
the hospital list falls back to fixed default distances.

**If distances look wrong on a laptop/desktop:** this is almost always
the browser's location accuracy, not the app's math. Desktops/laptops
usually lack a GPS chip, so the browser estimates location from nearby
WiFi networks and IP address — which can be off by several miles. Phones
use real GPS and are much more accurate. The app shows the detected
coordinates under "Using your location" so you can check them against
a map (e.g. Google Maps) to confirm whether the location itself is off.

## Notes on scope

- The priority label on the ER dashboard is a simple, transparent
  symptom+pain heuristic for demo purposes — not a clinical triage tool.
  A real deployment would never auto-triage; a nurse always makes that
  call. This only pre-fills what the nurse sees.
- Voice transcription is a best-effort read, never a source of truth —
  the patient always reviews it before anything is saved or sent.
- Hospital coordinates and driving-distance approximation are for demo
  purposes. The list currently covers 6 real Sacramento/Folsom/Roseville
  hospitals — enough to be sensible for that region, but still a fixed
  list, not a live search. A real version would use a maps/places API to
  find whatever hospitals are actually nearest to the patient, anywhere.
- There's no access control on wallet data in this prototype — anyone
  using the app on a given device/deployment can view or edit any
  profile. A real deployment would need proper authentication; this was
  deliberately left out of the prototype so nothing could block the
  core emergency flow (see the "Heading to ER" tab) for someone who
  isn't the patient themselves.
- Wallet and queue data are stored in a local SQLite file for this
  prototype. A real version would need encryption at rest and, for
  anything sent off-device, HIPAA-compliant infrastructure.
