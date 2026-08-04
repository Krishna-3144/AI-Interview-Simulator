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
  document.getElementById('totalQuestions').textContent = `${r.total_questions || 0} questions answered`;

  // Three Scores
  document.getElementById('techScore').textContent = r.technical_score !== undefined ? r.technical_score.toFixed(1) : '—';
  document.getElementById('commScore').textContent = r.communication_score !== undefined ? r.communication_score.toFixed(1) : '—';
  document.getElementById('gramScore').textContent = r.grammar_score !== undefined ? r.grammar_score.toFixed(1) : '—';

  // Strong Areas (Pills)
  const strongList = document.getElementById('strongAreasList');
  if (r.strong_areas && r.strong_areas.length > 0) {
    strongList.innerHTML = r.strong_areas.map(area => `<span class="pill-strong">${escapeHTML(area)}</span>`).join('');
  } else {
    strongList.innerHTML = `<p style="color: var(--text-dim);">No strong areas recorded.</p>`;
  }

  // Weak Areas (grouped by topic with frequencies)
  const weakContainer = document.getElementById('weakAreasContainer');
  if (r.weak_areas && r.weak_areas.length > 0) {
    let html = '';
    r.weak_areas.forEach(item => {
      const topic = item.topic || 'General';
      const missing = item.missing || {};
      const missingKeys = Object.keys(missing);
      if (missingKeys.length > 0) {
        html += `
          <div class="weak-topic-card">
            <div class="weak-topic-title">📁 ${escapeHTML(topic)}</div>
            <ul class="weak-concept-list">
              ${missingKeys.map(concept => `
                <li class="weak-concept-item">
                  <span>❌ ${escapeHTML(concept)}</span>
                  <span class="freq-badge" title="Times missed during interview">${missing[concept]}</span>
                </li>
              `).join('')}
            </ul>
          </div>
        `;
      }
    });
    weakContainer.innerHTML = html || `<p style="color: var(--text-dim);">No weak areas detected.</p>`;
  } else {
    weakContainer.innerHTML = `<p style="color: var(--text-dim);">No weak areas detected.</p>`;
  }

  // Contradictions
  const contraContainer = document.getElementById('contradictionsContainer');
  if (r.contradictions && r.contradictions.length > 0) {
    contraContainer.innerHTML = r.contradictions.map(c => {
      return `
        <div class="contra-card">
          <div class="contra-header">
            <span class="contra-topic">Topic: ${escapeHTML(c.topic || 'General')}</span>
          </div>
          <div class="contra-statement"><strong>Earlier:</strong> "${escapeHTML(c.earlier || '')}"</div>
          <div class="contra-statement"><strong>Later:</strong> "${escapeHTML(c.current || '')}"</div>
        </div>
      `;
    }).join('');
  } else {
    contraContainer.innerHTML = `<p style="color: var(--text-dim);">No contradictions detected.</p>`;
  }

  // Overall summary
  const behaviorEl = document.getElementById('behaviorSummary');
  if (behaviorEl) {
    behaviorEl.textContent = r.overall_summary || 'No overall summary generated.';
  }
}

function escapeHTML(str) {
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

// Load report
loadReport();
