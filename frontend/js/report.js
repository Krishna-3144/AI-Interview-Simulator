// backend/static/js/report.js

const params    = new URLSearchParams(window.location.search);
const sessionId = params.get('session') || sessionStorage.getItem('session_id');

if (!sessionId) window.location.href = 'index.html';

async function loadReport() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/analysis`);
    if (!res.ok) throw new Error("Failed to load");
    const data = await res.json();
    
    renderReport(data);
  } catch (err) {
    alert("Error loading report: " + err.message);
  }
}

function renderReport(r) {
  const candEl = document.getElementById('candidateName');
  if (candEl) candEl.textContent = r.candidate_name || 'Candidate';
  
  const roleEl = document.getElementById('targetRole');
  if (roleEl) roleEl.textContent = r.target_role ? `Target Role: ${r.target_role}` : '';
  
  const totalQEl = document.getElementById('totalQuestions');
  if (totalQEl) totalQEl.textContent = `${r.total_questions || 0} questions answered`;

  // Calculate overall average
  const tech = r.technical_score || 0;
  const comm = r.communication_score || 0;
  const gram = r.grammar_score || 0;
  let count = 0;
  if (r.technical_score !== undefined) count++;
  if (r.communication_score !== undefined) count++;
  if (r.grammar_score !== undefined) count++;
  const overall = count > 0 ? (tech + comm + gram) / count : 0;
  
  const overallScoreEl = document.getElementById('overallScore');
  if (overallScoreEl) {
    overallScoreEl.innerHTML = `${overall.toFixed(0)}<span>/ 100</span>`;
  }

  // Set the three individual score bars
  const setScore = (idPrefix, val) => {
    const numEl = document.getElementById(`${idPrefix}Num`);
    const barEl = document.getElementById(`${idPrefix}Bar`);
    if (numEl) numEl.textContent = val !== undefined ? val.toFixed(1) : '0.0';
    if (barEl) barEl.style.width = val !== undefined ? `${val}%` : '0%';
  };

  setScore('techScore', r.technical_score);
  setScore('commScore', r.communication_score);
  setScore('gramScore', r.grammar_score);

  // Removed skillsGrid based on user feedback

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
      let evidenceHtml = '';
      if (c.earlier_statement && c.current_statement) {
         evidenceHtml = `
            <div class="contra-statement"><strong>Earlier:</strong> "${escapeHTML(c.earlier_statement)}"</div>
            <div class="contra-statement"><strong>Current:</strong> "${escapeHTML(c.current_statement)}"</div>
         `;
      } else if (c.evidence && c.evidence.length > 0) {
         // Fallback for old sessions
         evidenceHtml = c.evidence.map(e => `<div class="contra-statement">"${escapeHTML(e)}"</div>`).join('');
      }
      return `
        <div class="contra-card">
          <div class="contra-header">
            <span class="contra-topic">Category ${escapeHTML(c.category || 'Unknown')} | Topic: ${escapeHTML(c.topic || 'General')}</span>
          </div>
          ${evidenceHtml}
          <div class="contra-statement" style="margin-top: 8px; color: var(--danger);"><strong>Reason:</strong> ${escapeHTML(c.reason || '')}</div>
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
