// static/js/focus_session.js
class FocusSessionManager {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.socket = new WebSocket(
      `ws://${window.location.host}/ws/focus_session/${sessionId}/`,
    );
    this.socket.onmessage = (e) => this.handleMessage(JSON.parse(e.data));
    this.socket.onclose = (e) => this.reloadWindowAfterDelay();
    this.remainingTime = 0;
    this.timerInterval = null;
  }

  reloadWindowAfterDelay() {
    setTimeout(this.reloadWindow, 2000);
  }

  reloadWindow() {
    // TODO: instead show a popup
    console.log("connection to server is dropped so reloading page");
    location.reload();
  }

  handleMessage(data) {
    if (data.type === "timer_update") {
      this.display_updated_timer_data(data);
    }
  }

  display_updated_timer_data(data) {
    console.log(data);
    console.log("got this data from backend");

    const timerDisplayData = data.timer_display_data;

    if (timerDisplayData.timer_state != "completed") {
      // only show the timer if the timer is not completed
      this.updateRemainingTimeDisplay(timerDisplayData.remaining_time);

      if (timerDisplayData.timer_state == "running") {
        this.startClientSideTimer(timerDisplayData.remaining_time);
      }

      // Update current cycle information
      const currentCycleElement = document.getElementById('current-cycle');
      currentCycleElement.textContent = `Current Cycle: ${timerDisplayData.current_cycle.type} - ${this.formatTime(timerDisplayData.current_cycle.duration_seconds)}`;

      // Update remaining cycles
      const focusCyclesListElement = document.getElementById('focus-cycles-list');
      focusCyclesListElement.innerHTML = ''; // Clear existing content
      Object.entries(timerDisplayData.focus_cycles).forEach(([order, cycle]) => {
        const cycleElement = document.createElement('div');
        let completed_cycle_prefix = "ᛜ";
        if (cycle.is_completed) {
          completed_cycle_prefix = "✅";
        } else if (cycle.order == timerDisplayData.current_cycle.order) {
          completed_cycle_prefix = "👉";
        }
        cycleElement.textContent = `${completed_cycle_prefix} Cycle ${order}: ${cycle.type} - ${this.formatTime(cycle.duration_seconds)}`;
        focusCyclesListElement.appendChild(cycleElement);
      });

    } else {
      this.stopClientSideTimer();
      document.getElementById("focus-session-container").innerHTML = "<h1>Session Completed</h1>";
    }
  }

  formatTime(seconds) {
    const totalMinutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${totalMinutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  }

  updateRemainingTimeDisplay(seconds) {
    const remainingTimeElement = document.getElementById('remaining-time');
    remainingTimeElement.textContent = `Remaining Time: ${this.formatTime(seconds)}`;
  }

  startClientSideTimer(initialTime) {
    this.stopClientSideTimer(); // Clear any existing interval
    this.remainingTime = initialTime;
    this.updateRemainingTimeDisplay(this.remainingTime);

    this.timerInterval = setInterval(() => {
      this.remainingTime--;
      this.updateRemainingTimeDisplay(this.remainingTime);

      if (this.remainingTime <= 0) {
        this.stopClientSideTimer();
        this.transitionToNextCycle();
      }
    }, 1000);
  }

  stopClientSideTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  toggleTimer() {
    // since we are toggling the timer
    // this will send request to backend to toggle the timer
    // and backend will send updated timer details
    // so here we can't stop the client side timer
    this.stopClientSideTimer();
    this.send_data_to_server(
      { "action": "toggle_timer" }
    )
  }

  stopTimer() {
    this.send_data_to_server(
      { "action": "stop_timer" }
    )
  }

  transitionToNextCycle() {
    console.log("transitioning to next cycle");
    this.send_data_to_server(
      { "action": "transition_to_next_cycle" }
    )
  }

  send_data_to_server(data) {
    this.socket.send(JSON.stringify(data));
  }
}

// Initialize the FocusSessionManager when the page loads
let focusSessionManager;
document.addEventListener("DOMContentLoaded", (event) => {
  const sessionId = document.getElementById("session-id").dataset.sessionId;
  focusSessionManager = new FocusSessionManager(sessionId);
});
