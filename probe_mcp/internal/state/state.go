package state

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"sync"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const MaxAgents = 4

// Phase constants
const (
	PhaseRegistered    = "REGISTERED"
	PhaseProposal      = "PROPOSAL"
	PhaseChallenge     = "CHALLENGE"
	PhaseRevision      = "REVISION"
	PhaseConsensus     = "CONSENSUS"
	PhaseComplete      = "COMPLETE"
	PhaseFailedTimeout = "FAILED_TIMEOUT"
)

// ---------------------------------------------------------------------------
// Agent
// ---------------------------------------------------------------------------

type Agent struct {
	AgentID       string
	Client        string
	Model         string
	DisplayName   string
	Status        string // "active" | "degraded"
	LastSeen      time.Time
	ServerSession *mcp.ServerSession
	Connected     bool
	ConnectionID  string
	mu            sync.RWMutex
}

func (a *Agent) SetStatus(status string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.Status = status
}

func (a *Agent) GetStatus() string {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.Status
}

func (a *Agent) SetServerSession(ss *mcp.ServerSession) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.ServerSession = ss
}

func (a *Agent) GetServerSession() *mcp.ServerSession {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.ServerSession
}

func (a *Agent) SetConnected(v bool, connID string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.Connected = v
	a.ConnectionID = connID
	if v {
		a.LastSeen = time.Now()
	}
}

func (a *Agent) IsConnected() bool {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.Connected
}

// ---------------------------------------------------------------------------
// PhaseTask
// ---------------------------------------------------------------------------

type PhaseTask struct {
	TaskID     string
	Phase      string
	AgentID    string
	TargetID   string // for challenge: whom to challenge
	PushCount  int
	LastPushAt time.Time
	Responded  bool
}

func (t *PhaseTask) IncrementPush() {
	t.PushCount++
	t.LastPushAt = time.Now()
}

func (t *PhaseTask) MarkResponded() {
	t.Responded = true
}

// ---------------------------------------------------------------------------
// MultiAgentSession
// ---------------------------------------------------------------------------

type MultiAgentSession struct {
	SessionID       string
	Phase           string
	Agents          map[string]*Agent // key: agent_id
	AgentOrder      []string          // registration order for challenge topology
	PhaseStartedAt  time.Time
	PhaseDeadline   time.Time
	Tasks           map[string]*PhaseTask // key: task_id
	CompletedPhases map[string]bool
	Completed       bool
	ManuallyStarted bool // UI-controlled start gate
	CreatedAt       time.Time
	mu              sync.RWMutex
}

func NewSession() *MultiAgentSession {
	return &MultiAgentSession{
		SessionID:       "sess_" + RandomHex(8),
		Phase:           PhaseRegistered,
		Agents:          make(map[string]*Agent),
		Tasks:           make(map[string]*PhaseTask),
		CompletedPhases: make(map[string]bool),
		CreatedAt:       time.Now(),
	}
}

func (s *MultiAgentSession) AddAgent(client, model string) *Agent {
	s.mu.Lock()
	defer s.mu.Unlock()

	agentID := fmt.Sprintf("%s_%s", client, RandomHex(8))
	a := &Agent{
		AgentID:     agentID,
		Client:      client,
		Model:       model,
		DisplayName: fmt.Sprintf("%s(%s)", client, model),
		Status:      "active",
		LastSeen:    time.Now(),
	}
	s.Agents[agentID] = a
	s.AgentOrder = append(s.AgentOrder, agentID)
	return a
}

func (s *MultiAgentSession) GetAgent(agentID string) *Agent {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.Agents[agentID]
}

func (s *MultiAgentSession) GetAgents() []*Agent {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*Agent, 0, len(s.Agents))
	for _, id := range s.AgentOrder {
		if a := s.Agents[id]; a != nil {
			out = append(out, a)
		}
	}
	return out
}

func (s *MultiAgentSession) AgentCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.Agents)
}

func (s *MultiAgentSession) ActiveAgentCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	count := 0
	for _, a := range s.Agents {
		if a.Status == "active" {
			count++
		}
	}
	return count
}

func (s *MultiAgentSession) GetPhase() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.Phase
}

func (s *MultiAgentSession) SetPhase(phase string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Phase = phase
	s.PhaseStartedAt = time.Now()
	s.PhaseDeadline = time.Now().Add(30 * time.Second)
	if phase != PhaseRegistered && phase != PhaseComplete && phase != PhaseFailedTimeout {
		s.CompletedPhases[phase] = true
	}
}

func (s *MultiAgentSession) GetTask(taskID string) *PhaseTask {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.Tasks[taskID]
}

func (s *MultiAgentSession) AddTask(task *PhaseTask) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Tasks[task.TaskID] = task
}

func (s *MultiAgentSession) ClearTasks() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Tasks = make(map[string]*PhaseTask)
}

func (s *MultiAgentSession) GetTasks() []*PhaseTask {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*PhaseTask, 0, len(s.Tasks))
	// Return tasks in agent registration order so UI is stable.
	for _, agentID := range s.AgentOrder {
		for _, t := range s.Tasks {
			if t.AgentID == agentID {
				out = append(out, t)
				break
			}
		}
	}
	return out
}

func (s *MultiAgentSession) GetTasksForPhase(phase string) []*PhaseTask {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*PhaseTask, 0)
	for _, t := range s.Tasks {
		if t.Phase == phase {
			out = append(out, t)
		}
	}
	return out
}

func (s *MultiAgentSession) AllTasksResponded() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	for _, t := range s.Tasks {
		agent := s.Agents[t.AgentID]
		if agent != nil && agent.Status == "active" && !t.Responded {
			return false
		}
	}
	return true
}

func (s *MultiAgentSession) MarkTaskResponded(taskID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t := s.Tasks[taskID]
	if t != nil {
		t.Responded = true
	}
}

func (s *MultiAgentSession) GetChallengeTarget(agentID string) string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	for i, id := range s.AgentOrder {
		if id == agentID {
			next := (i + 1) % len(s.AgentOrder)
			return s.AgentOrder[next]
		}
	}
	return ""
}

func (s *MultiAgentSession) IsComplete() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.Completed
}

func (s *MultiAgentSession) SetComplete() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Completed = true
}

func (s *MultiAgentSession) SetManuallyStarted() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.ManuallyStarted = true
}

func (s *MultiAgentSession) IsManuallyStarted() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.ManuallyStarted
}

// ---------------------------------------------------------------------------
// Global session store
// ---------------------------------------------------------------------------

var (
	sessionsMu sync.RWMutex
	sessions   = make(map[string]*MultiAgentSession)
)

func GetOrCreateSessionForAgent(client, model string) (*MultiAgentSession, *Agent, bool) {
	sessionsMu.Lock()
	defer sessionsMu.Unlock()

	// 1. Idempotency: exact client+model already in an active session.
	for _, s := range sessions {
		phase := s.GetPhase()
		if phase == PhaseComplete || phase == PhaseFailedTimeout {
			continue
		}
		for _, a := range s.GetAgents() {
			if a.Client == client && a.Model == model {
				return s, a, false
			}
		}
	}

	// 2. Find a REGISTERED session with room for a new agent.
	for _, s := range sessions {
		if s.GetPhase() == PhaseRegistered && s.AgentCount() < MaxAgents {
			agent := s.AddAgent(client, model)
			return s, agent, true
		}
	}

	// 3. Create new session.
	s := NewSession()
	agent := s.AddAgent(client, model)
	sessions[s.SessionID] = s
	return s, agent, true
}

func GetSession(sessionID string) *MultiAgentSession {
	sessionsMu.RLock()
	defer sessionsMu.RUnlock()
	return sessions[sessionID]
}

func GetSessionByAgentID(agentID string) *MultiAgentSession {
	sessionsMu.RLock()
	defer sessionsMu.RUnlock()
	for _, s := range sessions {
		if s.GetAgent(agentID) != nil {
			return s
		}
	}
	return nil
}

func GetAllSessions() []*MultiAgentSession {
	sessionsMu.RLock()
	defer sessionsMu.RUnlock()
	out := make([]*MultiAgentSession, 0, len(sessions))
	for _, s := range sessions {
		out = append(out, s)
	}
	return out
}

func GetActiveSessions() []*MultiAgentSession {
	sessionsMu.RLock()
	defer sessionsMu.RUnlock()
	out := make([]*MultiAgentSession, 0)
	for _, s := range sessions {
		phase := s.GetPhase()
		if phase != PhaseComplete && phase != PhaseFailedTimeout {
			out = append(out, s)
		}
	}
	return out
}

func DeleteSession(sessionID string) bool {
	sessionsMu.Lock()
	defer sessionsMu.Unlock()
	if _, ok := sessions[sessionID]; ok {
		delete(sessions, sessionID)
		return true
	}
	return false
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func RandomHex(n int) string {
	b := make([]byte, n/2+1)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)[:n]
}

// ComputeResult determines the session outcome.
// PASS    = no agents degraded.
// PARTIAL = some agents degraded but session reached COMPLETE.
// FAIL    = all agents degraded (or session never started).
func ComputeResult(s *MultiAgentSession) string {
	agents := s.GetAgents()
	if len(agents) == 0 {
		return "FAIL"
	}
	degradedCount := 0
	for _, a := range agents {
		if a.GetStatus() == "degraded" {
			degradedCount++
		}
	}
	if degradedCount == len(agents) {
		return "FAIL"
	}
	if degradedCount > 0 {
		return "PARTIAL"
	}
	return "PASS"
}
