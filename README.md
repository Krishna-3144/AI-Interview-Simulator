# 🤖 AI Interview Simulator

An advanced multi-agent AI interview system with adaptive follow-ups, voice analysis, and deep performance analytics.

---

## 🚀 Setup (3 steps)

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Configure environment
```bash
cp .env.example .env
```
Open `.env` and add your **Groq API key**:
```
GROQ_API_KEY=your_groq_api_key_here
```
Get a free key at: https://console.groq.com

### Step 3 — Run
```bash
python run.py
```
Open your browser at: **http://localhost:8000**

---

## 📁 Project Structure

```
interview_simulator/
├── run.py                        # Entry point
├── requirements.txt
├── .env.example                  # Copy to .env and add your API key
│
└── backend/
    ├── api/
    │   └── main.py               # FastAPI routes + WebSocket
    │
    ├── agents/                   # 6 LangGraph agents
    │   ├── resume_analysis.py    # Agent 1: parse PDF → candidate profile
    │   ├── interview_planning.py # Agent 2: topic queue + difficulty
    │   ├── question_generation.py# Agent 3: adaptive question generation
    │   ├── answer_evaluation.py  # Agent 4: 5-dimension scoring
    │   ├── followup_decision.py  # Agent 5: adaptive routing brain
    │   └── report_generation.py  # Agent 6: final analytics
    │
    ├── core/
    │   ├── state.py              # Shared InterviewState TypedDict
    │   ├── graph.py              # LangGraph state machine
    │   ├── llm.py                # Groq LLM client (swap model here)
    │   └── config.py             # Settings from .env
    │
    ├── services/
    │   ├── audio_service.py      # Whisper + librosa pipeline
    │   ├── memory_service.py     # ChromaDB semantic memory
    │   └── session_service.py    # Session CRUD + state persistence
    │
    ├── db/
    │   └── models.py             # SQLAlchemy models + SQLite
    │
    └── static/                   # Frontend (served by FastAPI)
        ├── index.html            # Resume upload page
        ├── interview.html        # Live interview page
        ├── report.html           # Final analytics dashboard
        ├── css/style.css
        └── js/
            ├── interview.js
            └── report.js
```

---

## 🧠 Agent Architecture

```
User uploads resume
        ↓
[Agent 1] Resume Analysis      → extracts structured candidate profile
        ↓
[Agent 2] Interview Planning   → builds topic queue, sets difficulty
        ↓
[Agent 3] Question Generation  → generates personalized question
        ↓
     [USER ANSWERS]
        ↓
[Agent 4] Answer Evaluation    → scores 5 dimensions + stores in memory
        ↓
[Agent 5] Follow-Up Decision   → decides: probe deeper / advance / wrap up
        ↓
    ┌───────────────────────────────────────┐
    │  next_action routing                  │
    │  "ask_follow_up"  → Agent 3 (probe)   │
    │  "advance_topic"  → Agent 2 → Agent 3 │
    │  "deepen"         → Agent 3 (harder)  │
    │  "project_deep"   → Agent 3 (project) │
    │  "generate_report"→ Agent 6           │
    └───────────────────────────────────────┘
        ↓
[Agent 6] Report Generation    → final analytics + hiring recommendation
```

---

## 🎙️ Voice Mode

The system uses **Whisper** for transcription and **librosa** for audio analysis.

Whisper model options (set in `.env`):
- `base` — fast, good enough (default)
- `small` — more accurate, slightly slower
- `medium` — best accuracy, requires more RAM

Audio features extracted:
- Speech rate (words per second)
- Long pause detection (pauses > 1 second)
- Filler word count (umm, uh, like, you know...)
- Pitch variance (nervousness signal)
- Hesitation score (0-1)
- Confidence score (0-1)

---

## 🔄 Switching LLM

To switch from Groq to another provider, edit `backend/core/llm.py`:

```python
# Current: Groq
from langchain_groq import ChatGroq

# Switch to OpenAI:
from langchain_openai import ChatOpenAI
def get_main_llm(): return ChatOpenAI(model="gpt-4o", ...)

# Switch to Ollama (local):
from langchain_ollama import ChatOllama
def get_main_llm(): return ChatOllama(model="llama3.1:70b", ...)
```

---

## 📊 Satisfaction Scoring

Each answer is scored across 5 dimensions:

| Dimension | Weight | What it measures |
|---|---|---|
| Technical Accuracy | 35% | Correctness, concept understanding |
| Depth | 25% | Examples, edge cases, tradeoffs |
| Communication | 20% | Clarity, structure, coherence |
| Confidence | 10% | Audio analysis + text inference |
| Consistency | 10% | No contradictions with prior answers |

If overall score < 0.65 (configurable) → follow-up question is generated.
If overall score > 0.85 → difficulty increases.

---

## ⚙️ Configuration

All behaviour is configurable in `.env`:

```
SATISFACTION_THRESHOLD=0.65      # below this → follow-up
MAX_FOLLOW_UPS_PER_QUESTION=3    # max probes per question
MIN_QUESTIONS_PER_TOPIC=2        # min before advancing topic
MAX_QUESTIONS_PER_TOPIC=5        # max before forcing advance
WHISPER_MODEL=base               # whisper model size
```
