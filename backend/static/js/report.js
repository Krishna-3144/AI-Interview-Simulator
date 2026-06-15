// backend/static/js/report.js

const params    = new URLSearchParams(window.location.search);
const sessionId = params.get('session') || sessionStorage.getItem('session_id');

if (!sessionId) window.location.href = '/';

async function loadReport() {
  try {
    const res    = await fetch(`/api/sessions/${sessionId}/report`);
    if (!res.ok) throw new Error('Report not ready');
    const report = await res.json();
    renderReport(report);
  } catch (err) {
    document.querySelector('.report-layout').innerHTML =
      `<div class="report-card"><h2>⏳ Loading...</h2>
       <p>Report is being generated. <a href="#" onclick="location.reload()">Refresh</a></p></div>`;
  }
}

function renderReport(r) {
  // Hero
  document.getElementById('candidateName').textContent = r.candidate_name || 'Candidate';
  document.getElementById('targetRole').textContent    = r.target_role ? `Target Role: ${r.target_role}` : '';
  document.getElementById('totalQuestions').textContent = `${r.total_questions} questions answered`;

  const score = Math.round((r.overall_score || 0) * 100);
  document.getElementById('overallScore').textContent = `${score}%`;

  // Recommendation badge
  const recBadge = document.getElementById('recBadge');
  const rec = r.hiring_recommendation || 'Borderline';
  recBadge.textContent = rec;
  const recClass = {
    'Strong Hire': 'rec-strong-hire',
    'Hire':        'rec-hire',
    'Borderline':  'rec-borderline',
    'Reject':      'rec-reject',
  }[rec] || 'rec-borderline';
  recBadge.classList.add(recClass);

  // Text fields
  setText('summary',               r.summary);
  setText('communicationAssessment', r.communication_assessment);
  setText('confidenceAssessment',  r.confidence_assessment);
  setText('behavioralInsights',    r.behavioral_insights);
  setText('recReasoning',          r.recommendation_reasoning);

  // Lists
  setList('strengths',  r.technical_strengths || []);
  setList('weaknesses', r.technical_weaknesses || []);
  setList('suggestions', r.improvement_suggestions || []);

  // Confidence grid
  const cs = r.confidence_summary || {};
  document.getElementById('confidenceGrid').innerHTML = `
    <div class="conf-stat">
      <div class="conf-stat-value">${Math.round((cs.confidence_score||0)*100)}%</div>
      <div class="conf-stat-label">Avg Confidence</div>
    </div>
    <div class="conf-stat">
      <div class="conf-stat-value">${(cs.words_per_second||0).toFixed(1)}</div>
      <div class="conf-stat-label">Words/sec</div>
    </div>
    <div class="conf-stat">
      <div class="conf-stat-value">${Math.round(cs.filler_word_count||0)}</div>
      <div class="conf-stat-label">Avg Fillers</div>
    </div>
    <div class="conf-stat">
      <div class="conf-stat-value">${Math.round(cs.long_pause_count||0)}</div>
      <div class="conf-stat-label">Avg Pauses</div>
    </div>
    <div class="conf-stat">
      <div class="conf-stat-value">${Math.round((cs.hesitation_score||0)*100)}%</div>
      <div class="conf-stat-label">Hesitation</div>
    </div>
    <div class="conf-stat">
      <div class="conf-stat-value">${Math.round((cs.silence_ratio||0)*100)}%</div>
      <div class="conf-stat-label">Silence Ratio</div>
    </div>
  `;

  // Contradictions
  if (r.contradictions && r.contradictions.length > 0) {
    document.getElementById('contradictionsCard').style.display = 'block';
    document.getElementById('contradictionsList').innerHTML =
      r.contradictions.map(c => `
        <div class="contradiction-item">
          <strong>Earlier:</strong> "${c.earlier_statement || ''}"<br>
          <strong>Later:</strong> "${c.current_statement || ''}"<br>
          <em>${c.explanation || ''}</em>
        </div>
      `).join('');
  }

  // ── Charts ────────────────────────────────────────────────────────────────
  renderTopicChart(r.score_by_topic || {});
  renderRadarChart(r);
  renderConfidenceChart(r.confidence_timeline || [], r.answer_scores || []);
}

function renderTopicChart(topicScores) {
  const labels = Object.keys(topicScores);
  const data   = Object.values(topicScores).map(v => Math.round(v * 100));

  new Chart(document.getElementById('topicChart'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Score %',
        data,
        backgroundColor: data.map(v =>
          v >= 75 ? 'rgba(76,175,130,0.7)' :
          v >= 50 ? 'rgba(108,99,255,0.7)' :
                   'rgba(224,92,92,0.7)'
        ),
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, ticks: { color: '#8b90b0' }, grid: { color: '#2e3150' } },
        x: { ticks: { color: '#8b90b0' }, grid: { display: false } },
      },
    },
  });
}

function renderRadarChart(r) {
  // Average per dimension across all answers
  const records = r.answer_scores || [];
  const avg = key => records.length
    ? records.reduce((s, a) => s + (a[key] || 0), 0) / records.length * 100
    : 0;

  new Chart(document.getElementById('radarChart'), {
    type: 'radar',
    data: {
      labels: ['Technical', 'Depth', 'Communication', 'Confidence', 'Consistency'],
      datasets: [{
        label: 'Performance',
        data: [
          avg('technical_accuracy'),
          avg('depth'),
          avg('communication'),
          r.confidence_summary?.confidence_score * 100 || 0,
          80, // consistency — placeholder
        ],
        backgroundColor: 'rgba(108,99,255,0.2)',
        borderColor:     'rgba(108,99,255,0.8)',
        pointBackgroundColor: '#6c63ff',
      }],
    },
    options: {
      responsive: true,
      scales: {
        r: {
          min: 0, max: 100,
          ticks: { display: false },
          grid:  { color: '#2e3150' },
          pointLabels: { color: '#8b90b0', font: { size: 11 } },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function renderConfidenceChart(timeline, answerScores) {
  if (!answerScores || answerScores.length === 0) return;

  const labels = answerScores.map((_, i) => `Q${i + 1}`);
  const accuracy = answerScores.map(a => Math.round((a.overall || 0) * 100));
  const conf = answerScores.map((a, i) => {
    if (timeline && timeline[i]) {
      return Math.round((timeline[i].confidence_score || 0) * 100);
    }
    return Math.round((a.overall || 0.7) * 100);
  });

  new Chart(document.getElementById('confidenceChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Accuracy (Score)',
          data: accuracy,
          borderColor: '#6c63ff',
          backgroundColor: 'rgba(108,99,255,0.1)',
          tension: 0.4,
          fill: true,
        },
        {
          label: 'Confidence',
          data: conf,
          borderColor: '#4ecdc4',
          backgroundColor: 'rgba(78,205,196,0.1)',
          tension: 0.4,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: { min: 0, max: 100, ticks: { color: '#8b90b0' }, grid: { color: '#2e3150' } },
        x: { ticks: { color: '#8b90b0' }, grid: { display: false } },
      },
      plugins: { legend: { labels: { color: '#8b90b0' } } },
    },
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text || '';
}

function setList(id, items) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = items.map(i => `<li>${i}</li>`).join('');
}

// Load on page ready
loadReport();
