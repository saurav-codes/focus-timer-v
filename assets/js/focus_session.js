// static/js/focus_session.js
class FocusSessionManager {
  constructor(sessionId, username, debug) {
    this.sessionId = sessionId;
    this.username = username;
    const protocol = debug ? 'ws' : 'wss';
    this.socket = new WebSocket(
      `${protocol}://${window.location.host}/ws/focus_session/${sessionId}/${username}`,
    );
    this.socket.onmessage = (e) => this.handleMessage(JSON.parse(e.data));
    this.socket.onclose = (e) => this.reloadWindowAfterDelay();
    this.remainingTime = 0;
    this.timerInterval = null;
    this.originalTitle = document.title;
    this.lastSyncTime = Date.now();
    this.willFinishAt = document.getElementById('will-finish-at')?.dataset.willFinishAt;
    console.log(`FocusSessionManager initialized for session: ${sessionId}, user: ${username}`);
    this.updateFinishTime();

  }

  // *****************************************
  // ********* WebSocket Handlers **********
  // *****************************************

  handleMessage(data) {
    if (data.type === "timer_update") {
      console.log("Received timer update from server", data);
      this.display_updated_timer_data(data);
      // since we got this time from server
      // it is synced with server time
      // so we can update our last sync time
      this.lastSyncTime = Date.now();
    } else if (data.type === "followers_update") {
      console.log("Received followers update from server", data);
      this.update_session_followers_list(data);
    } else if (data.type === "will_finish_at_update") {
      console.log("Received will finish at update from server", data);
      this.willFinishAt = data.will_finish_at;
      this.updateFinishTime();
    } else if (data.type === "onesignal_tag") {
      console.log("Received OneSignal tag update", data);
      this.setOneSignalTag(data.session_id);
    }
  }

  toggleTimer() {
    console.log("Toggling timer");
    // since we are toggling the timer
    // this will send request to backend to toggle the timer
    // and backend will send updated timer details
    // so here we can't stop the client side timer
    this.stopClientSideTimer();
    this.send_action_to_server(
      { "action": "toggle_timer" }
    )
  }

  stopTimer() {
    console.log("Stopping timer");
    this.send_action_to_server(
      { "action": "stop_timer" }
    )
  }

  sync_timer() {
    console.log("Syncing timer");
    this.send_action_to_server(
      { "action": "sync_timer" }
    )
  }

  skipCycle() {
    console.log("Skipping cycle");
    // show a loading state
    let skipButton = document.getElementById('skip-cycle-btn');
    const skipButtonOriginalText = skipButton.innerHTML;
    this.send_action_to_server(
      { "action": "skip_cycle" }
    )
    if (skipButton) {
      // disable skip button for 2 seconds
      skipButton.disabled = true;
      // enable skip button after 3 seconds
      setTimeout(() => {
        if (skipButton) {
          skipButton.innerHTML = skipButtonOriginalText;
          skipButton.disabled = false;
        }
      }, 3000);
    }
  }

  // *****************************************
  // ********** Helper Functions **********
  // *****************************************

  send_action_to_server(event_type) {
    console.log("Sending action to server", event_type);
    this.socket.send(JSON.stringify(event_type));
  }

  reloadWindowAfterDelay() {
    console.log("Connection to server is dropped, reloading page in 2 seconds");
    setTimeout(this.reloadWindow, 2000);
  }

  reloadWindow() {
    // TODO: instead show a popup
    console.log("connection to server is dropped so reloading page");
    location.reload();
  }

  display_updated_timer_data(data) {
    console.log("Displaying updated timer data", data);
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
      if (currentCycleElement) {
        currentCycleElement.textContent = `Current Cycle: ${timerDisplayData.current_cycle.type} - ${this.formatTime(timerDisplayData.current_cycle.duration_seconds)}`;
      }
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
    console.log("Starting client-side timer", timerDisplayData);
    this.stopClientSideTimer(); // Clear any existing interval
    const endTime = Date.now() + timerDisplayData.remaining_time * 1000;
    this.remainingTime = timerDisplayData.remaining_time;
    this.updateRemainingTimeDisplay(this.remainingTime);

    this.timerInterval = setInterval(() => {
      if (this.remainingTime <= 0) {
        // if current focus cycle is completed
        // then we need to transition to next cycle
        // and also stop the current cycle timer
        this.stopClientSideTimer();
        console.log("Current cycle is completed");
        this.remainingTime = 0;
        this.updateRemainingTimeDisplay(this.remainingTime);
        return;
      }
      const currentTime = Date.now();
      this.remainingTime = Math.round((endTime - currentTime) / 1000);
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
    if (remainingTimeElement) {
      let formattedTime = this.formatTime(seconds);
      remainingTimeElement.textContent = `${formattedTime}`;
    }
    this.updateZenMode();
  }

  updatePageTitleToCurrentCycle(seconds, current_cycle_type) {
    let formattedTime = this.formatTime(seconds);
    document.title = `${formattedTime} - ${current_cycle_type}`;
  }

  resetPageTitle() {
    document.title = this.originalTitle;
    console.log("Reset page title to original");
  }

  update_will_finish_at_display(data) {
    const willFinishAtElement = document.getElementById('will-finish-at');
    if (willFinishAtElement) {
      willFinishAtElement.textContent = `Session will finish at: ${this.formatLocalDateTime(data.will_finish_at_timestamp)}`;
      console.log(`Updated will finish at display: ${data.will_finish_at_timestamp}`);
    }
  }

  update_focus_cycles_list(timerDisplayData) {
    const focusCyclesContent = document.getElementById('focus-cycles-content');
    const stackedCycles = document.getElementById('stacked-cycles');
    if (focusCyclesContent && stackedCycles) {
      let cyclesHtml = '<ul class="space-y-2">';
      let stackedHtml = '';
      let stackedCount = 0;
      let additionalCycles = 0;

      Object.entries(timerDisplayData.focus_cycles).forEach(([order, cycle]) => {
        const cycleStatus = cycle.is_completed ? '✅' : (cycle.order == timerDisplayData.current_cycle.order ? '👉' : '⏳');
        const cycleIcon = this.getCycleIcon(cycle.type);

        // Add all cycles to the expanded list
        cyclesHtml += `
          <li class="flex items-center space-x-3">
            <span class="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-gray-700 rounded-full">${cycleIcon}</span>
            <div>
              <p class="text-sm font-medium">${cycleStatus} ${cycle.type} - ${this.formatTime(cycle.duration_seconds)}</p>
            </div>
          </li>
        `;

        // Add up to 5 cycles to the stacked view
        if (stackedCount < 5 && !cycle.is_completed) {
          stackedHtml += `<span class="w-6 h-6 flex items-center justify-center bg-gray-700 rounded-full text-xs">${cycleIcon}</span>`;
          stackedCount++;
        } else if (!cycle.is_completed) {
          additionalCycles++;
        }
      });

      cyclesHtml += '</ul>';
      focusCyclesContent.innerHTML = cyclesHtml;

      if (additionalCycles > 0) {
        stackedHtml += `<span class="flex items-center justify-center w-6 h-6 text-xs font-medium text-white bg-gray-700 rounded-full">+${additionalCycles}</span>`;
      }
      stackedCycles.innerHTML = stackedHtml;

      console.log("Updated focus cycles list in UI");
    }
  }

  getCycleIcon(cycleType) {
    switch(cycleType.toLowerCase()) {
      case 'focus':
        return '🎯';
      case 'break':
        return '☕';
      default:
        return '⏳';
    }
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
    console.log("Updated timer toggle icon to play");
    this.updateZenModeToggleIcon(true);
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
    console.log("Updated timer toggle icon to pause");
    this.updateZenModeToggleIcon(false);
  }

  update_session_followers_list(data) {
    console.log("Updating session followers list", data);
    const followersContainer = document.getElementById('session-followers-container');
    const stackedFollowers = document.getElementById('stacked-followers');
    if (followersContainer && stackedFollowers) {
      let allUsers = [];

      Object.entries(data.followers).forEach(([username, follower]) => {
        const joinedDate = new Date(follower.joined_at).toLocaleString();
        allUsers.push({ username: username, joined_at: joinedDate });
      });

      // Update expanded list view
      followersContainer.innerHTML = '<ul class="space-y-2">';
      allUsers.forEach(user => {
        const avatar = generateAvatar(user.username);
        followersContainer.innerHTML += `
          <li class="flex items-center space-x-3">
            <img class="w-8 h-8 rounded-full" src="${avatar}" alt="${user.username}">
            <div>
              <p class="text-sm font-medium">${user.username}</p>
              <p class="text-xs text-gray-500">Joined at: ${user.joined_at}</p>
            </div>
          </li>
        `;
      });
      followersContainer.innerHTML += '</ul>';

      // Update stacked view
      stackedFollowers.innerHTML = '';
      allUsers.slice(0, 3).forEach(user => {
        const avatar = generateAvatar(user.username);
        stackedFollowers.innerHTML += `<img class="w-6 h-6 border-2 border-white rounded-full dark:border-gray-800" src="${avatar}" alt="${user.username}">`;
      });
      if (allUsers.length > 3) {
        stackedFollowers.innerHTML += `<span class="flex items-center justify-center w-6 h-6 text-xs font-medium text-white bg-gray-700 border-2 border-white rounded-full">+${allUsers.length - 3}</span>`;
      }

      console.log("Updated session followers list in UI");
    }
  }

  setOneSignalTag(sessionId) {
    if (typeof OneSignal !== 'undefined') {
      OneSignal.push(function () {
        OneSignal.User.addTag("session_id", sessionId);
        console.log(`OneSignal tag set for session: ${sessionId}`);
      });
    } else {
      console.error("OneSignal is not defined");
    }
  }

  formatLocalDateTime(date) {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'medium'
    }).format(date);
  }

  updateFinishTime() {
    if (this.willFinishAt) {
      const finishTime = new Date(this.willFinishAt);
      let finish_time_element = document.getElementById('finish-time');
      if (finish_time_element) {
        finish_time_element.textContent = this.formatLocalDateTime(finishTime);
      }
    }
  }

  updateCycles(cycles) {
    let totalDuration = cycles.reduce((sum, cycle) => sum + cycle.duration, 0);
    const currentTime = new Date();
    const finishTime = new Date(currentTime.getTime() + totalDuration * 1000);
    this.willFinishAt = finishTime.toISOString();
    this.updateFinishTime();
  }

  updateZenMode() {
    const zenRemainingTime = document.getElementById('zen-remaining-time');
    const zenCurrentCycle = document.getElementById('zen-current-cycle');
    const remainingTime = document.getElementById('remaining-time');
    const currentCycle = document.getElementById('current-cycle');

    if (zenRemainingTime && remainingTime) {
      zenRemainingTime.textContent = remainingTime.textContent;
    }
    if (zenCurrentCycle && currentCycle) {
      zenCurrentCycle.textContent = currentCycle.textContent;
    }
  }

  updateZenModeToggleIcon(isRunning) {
    const zenTimerToggleIcon = document.getElementById('zen-timer-toggle-icon');
    if (zenTimerToggleIcon) {
      zenTimerToggleIcon.className = isRunning ? "fas fa-pause" : "fas fa-play";
    }
  }

}

// Initialize the FocusSessionManager when the page loads
let focusSessionManager;
document.addEventListener("DOMContentLoaded", (event) => {
  const sessionId = document.getElementById("session-id").dataset.sessionId;
  const username = document.getElementById("username").dataset.username;
  const debug = document.getElementById("debug-mode").dataset.debug === 'true';
  if (username) {
    focusSessionManager = new FocusSessionManager(sessionId, username, debug);
  }

  // *****************************************
  // ********** Timer Syncing **********
  // *****************************************

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
      const currentTime = Date.now();
      // Convert to seconds
      const timeSinceLastSync = (currentTime - focusSessionManager.lastSyncTime) / 1000;
      if (timeSinceLastSync > 300) { // 300 seconds = 5 minutes
        console.log("Time since last sync:", timeSinceLastSync, "seconds. Syncing inactive timer.");
        focusSessionManager.sync_timer();
      }
    }
  });

  const focusCyclesTable = document.getElementById('focus-cycles-list');
  if (focusCyclesTable) {
    focusCyclesTable.addEventListener('change', function (e) {
      if (e.target.name === 'focus_cycle_duration') {
        const cycles = Array.from(focusCyclesTable.children).map(cycle => ({
          duration: parseInt(cycle.querySelector('input[name="focus_cycle_duration"]').value, 10) * 60 // Convert to seconds
        }));
        focusSessionManager.updateCycles(cycles);
      }
    });
  }

  const taskToggle = document.getElementById('taskToggle');
  const taskPopup = document.getElementById('taskPopup');
  const closeTaskPopup = document.getElementById('closeTaskPopup');

  if (taskToggle && taskPopup && closeTaskPopup) {
    taskToggle.addEventListener('click', function() {
      taskPopup.classList.remove('hidden');
    });

    closeTaskPopup.addEventListener('click', function() {
      taskPopup.classList.add('hidden');
    });

    // Close popup when clicking outside
    taskPopup.addEventListener('click', function(e) {
      if (e.target === taskPopup) {
        taskPopup.classList.add('hidden');
      }
    });
  }

});


// share link functionality
document.addEventListener('DOMContentLoaded', function () {
  const shareSessionBtn = document.getElementById('shareSessionBtn');
  const shareSessionFeedback = document.getElementById('shareSessionFeedback');

  if (shareSessionBtn) {
    shareSessionBtn.addEventListener('click', function () {
      const currentUrl = window.location.href;

      navigator.clipboard.writeText(currentUrl).then(function () {
        // Success feedback
        shareSessionFeedback.textContent = 'Session link copied to clipboard!';
        shareSessionFeedback.classList.remove('opacity-0');
        shareSessionBtn.classList.add('bg-green-600', 'hover:bg-green-700');
        shareSessionBtn.classList.remove('bg-purple-600', 'hover:bg-purple-700');
        shareSessionBtn.innerHTML = '<i class="fas fa-check mr-2"></i> Copied!';

        // Reset button after 3 seconds
        setTimeout(function () {
          shareSessionFeedback.classList.add('opacity-0');
          shareSessionBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
          shareSessionBtn.classList.add('bg-purple-600', 'hover:bg-purple-700');
          shareSessionBtn.innerHTML = '<i class="fas fa-share-alt mr-2"></i> Share Session';
        }, 3000);
      }, function () {
        // Error feedback
        shareSessionFeedback.textContent = 'Failed to copy. Please try again.';
        shareSessionFeedback.classList.remove('opacity-0');
        shareSessionFeedback.classList.add('text-red-500');

        // Reset feedback after 3 seconds
        setTimeout(function () {
          shareSessionFeedback.classList.add('opacity-0');
          shareSessionFeedback.classList.remove('text-red-500');
        }, 3000);
      });
    });
  }
});

// Add this function to generate a simple avatar based on username
function generateAvatar(username) {
  const canvas = document.createElement('canvas');
  canvas.width = 40;
  canvas.height = 40;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = `hsl(${username.charCodeAt(0) * 10}, 70%, 50%)`;
  ctx.fillRect(0, 0, 40, 40);
  ctx.fillStyle = 'white';
  ctx.font = 'bold 20px Arial';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(username.charAt(0).toUpperCase(), 20, 20);
  return canvas.toDataURL();
}

// Update the toggleList function
window.toggleList = function(listType) {
  const content = document.getElementById(`${listType}-wrapper`) || document.getElementById(`session-followers-container`);
  const toggle = document.querySelector(`.${listType}-toggle`);
  content.classList.toggle('expanded');
  toggle.classList.toggle('expanded');

  localStorage.setItem(`${listType}-expanded`, content.classList.contains('expanded'));

  if (listType === 'focus-cycles') {
    applyFocusCyclesVisibility();
  } else {
    applyFollowersVisibility();
  }
}

// Update the applyFollowersVisibility function
function applyFollowersVisibility() {
  const followersContent = document.getElementById('session-followers-container');
  const isExpanded = localStorage.getItem('followers-expanded') === 'true';

  if (followersContent) {
    if (isExpanded) {
      followersContent.style.maxHeight = '500px';
      followersContent.style.overflow = 'auto';
      followersContent.classList.add('expanded');
    } else {
      followersContent.style.maxHeight = '0';
      followersContent.style.overflow = 'hidden';
      followersContent.classList.remove('expanded');
    }
  }
}

// Call applyFollowersVisibility on page load
document.addEventListener('DOMContentLoaded', function() {
  applyFollowersVisibility();
});
