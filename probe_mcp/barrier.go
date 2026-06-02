package main

// checkBarrier returns true when all non-degraded agents have responded
// to their current phase tasks. Degraded agents are exempt.
func checkBarrier(session *MultiAgentSession) bool {
	return session.AllTasksResponded()
}
