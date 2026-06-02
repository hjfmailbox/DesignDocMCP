package state

// CheckBarrier returns true when all non-degraded agents have responded
// to their current phase tasks. Degraded agents are exempt.
func CheckBarrier(session *MultiAgentSession) bool {
	return session.AllTasksResponded()
}
