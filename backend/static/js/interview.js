// backend/static/js/interview.js

const sessionId   = sessionStorage.getItem('session_id');
const candidate   = JSON.parse(sessionStorage.getItem('candidate') || '{}');

if (!sessionId) window.location.href = '/';

// ── State ──────────────────────────────────────────────────────────────────
let currentMode    = 'text';
let mediaRecorder  = null;
let audioChunks    = [];
let recordedBlob   = null;
let isRecording    = false;

// ── Init ───────────────────────────────────────────────────────────────────
document.getElementById('candidateName').textContent = candidate.name || '';

const firstQuestion    = sessionStorage.getItem('first_question');
const firstTopic       = sessionStorage.getItem('first_topic');
const firstDifficulty  = parseInt(sessionStorage.getItem('first_difficulty') || '2');
const firstExplanation = sessionStorage.getItem('first_explanation');

if (firstQuestion) {
  displayQuestion(firstQuestion, firstTopic, firstDifficulty, firstExplanation, false);
  addToHistory('interviewer', firstQuestion);
}

// ── Mode toggle ────────────────────────────────────────────────────────────
function setMode(mode) {
  currentMode = mode;
  document.getElementById('textMode').style.display  = mode === 'text'  ? 'block' : 'none';
  document.getElementById('audioMode').style.display = mode === 'audio' ? 'block' : 'none';
  document.getElementById('textTab').classList.toggle('active',  mode === 'text');
  document.getElementById('audioTab').classList.toggle('active', mode === 'audio');
}

// ── Display question ───────────────────────────────────────────────────────
function displayQuestion(question, topic, difficulty, explanation, isFollowUp) {
  document.getElementById('questionText').textContent = question;
  document.getElementById('topicBadge').textContent   = topic || 'General';

  const dots = '●'.repeat(difficulty) + '○'.repeat(5 - difficulty);
  document.getElementById('diffBadge').textContent = dots;

  const fuBadge = document.getElementById('followUpBadge');
  fuBadge.classList.toggle('hidden', !isFollowUp);

  const explBox  = document.getElementById('explanationBox');
  const explText = document.getElementById('explanationText');
  if (explanation) {
    explText.textContent = explanation;
    explBox.style.display = 'block';
  } else {
    explBox.style.display = 'none';
  }

  // Reset answer area
  document.getElementById('answerText').value = '';
  recordedBlob = null;
  document.getElementById('transcriptPreview').classList.add('hidden');
  document.getElementById('submitAudioBtn').classList.add('hidden');
}

// ── Text submission ────────────────────────────────────────────────────────
async function submitText() {
  const answer = document.getElementById('answerText').value.trim();
  if (!answer) return;

  addToHistory('candidate', answer);
  showThinking(true);
  lockInput(true);

  const fd = new FormData();
  fd.append('answer', answer);

  try {
    const res  = await fetch(`/api/sessions/${sessionId}/answer`, { method: 'POST', body: fd });
    const data = await res.json();
    handleResponse(data);
  } catch (err) {
    showError('Network error. Please try again.');
  } finally {
    showThinking(false);
    lockInput(false);
  }
}

// ── Audio recording ────────────────────────────────────────────────────────
async function toggleRecord() {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks  = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(audioChunks, { type: 'audio/wav' });
      document.getElementById('submitAudioBtn').classList.remove('hidden');
      document.getElementById('transcriptPreview').classList.remove('hidden');
      document.getElementById('transcriptText').textContent = 'Processing transcript...';
    };

    mediaRecorder.start();
    isRecording = true;

    const btn = document.getElementById('recordBtn');
    btn.textContent = '⏹️ Stop Recording';
    btn.classList.add('recording');
    document.getElementById('recordingIndicator').classList.remove('hidden');
  } catch (err) {
    showError('Microphone access denied. Please allow microphone and try again.');
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    isRecording = false;

    const btn = document.getElementById('recordBtn');
    btn.textContent = '🎙️ Start Recording';
    btn.classList.remove('recording');
    document.getElementById('recordingIndicator').classList.add('hidden');
  }
}

async function submitAudio() {
  if (!recordedBlob) return;

  showThinking(true);
  lockInput(true);

  const fd = new FormData();
  fd.append('audio', recordedBlob, 'answer.wav');

  try {
    const res  = await fetch(`/api/sessions/${sessionId}/audio`, { method: 'POST', body: fd });
    const data = await res.json();

    if (data.transcript) {
      document.getElementById('transcriptText').textContent = data.transcript;
      addToHistory('candidate', data.transcript);
    }
    if (data.confidence) displayConfidence(data.confidence);
    handleResponse(data);
  } catch (err) {
    showError('Error processing audio. Try text mode.');
  } finally {
    showThinking(false);
    lockInput(false);
  }
}

// ── Handle API response ────────────────────────────────────────────────────
function handleResponse(data) {
  if (data.done) {
    // Interview complete — go to report
    window.location.href = `/report?session=${sessionId}`;
    return;
  }

  // Show scores
  if (data.latest_scores) displayScores(data.latest_scores);

  // Contradiction alert
  const contAlert = document.getElementById('contradictionAlert');
  if (data.contradictions && data.contradictions.length > 0) {
    contAlert.classList.remove('hidden');
    setTimeout(() => contAlert.classList.add('hidden'), 8000);
  }

  // Display next question
  const isFollowUp = data.next_action === 'ask_follow_up' || data.follow_up_depth > 0;
  displayQuestion(
    data.question,
    data.topic,
    data.difficulty,
    data.explanation,
    isFollowUp
  );
  addToHistory('interviewer', data.question);
}

// ── Display scores ─────────────────────────────────────────────────────────
function displayScores(scores) {
  const dims = [
    { key: 'technical_accuracy', label: 'Technical Accuracy' },
    { key: 'depth',              label: 'Depth' },
    { key: 'communication',      label: 'Communication' },
    { key: 'confidence',         label: 'Confidence' },
    { key: 'consistency',        label: 'Consistency' },
  ];

  let html = '';
  dims.forEach(d => {
    const val  = scores[d.key] || 0;
    const pct  = Math.round(val * 100);
    const cls  = val >= 0.7 ? 'high' : val >= 0.45 ? 'medium' : 'low';
    html += `
      <div class="score-row">
        <div class="score-row-header">
          <span>${d.label}</span>
          <span>${pct}%</span>
        </div>
        <div class="score-bar-bg">
          <div class="score-bar-fill ${cls}" style="width:${pct}%"></div>
        </div>
      </div>`;
  });

  if (scores.reasoning) {
    html += `<div class="score-reasoning">💬 ${scores.reasoning}</div>`;
  }

  document.getElementById('scoresDisplay').innerHTML = html;
}

// ── Display confidence ─────────────────────────────────────────────────────
function displayConfidence(c) {
  const confDiv = document.getElementById('confidenceDisplay');
  confDiv.classList.remove('hidden');
  document.getElementById('confidenceMetrics').innerHTML = `
    <div class="conf-metric"><span>Confidence</span><span class="conf-value">${Math.round(c.confidence_score*100)}%</span></div>
    <div class="conf-metric"><span>Speech rate</span><span class="conf-value">${c.words_per_second} wps</span></div>
    <div class="conf-metric"><span>Long pauses</span><span class="conf-value">${c.long_pause_count}</span></div>
    <div class="conf-metric"><span>Filler words</span><span class="conf-value">${c.filler_word_count}</span></div>
    <div class="conf-metric"><span>Pace</span><span class="conf-value">${c.speech_rate_category}</span></div>
  `;
}

// ── History ────────────────────────────────────────────────────────────────
function addToHistory(role, content) {
  const list = document.getElementById('history');
  const item = document.createElement('div');
  item.className = `history-item ${role}`;
  item.innerHTML = `
    <div class="history-role">${role === 'interviewer' ? '🤖 Interviewer' : '👤 You'}</div>
    <div>${content.substring(0, 120)}${content.length > 120 ? '...' : ''}</div>
  `;
  list.appendChild(item);
  list.scrollTop = list.scrollHeight;
}

// ── UI helpers ─────────────────────────────────────────────────────────────
function showThinking(show) {
  document.getElementById('thinking').classList.toggle('hidden', !show);
}

function lockInput(locked) {
  document.getElementById('submitTextBtn').disabled = locked;
  document.getElementById('submitAudioBtn').disabled = locked;
  document.getElementById('recordBtn').disabled = locked;
  document.getElementById('answerText').disabled = locked;
}

function showError(msg) {
  // Simple alert for now
  alert(msg);
}

// Enter key to submit text
document.getElementById('answerText').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) submitText();
});

// ── Control and Skip Actions ────────────────────────────────────────────────
async function skipFollowup() {
  if (!confirm("Are you sure you want to skip follow-ups and move to the next question?")) return;
  showThinking(true);
  lockInput(true);
  try {
    const res = await fetch(`/api/sessions/${sessionId}/skip_followup`, { method: 'POST' });
    const data = await res.json();
    handleResponse(data);
  } catch (err) {
    showError('Error skipping follow-up.');
  } finally {
    showThinking(false);
    lockInput(false);
  }
}

async function skipTopic() {
  if (!confirm("Are you sure you want to skip the current topic and advance to the next topic?")) return;
  showThinking(true);
  lockInput(true);
  try {
    const res = await fetch(`/api/sessions/${sessionId}/skip_topic`, { method: 'POST' });
    const data = await res.json();
    handleResponse(data);
  } catch (err) {
    showError('Error skipping topic.');
  } finally {
    showThinking(false);
    lockInput(false);
  }
}

async function endInterview() {
  if (!confirm("Are you sure you want to end the interview now and see your performance?")) return;
  showThinking(true);
  lockInput(true);
  try {
    const res = await fetch(`/api/sessions/${sessionId}/end_interview`, { method: 'POST' });
    const data = await res.json();
    handleResponse(data);
  } catch (err) {
    showError('Error ending interview.');
  } finally {
    showThinking(false);
    lockInput(false);
  }
}

// ── Detailed Analysis Modal ─────────────────────────────────────────────────
const FILLER_WORDS = [
  "umm", "um", "uh", "uhh", "hmm", "like", "you know",
  "basically", "actually", "literally", "i mean", "sort of",
  "kind of", "right", "okay so", "so yeah", "aaa", "err"
];

function escapeHTML(str) {
  if (!str) return "";
  return str.replace(/[&<>'"]/g, 
    tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag)
  );
}

function highlightFillerWords(text) {
  if (!text) return "";
  let escapedText = escapeHTML(text);
  
  const sortedFillers = [...FILLER_WORDS].sort((a, b) => b.length - a.length);
  
  sortedFillers.forEach(filler => {
    const escapedFiller = filler.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
    const regex = new RegExp(`\\b(${escapedFiller})\\b`, 'gi');
    escapedText = escapedText.replace(regex, '<span class="filler-word" title="Filler word detected">$1</span>');
  });
  return escapedText;
}

async function openAnalysisModal() {
  const modal = document.getElementById('analysisModal');
  const detailsDiv = document.getElementById('analysisDetails');
  detailsDiv.innerHTML = '<p class="loading-msg">Fetching turn-by-turn analysis...</p>';
  modal.classList.remove('hidden');

  try {
    const res = await fetch(`/api/sessions/${sessionId}/analysis`);
    if (!res.ok) throw new Error('Failed to load analysis');
    const data = await res.json();
    renderDetailedAnalysis(data);
  } catch (err) {
    detailsDiv.innerHTML = `<p class="error-msg">Error: ${err.message}</p>`;
  }
}

function closeAnalysisModal() {
  document.getElementById('analysisModal').classList.add('hidden');
}

function renderDetailedAnalysis(data) {
  const detailsDiv = document.getElementById('analysisDetails');
  const records = data.answer_records || [];

  if (records.length === 0) {
    detailsDiv.innerHTML = '<p class="empty-msg">No answers evaluated yet. Try answering a question first.</p>';
    return;
  }

  let html = '';
  records.forEach((r, idx) => {
    const sat = r.satisfaction || {};
    const metrics = r.confidence_metrics || {};
    
    const highlightedAnswer = highlightFillerWords(r.answer_text);
    
    let pausesHtml = '';
    if (metrics.long_pause_timestamps && metrics.long_pause_timestamps.length > 0) {
      pausesHtml = `
        <div style="margin-top: 8px; font-size: 13px;">
          <strong>Awkward Pauses Timeline:</strong>
          ${metrics.long_pause_timestamps.map(p => `<span class="pause-tag" title="Silence duration: ${p[2]}s">⏱️ ${p[2]}s pause at ${Math.round(p[0])}s</span>`).join('')}
        </div>
      `;
    }

    let gapsHtml = '';
    const gaps = sat.technical_gaps || [];
    if (gaps.length > 0) {
      gapsHtml = `
        <div class="analysis-gaps-title">⚠️ Technical Gaps:</div>
        <ul class="analysis-gaps-list">
          ${gaps.map(g => `<li>${escapeHTML(g)}</li>`).join('')}
        </ul>`;
    } else {
      gapsHtml = `<div class="analysis-gaps-title" style="color: var(--success);">✅ No Technical Gaps Identified</div>`;
    }

    html += `
      <div class="analysis-turn">
        <div class="analysis-q">Q${idx + 1} (${r.topic}): ${escapeHTML(r.question_text)}</div>
        <div class="analysis-a">${highlightedAnswer}</div>
        
        <div class="analysis-metrics-row">
          <div class="analysis-metric-badge">🎯 Accuracy: <strong>${Math.round(sat.technical_accuracy * 100)}%</strong></div>
          <div class="analysis-metric-badge">📚 Depth: <strong>${Math.round(sat.depth * 100)}%</strong></div>
          <div class="analysis-metric-badge">🗣️ Comm: <strong>${Math.round(sat.communication * 100)}%</strong></div>
          <div class="analysis-metric-badge">🎙️ Confidence: <strong>${Math.round(sat.confidence * 100)}%</strong></div>
        </div>

        ${pausesHtml}
        ${gapsHtml}
      </div>
    `;
  });

  detailsDiv.innerHTML = html;
}
