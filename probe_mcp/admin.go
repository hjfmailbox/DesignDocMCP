package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// ---------------------------------------------------------------------------
// Manual advance logic
// ---------------------------------------------------------------------------

func manualAdvanceSession(sessionID string) error {
	s := getSession(sessionID)
	if s == nil {
		return fmt.Errorf("session not found")
	}

	phase := s.GetPhase()
	switch phase {
	case PhaseRegistered:
		enterPhase(s, PhaseProposal)
	case PhaseProposal:
		enterPhase(s, PhaseChallenge)
	case PhaseChallenge:
		enterPhase(s, PhaseRevision)
	case PhaseRevision:
		enterPhase(s, PhaseConsensus)
	case PhaseConsensus:
		s.SetPhase(PhaseComplete)
		s.SetComplete()
		logTimeline(s.SessionID, "session_complete", PhaseComplete, "")
		writeSessionReport(s, computeResult(s))
	case PhaseComplete, PhaseFailedTimeout:
		return fmt.Errorf("session already in terminal state %s", phase)
	default:
		return fmt.Errorf("unknown phase %s", phase)
	}
	return nil
}

// ---------------------------------------------------------------------------
// Ping helper
// ---------------------------------------------------------------------------

func sendPingToAgent(agent *Agent, pingID string) {
	ss := agent.GetServerSession()
	if ss == nil {
		return
	}
	payload := map[string]any{
		"ping_id": pingID,
	}
	data, _ := json.Marshal(payload)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	logNotificationSent("", agent.AgentID, agent.DisplayName, "PING", "", "logging/message", payload)

	err := ss.Log(ctx, &mcp.LoggingMessageParams{
		Level:  mcp.LoggingLevel("info"),
		Data:   string(data),
		Logger: "probe/ping",
	})
	if err != nil {
		fmt.Printf("ping failed for agent %s: %v\n", agent.AgentID, err)
	}
}

// ---------------------------------------------------------------------------
// HTTP API handlers
// ---------------------------------------------------------------------------

type agentSnapshot struct {
	AgentID     string `json:"agent_id"`
	DisplayName string `json:"display_name"`
	Status      string `json:"status"`
}

type taskSnapshot struct {
	TaskID    string `json:"task_id"`
	AgentID   string `json:"agent_id"`
	Responded bool   `json:"responded"`
	PushCount int    `json:"push_count"`
	TargetID  string `json:"target_id,omitempty"`
}

type sessionSnapshot struct {
	SessionID       string          `json:"session_id"`
	Phase           string          `json:"phase"`
	AgentCount      int             `json:"agent_count"`
	ActiveCount     int             `json:"active_count"`
	ManuallyStarted bool            `json:"manually_started"`
	CreatedAt       time.Time       `json:"created_at"`
	PhaseStartedAt  time.Time       `json:"phase_started_at"`
	Agents          []agentSnapshot `json:"agents"`
	Tasks           []taskSnapshot  `json:"tasks"`
}

func handleAPISessions(w http.ResponseWriter, _ *http.Request) {
	sessions := getAllSessions()
	out := make([]sessionSnapshot, 0, len(sessions))
	for _, s := range sessions {
		agents := s.GetAgents()
		agentSnaps := make([]agentSnapshot, 0, len(agents))
		for _, a := range agents {
			agentSnaps = append(agentSnaps, agentSnapshot{
				AgentID:     a.AgentID,
				DisplayName: a.DisplayName,
				Status:      a.GetStatus(),
			})
		}
		tasks := s.GetTasks()
		taskSnaps := make([]taskSnapshot, 0, len(tasks))
		for _, t := range tasks {
			taskSnaps = append(taskSnaps, taskSnapshot{
				TaskID:    t.TaskID,
				AgentID:   t.AgentID,
				Responded: t.Responded,
				PushCount: t.PushCount,
				TargetID:  t.TargetID,
			})
		}
		out = append(out, sessionSnapshot{
			SessionID:       s.SessionID,
			Phase:           s.GetPhase(),
			AgentCount:      s.AgentCount(),
			ActiveCount:     s.ActiveAgentCount(),
			ManuallyStarted: s.IsManuallyStarted(),
			CreatedAt:       s.CreatedAt,
			PhaseStartedAt:  s.PhaseStartedAt,
			Agents:          agentSnaps,
			Tasks:           taskSnaps,
		})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(out)
}

func handleAPIAdvance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		SessionID string `json:"session_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if err := manualAdvanceSession(req.SessionID); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func handleAPIStart(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		SessionID string `json:"session_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	s := getSession(req.SessionID)
	if s == nil {
		http.Error(w, "session not found", http.StatusNotFound)
		return
	}
	if s.GetPhase() != PhaseRegistered {
		http.Error(w, "session already started", http.StatusBadRequest)
		return
	}
	s.SetManuallyStarted()
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "started"})
}

func handleAPIDelete(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		SessionID string `json:"session_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if !deleteSession(req.SessionID) {
		http.Error(w, "session not found", http.StatusNotFound)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "deleted"})
}

func handleAPIPing(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var req struct {
		SessionID string `json:"session_id"`
		AgentID   string `json:"agent_id,omitempty"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	s := getSession(req.SessionID)
	if s == nil {
		http.Error(w, "session not found", http.StatusNotFound)
		return
	}

	pingID := "ping_" + randomHex(6)
	agents := s.GetAgents()
	pinged := 0
	for _, agent := range agents {
		if req.AgentID != "" && agent.AgentID != req.AgentID {
			continue
		}
		logPingSent(s.SessionID, agent.AgentID, pingID)
		sendPingToAgent(agent, pingID)
		pinged++
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"status":   "ok",
		"ping_id":  pingID,
		"pinged":   pinged,
	})
}

// ---------------------------------------------------------------------------
// Static UI page
// ---------------------------------------------------------------------------

func handleUI(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(uiHTML))
}

const uiHTML = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MiniDebateRuntime Admin</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; background: #f5f6f7; color: #222; }
  h1 { margin: 0 0 20px; font-size: 22px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; }
  .card { background: #fff; border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .card h2 { margin: 0 0 10px; font-size: 15px; color: #555; word-break: break-all; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
  .phase-REGISTERED { background: #e8f0fe; color: #174ea6; }
  .phase-PROPOSAL { background: #fce8e6; color: #a50e0e; }
  .phase-CHALLENGE { background: #fef7e0; color: #b06000; }
  .phase-REVISION { background: #e6f4ea; color: #137333; }
  .phase-CONSENSUS { background: #f3e8fd; color: #6b1cb0; }
  .phase-COMPLETE { background: #e8eaed; color: #3c4043; }
  .phase-FAILED_TIMEOUT { background: #fce8e6; color: #c5221f; }
  .row { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
  .agents { margin-top: 10px; }
  .agent { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
  .agent:last-child { border-bottom: none; }
  .status-active { color: #137333; }
  .status-degraded { color: #c5221f; }
  .tasks { margin-top: 10px; font-size: 12px; }
  .task { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #f8f8f8; }
  .responded-yes { color: #137333; }
  .responded-no { color: #c5221f; }
  button { padding: 6px 14px; border: none; border-radius: 6px; background: #1a73e8; color: #fff; font-size: 13px; cursor: pointer; }
  button:hover { background: #1557b0; }
  button:disabled { background: #dadce0; color: #5f6368; cursor: not-allowed; }
  .btn-danger { background: #ea4335; }
  .btn-danger:hover { background: #c5221f; }
  .btn-ping { background: #34a853; }
  .btn-ping:hover { background: #1e8e3e; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .empty { color: #888; font-size: 14px; margin-top: 10px; }
  .refresh { margin-bottom: 16px; font-size: 12px; color: #666; }
  .ping-result { margin-top: 8px; font-size: 12px; color: #137333; }
</style>
</head>
<body>
<h1>MiniDebateRuntime Admin</h1>
<div class="refresh">自动刷新每 2 秒 | <a href="/ui" style="color:#1a73e8">立即刷新</a></div>
<div id="app" class="grid"></div>

<script>
const phaseOrder = ['REGISTERED','PROPOSAL','CHALLENGE','REVISION','CONSENSUS','COMPLETE'];
const phaseNext = {
  'REGISTERED':'PROPOSAL','PROPOSAL':'CHALLENGE','CHALLENGE':'REVISION','REVISION':'CONSENSUS','CONSENSUS':'COMPLETE'
};

async function load() {
  try {
    const res = await fetch('/api/sessions');
    const sessions = await res.json();
    render(sessions);
  } catch (e) {
    document.getElementById('app').innerHTML = '<div class="empty">加载失败: '+e.message+'</div>';
  }
}

function render(sessions) {
  const app = document.getElementById('app');
  if (!sessions.length) {
    app.innerHTML = '<div class="empty">暂无 Session</div>';
    return;
  }
  app.innerHTML = sessions.map(s => {
    const isTerminal = s.phase === 'COMPLETE' || s.phase === 'FAILED_TIMEOUT';
    const isRegistered = s.phase === 'REGISTERED';
    const nextPhase = phaseNext[s.phase] || '—';
    const btnText = isRegistered ? (s.manually_started ? '等待开始…' : '开始') : (isTerminal ? '已完成' : '手动推进');
    const btnAction = isRegistered ? 'startSession' : 'advance';
    const btnDisabled = isTerminal || (isRegistered && s.manually_started);

    const tasksHtml = s.tasks.length ? s.tasks.map(t =>
      '<div class="task">' +
      '<span>' + t.agent_id.slice(0,24) + '…</span>' +
      '<span class="' + (t.responded ? 'responded-yes' : 'responded-no') + '">' +
      (t.responded ? '已响应' : '待响应') + ' (推送' + t.push_count + '次)' +
      (t.target_id ? ' → ' + t.target_id.slice(0,20)+'…' : '') +
      '</span></div>'
    ).join('') : '<div class="empty">无任务</div>';

    const agentsPingHtml = s.agents.map(a =>
      '<button class="btn-ping" onclick="pingAgent(\'' + s.session_id + '\',\'' + a.agent_id + '\')">Ping ' + a.display_name + '</button>'
    ).join('');

    return '<div class="card">' +
      '<h2>' + s.session_id + '</h2>' +
      '<div class="row">' +
        '<span class="badge phase-' + s.phase + '">' + s.phase + '</span>' +
        '<span style="font-size:12px;color:#666">agents: ' + s.active_count + '/' + s.agent_count + ' active</span>' +
      '</div>' +
      '<div class="agents">' +
        s.agents.map(a =>
          '<div class="agent">' +
          '<span>' + a.display_name + '</span>' +
          '<span class="status-' + a.status + '">' + a.status + '</span>' +
          '</div>'
        ).join('') +
      '</div>' +
      '<div class="tasks">' + tasksHtml + '</div>' +
      '<div class="row" style="margin-top:14px">' +
        '<span style="font-size:12px;color:#888">' + (isTerminal ? '已结束' : (isRegistered ? '等待开始' : '下一阶段: ' + nextPhase)) + '</span>' +
        '<div class="actions">' +
          '<button class="btn-danger" onclick="delSession(\'' + s.session_id + '\')">删除</button>' +
          '<button ' + (btnDisabled ? 'disabled' : '') + ' onclick="' + btnAction + '(\'' + s.session_id + '\')">' + btnText + '</button>' +
        '</div>' +
      '</div>' +
      '<div class="actions" style="margin-top:10px">' +
        '<button class="btn-ping" onclick="pingSession(\'' + s.session_id + '\')">Ping All</button>' +
        agentsPingHtml +
      '</div>' +
      '<div id="ping-result-' + s.session_id + '" class="ping-result"></div>' +
    '</div>';
  }).join('');
}

async function advance(sessionId) {
  if (!confirm('确认手动推进 Session 到下一阶段？')) return;
  try {
    const res = await fetch('/api/advance', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({session_id: sessionId})
    });
    if (!res.ok) throw new Error(await res.text());
    load();
  } catch (e) {
    alert('推进失败: ' + e.message);
  }
}

async function startSession(sessionId) {
  if (!confirm('确认开始 Session？agent 将收到 PROPOSAL 推送。')) return;
  try {
    const res = await fetch('/api/start', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({session_id: sessionId})
    });
    if (!res.ok) throw new Error(await res.text());
    load();
  } catch (e) {
    alert('开始失败: ' + e.message);
  }
}

async function delSession(sessionId) {
  if (!confirm('确认删除 Session ' + sessionId + '？此操作不可恢复。')) return;
  try {
    const res = await fetch('/api/delete', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({session_id: sessionId})
    });
    if (!res.ok) throw new Error(await res.text());
    load();
  } catch (e) {
    alert('删除失败: ' + e.message);
  }
}

async function pingSession(sessionId) {
  try {
    const res = await fetch('/api/ping', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({session_id: sessionId})
    });
    const data = await res.json();
    document.getElementById('ping-result-' + sessionId).textContent = 'Ping OK: ' + data.ping_id + ' (' + data.pinged + ' agents)';
  } catch (e) {
    document.getElementById('ping-result-' + sessionId).textContent = 'Ping failed: ' + e.message;
  }
}

async function pingAgent(sessionId, agentId) {
  try {
    const res = await fetch('/api/ping', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({session_id: sessionId, agent_id: agentId})
    });
    const data = await res.json();
    document.getElementById('ping-result-' + sessionId).textContent = 'Ping OK: ' + data.ping_id + ' (' + data.pinged + ' agents)';
  } catch (e) {
    document.getElementById('ping-result-' + sessionId).textContent = 'Ping failed: ' + e.message;
  }
}

load();
setInterval(load, 2000);
</script>
</body>
</html>
`

// mux routes /mcp, /api/*, /ui
func adminMux(mcpHandler http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		path := strings.TrimRight(req.URL.Path, "/")
		switch path {
		case "/api/sessions":
			handleAPISessions(w, req)
		case "/api/advance":
			handleAPIAdvance(w, req)
		case "/api/start":
			handleAPIStart(w, req)
		case "/api/delete":
			handleAPIDelete(w, req)
		case "/api/ping":
			handleAPIPing(w, req)
		case "/ui", "/admin":
			handleUI(w, req)
		default:
			mcpHandler.ServeHTTP(w, req)
		}
	})
}
