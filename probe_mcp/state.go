package main

import (
	"fmt"
	"sync"
)

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

// DebateSession represents a single-agent debate runtime session.
type DebateSession struct {
	SessionID       string
	AgentID         string
	Client          string
	Model           string
	DisplayName     string
	Phase           string
	CurrentTaskID   string
	RetryCount      int
	CompletedPhases map[string]bool // key: task_id
	PhaseCompletions map[string]bool // key: phase name
	ResponseCh      chan struct{}
	mu              sync.RWMutex
}

var (
	sessionsMu sync.RWMutex
	sessions   = make(map[string]*DebateSession) // key: SessionID
)

func createSession(client, model string) *DebateSession {
	sessionsMu.Lock()
	defer sessionsMu.Unlock()

	sessionID := "sess_" + randomHex(8)
	agentID := fmt.Sprintf("%s_%s", client, randomHex(8))
	displayName := fmt.Sprintf("%s(%s)", client, model)

	s := &DebateSession{
		SessionID:        sessionID,
		AgentID:          agentID,
		Client:           client,
		Model:            model,
		DisplayName:      displayName,
		Phase:            PhaseRegistered,
		CompletedPhases:  make(map[string]bool),
		PhaseCompletions: make(map[string]bool),
	}
	sessions[sessionID] = s
	return s
}

func getSession(sessionID string) *DebateSession {
	sessionsMu.RLock()
	defer sessionsMu.RUnlock()
	return sessions[sessionID]
}

func getSessionByAgentID(agentID string) *DebateSession {
	sessionsMu.RLock()
	defer sessionsMu.RUnlock()
	for _, s := range sessions {
		if s.AgentID == agentID {
			return s
		}
	}
	return nil
}

func getAllSessions() []*DebateSession {
	sessionsMu.RLock()
	defer sessionsMu.RUnlock()
	out := make([]*DebateSession, 0, len(sessions))
	for _, s := range sessions {
		out = append(out, s)
	}
	return out
}

func (s *DebateSession) IsPhaseCompleted(taskID string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.CompletedPhases[taskID]
}

func (s *DebateSession) MarkPhaseCompleted(taskID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.CompletedPhases[taskID] = true
	if s.Phase != "" {
		s.PhaseCompletions[s.Phase] = true
	}
}

func (s *DebateSession) GetPhase() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.Phase
}

func (s *DebateSession) SetPhase(phase string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Phase = phase
}

func (s *DebateSession) GetCurrentTaskID() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.CurrentTaskID
}

func (s *DebateSession) SetCurrentTaskID(taskID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.CurrentTaskID = taskID
}

func (s *DebateSession) GetRetryCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.RetryCount
}

func (s *DebateSession) SetRetryCount(n int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.RetryCount = n
}

func (s *DebateSession) ResetResponseCh() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.ResponseCh = make(chan struct{}, 1)
}

func (s *DebateSession) NotifyResponse() {
	s.mu.RLock()
	ch := s.ResponseCh
	s.mu.RUnlock()
	if ch != nil {
		select {
		case ch <- struct{}{}:
		default:
		}
	}
}
