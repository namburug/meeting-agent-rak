let currentMeetingId = null;

const uploadForm = document.getElementById("uploadForm");
const uploadError = document.getElementById("uploadError");
const results = document.getElementById("results");
const processBtn = document.getElementById("processBtn");

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  uploadError.textContent = "";
  const file = document.getElementById("fileInput").files[0];
  const meetingDate = document.getElementById("meetingDate").value;
  if (!file || !meetingDate) return;

  const fd = new FormData();
  fd.append("file", file);
  fd.append("meeting_date", meetingDate);

  processBtn.disabled = true;
  processBtn.textContent = "Processing…";
  try {
    const res = await fetch("/api/meetings", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");
    currentMeetingId = data.id;
    if (data.duplicate) {
      uploadError.textContent = "This exact transcript was already processed — showing the existing meeting record (no duplicate created).";
      uploadError.style.color = "var(--amber)";
    } else {
      uploadError.textContent = "";
    }
    await loadMeeting(currentMeetingId);
  } catch (err) {
    uploadError.style.color = "var(--red)";
    uploadError.textContent = err.message;
  } finally {
    processBtn.disabled = false;
    processBtn.textContent = "Process meeting";
  }
});

async function loadMeeting(meetingId) {
  const res = await fetch(`/api/meetings/${meetingId}`);
  const meeting = await res.json();
  renderMeeting(meeting);
  await loadAudit(meetingId);
  results.style.display = "block";
}

function renderMeeting(meeting) {
  document.getElementById("execSummary").textContent = meeting.executive_summary || "(no summary)";
  fillList("decisionsList", meeting.decisions);
  fillList("openQuestionsList", meeting.open_questions);
  fillList("risksList", meeting.risks);
  renderItems(meeting.action_items);
}

function fillList(id, items) {
  const el = document.getElementById(id);
  el.innerHTML = "";
  if (!items || items.length === 0) {
    el.innerHTML = "<li><em>none</em></li>";
    return;
  }
  for (const it of items) {
    const li = document.createElement("li");
    li.textContent = it;
    el.appendChild(li);
  }
}

function renderItems(items) {
  const body = document.getElementById("itemsBody");
  body.innerHTML = "";
  for (const item of items) {
    const tr = document.createElement("tr");
    tr.dataset.itemId = item.id;

    const ownerLabel = item.owner_matched
      ? `${item.owner_name}`
      : `<span class="badge unresolved">unresolved</span> ${item.owner_raw || "—"}`;

    tr.innerHTML = `
      <td><input type="text" data-field="text" value="${escapeAttr(item.text)}"></td>
      <td>${ownerLabel}</td>
      <td><input type="date" data-field="due_date_resolved" value="${item.due_date_resolved || ""}"></td>
      <td>
        <select data-field="priority">
          <option value="low" ${item.priority === "low" ? "selected" : ""}>low</option>
          <option value="medium" ${item.priority === "medium" ? "selected" : ""}>medium</option>
          <option value="high" ${item.priority === "high" ? "selected" : ""}>high</option>
        </select>
      </td>
      <td>${(item.confidence ?? 0).toFixed(2)}</td>
      <td><span class="badge ${item.status}">${item.status}</span></td>
      <td class="row-actions">
        <button class="small secondary" data-action="save">Save</button>
        <button class="small" data-action="approve">Approve</button>
        <button class="small danger" data-action="reject">Reject</button>
      </td>
    `;
    body.appendChild(tr);
  }

  body.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", handleItemAction);
  });
}

function escapeAttr(s) {
  return (s || "").replace(/"/g, "&quot;");
}

async function handleItemAction(e) {
  const action = e.target.dataset.action;
  const tr = e.target.closest("tr");
  const itemId = tr.dataset.itemId;

  if (action === "save") {
    const fields = {};
    tr.querySelectorAll("[data-field]").forEach((el) => {
      fields[el.dataset.field] = el.value;
    });
    await fetch(`/api/items/${itemId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
  } else if (action === "approve" || action === "reject") {
    await fetch(`/api/items/${itemId}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actor: "human:demo-user" }),
    });
  }
  await loadMeeting(currentMeetingId);
}

document.getElementById("finalizeBtn").addEventListener("click", async () => {
  const resultEl = document.getElementById("finalizeResult");
  resultEl.textContent = "Sending…";
  try {
    const res = await fetch(`/api/meetings/${currentMeetingId}/finalize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actor: "human:demo-user" }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Finalize failed");
    resultEl.style.color = "var(--green)";
    resultEl.textContent = data.status === "no_op" ? data.reason : `Sent ${data.items_sent} item(s) to Slack.`;
  } catch (err) {
    resultEl.style.color = "var(--red)";
    resultEl.textContent = err.message;
  }
  await loadAudit(currentMeetingId);
});

async function loadAudit(meetingId) {
  const res = await fetch(`/api/meetings/${meetingId}/audit`);
  const entries = await res.json();
  const el = document.getElementById("auditList");
  el.innerHTML = "";
  for (const e of entries) {
    const div = document.createElement("div");
    div.textContent = `[${e.timestamp}] ${e.actor} — ${e.action} ${e.payload_json}`;
    el.appendChild(div);
  }
}
