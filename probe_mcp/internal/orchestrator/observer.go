package orchestrator

import (
	"fmt"
	"time"

	"github.com/fluorine/designdoc-mcp/probe/internal/state"
)

// Observer watches the session barrier and signals when all active
// agents have submitted for the current phase.
type Observer interface {
	WaitForBarrier(sessionID string, timeout time.Duration) (bool, error)
}

// BarrierObserver polls CheckBarrier until it returns true or timeout.
// Polling interval is 100 ms to keep tests fast while still being
// realistic.
type BarrierObserver struct{}

func (b *BarrierObserver) WaitForBarrier(sessionID string, timeout time.Duration) (bool, error) {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		sess := state.GetSession(sessionID)
		if sess == nil {
			return false, fmt.Errorf("session %s disappeared", sessionID)
		}
		if state.CheckBarrier(sess) {
			return true, nil
		}
		time.Sleep(100 * time.Millisecond)
	}
	return false, nil
}
