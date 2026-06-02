package main

import (
	"sync"
)

type AgentProbe struct {
	AgentName       string
	AgentID         string
	ProbeID         string
	RegisteredAt    string
	Completed       bool
	ResultSubmitted bool
}

var (
	agentsMu        sync.RWMutex
	agents          = make(map[string]*AgentProbe)
	completedProbes = make(map[string]bool)
)

func registerAgent(a *AgentProbe) {
	agentsMu.Lock()
	defer agentsMu.Unlock()
	agents[a.AgentID] = a
}

func getAgent(agentID string) *AgentProbe {
	agentsMu.RLock()
	defer agentsMu.RUnlock()
	return agents[agentID]
}

func getAllAgents() []*AgentProbe {
	agentsMu.RLock()
	defer agentsMu.RUnlock()
	out := make([]*AgentProbe, 0, len(agents))
	for _, a := range agents {
		out = append(out, a)
	}
	return out
}

func isProbeCompleted(probeID string) bool {
	agentsMu.RLock()
	defer agentsMu.RUnlock()
	return completedProbes[probeID]
}

func markProbeCompleted(probeID string) {
	agentsMu.Lock()
	defer agentsMu.Unlock()
	completedProbes[probeID] = true
}

