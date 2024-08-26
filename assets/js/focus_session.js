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
    this.originalTitle = document.title;
    this.lastSyncTime = Date.now();
  }

  // *****************************************
  // ********* WebSocket Handlers **********
  // *****************************************

  handleMessage(data) {
    if (data.type === "timer_update") {
      this.display_updated_timer_data(data);
      // since we got this time from server
      // it is synced with server time
      // so we can update our last sync time
      this.lastSyncTime = Date.now();
    } else if (data.type === "followers_update") {
      this.update_session_followers_list(data);
    } else if (data.type === "will_finish_at_update") {
      this.update_will_finish_at_display(data);
    }
  }

  transitionToNextCycle() {
    console.log("transitioning to next cycle");
    this.send_data_to_server(
      { "action": "transition_to_next_cycle" }
    )
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

  sync_inactive_timer() {
    this.send_data_to_server(
      { "action": "sync_inactive_timer" }
    )
  }

  // *****************************************
  // ********** Helper Functions **********
  // *****************************************

  send_data_to_server(data) {
    this.socket.send(JSON.stringify(data));
  }

  reloadWindowAfterDelay() {
    setTimeout(this.reloadWindow, 2000);
  }

  reloadWindow() {
    // TODO: instead show a popup
    console.log("connection to server is dropped so reloading page");
    location.reload();
  }

  display_updated_timer_data(data) {
    console.log(data);
    console.log("got this data from backend");

    const timerDisplayData = data.timer_display_data;
    this.stopClientSideTimer(); // Clear any existing interval
    this.resetPageTitle();  // reset page title incase it was changed

    if (timerDisplayData.timer_state != "completed") {
      // only show the timer if the timer is not completed
      this.updateRemainingTimeDisplay(timerDisplayData.remaining_time);

      if (timerDisplayData.timer_state == "running") {
        this.startClientSideTimer(timerDisplayData);
        this.update_timer_toggle_icon_to_play();
      } else {
        this.update_timer_toggle_icon_to_pause();
      }

      // Update current cycle information
      const currentCycleElement = document.getElementById('current-cycle');
      currentCycleElement.textContent = `Current Cycle: ${timerDisplayData.current_cycle.type} - ${this.formatTime(timerDisplayData.current_cycle.duration_seconds)}`;

      // Update focus cycles list
      this.update_focus_cycles_list(timerDisplayData);

    } else {
      document.getElementById("focus-session-container").innerHTML = "<h1>Session Completed</h1>";
    }
  }

  formatTime(seconds) {
    const totalMinutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60; // remainder of seconds after dividing by 60
    return `${totalMinutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  }

  startClientSideTimer(timerDisplayData) {
    this.stopClientSideTimer(); // Clear any existing interval
    this.remainingTime = timerDisplayData.remaining_time;
    this.updateRemainingTimeDisplay(this.remainingTime);

    this.timerInterval = setInterval(() => {
      if (this.remainingTime <= 0) {
        this.stopClientSideTimer();
        this.transitionToNextCycle();
        return;
      }
      this.remainingTime--;
      this.updateRemainingTimeDisplay(this.remainingTime);
      this.updatePageTitleToCurrentCycle(this.remainingTime, timerDisplayData.current_cycle.type);

    }, 1000);
  }

  stopClientSideTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
      console.log("stopped client side timer");
    }
  }


  // *****************************************
  // ********** UI Update Functions *********
  // *****************************************

  updateRemainingTimeDisplay(seconds) {
    const remainingTimeElement = document.getElementById('remaining-time');
    let formattedTime = this.formatTime(seconds);
    remainingTimeElement.textContent = `Remaining Time: ${formattedTime}`;
  }

  updatePageTitleToCurrentCycle(seconds, current_cycle_type) {
    let formattedTime = this.formatTime(seconds);
    document.title = `${formattedTime} - ${current_cycle_type}`;
  }

  resetPageTitle() {
    document.title = this.originalTitle;
  }

  update_will_finish_at_display(data) {
    const willFinishAtElement = document.getElementById('will-finish-at');
    willFinishAtElement.textContent = `Session will finish at: ${data.will_finish_at_timestamp}`;
  }

  update_focus_cycles_list(timerDisplayData) {
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
  }

  update_timer_toggle_icon_to_play() {
    let timerToggleIcon = document.getElementById("timer-toggle-icon")
    // we are using conditional check here as for a follower
    // the timer toggle icon and text is not present
    if (timerToggleIcon) {
      timerToggleIcon.className = "fa-regular fa-circle-pause";
    }
    let timerToggleText = document.getElementById("timer-toggle-text")
    if (timerToggleText) {
      timerToggleText.textContent = "Pause";
    }
  }

  update_timer_toggle_icon_to_pause() {
    // we are using conditional check here as for a follower
    // the timer toggle icon and text is not present
    let timerToggleIcon = document.getElementById("timer-toggle-icon")
    if (timerToggleIcon) {
      timerToggleIcon.className = "fa-regular fa-circle-play";
    }
    let timerToggleText = document.getElementById("timer-toggle-text")
    if (timerToggleText) {
      timerToggleText.textContent = "Resume";
    }
  }

  update_session_followers_list(data) {
    const followersList = document.getElementById('session-followers-list');
    if (followersList) {
      followersList.innerHTML = '<h3>Session Followers</h3>';
      followersList.innerHTML += '<ul>';
      data.followers.forEach(follower => {
        const joinedDate = new Date(follower.joined_at).toLocaleString();
        followersList.innerHTML += `<li>${follower.username} (Joined: ${joinedDate})</li>`;
      });
      followersList.innerHTML += '</ul>';
    }
  }

}

// Initialize the FocusSessionManager when the page loads
let focusSessionManager;
document.addEventListener("DOMContentLoaded", (event) => {
  const sessionId = document.getElementById("session-id").dataset.sessionId;
  focusSessionManager = new FocusSessionManager(sessionId);

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
      const currentTime = Date.now();
      // Convert to seconds
      const timeSinceLastSync = (currentTime - focusSessionManager.lastSyncTime) / 1000;
      if (timeSinceLastSync > 300) {  // 300 seconds = 5 minutes
        console.log("since timer last synced", timeSinceLastSync, "seconds");
        console.log("syncing inactive timer");
        focusSessionManager.sync_inactive_timer();
      }
    }
  });

});
