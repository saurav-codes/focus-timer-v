// static/js/focus_session.js
class FocusSessionManager {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.socket = new WebSocket(
            `ws://${window.location.host}/ws/focus_session/${sessionId}/`
        );
        this.socket.onmessage = (e) => this.handleMessage(JSON.parse(e.data));
    }

    handleMessage(data) {
        if (data.type === 'timer_update') {
            this.updateTimerDisplay(data.elapsed_time);
        } else if (data.type === 'task_created') {
            this.addTaskToList(data.task);
        } else if (data.type === 'task_updated') {
            this.updateTaskInList(data.task);
        }
    }

    updateTimerDisplay(elapsedTime) {
        const timerElement = document.getElementById('timer');
        timerElement.textContent = this.formatTime(elapsedTime);
    }

    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainingSeconds = seconds % 60;
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    addTaskToList(task) {
        const taskList = document.getElementById('task-list');
        const taskItem = document.createElement('li');
        taskItem.id = `task-${task.id}`;
        taskItem.innerHTML = `
            ${task.description}
            <button onclick="focusSessionManager.toggleTask(${task.id})">
                ${task.is_completed ? 'Undo' : 'Complete'}
            </button>
        `;
        taskList.appendChild(taskItem);
    }

    updateTaskInList(task) {
        const taskItem = document.getElementById(`task-${task.id}`);
        if (taskItem) {
            taskItem.innerHTML = `
                ${task.description}
                <button onclick="focusSessionManager.toggleTask(${task.id})">
                    ${task.is_completed ? 'Undo' : 'Complete'}
                </button>
            `;
        }
    }

    startTimer() {
        this.socket.send(JSON.stringify({action: 'start_timer'}));
    }

    pauseTimer() {
        this.socket.send(JSON.stringify({action: 'pause_timer'}));
    }

    stopTimer() {
        this.socket.send(JSON.stringify({action: 'stop_timer'}));
    }

    createTask(description) {
        this.socket.send(JSON.stringify({action: 'create_task', description: description}));
    }

    toggleTask(taskId) {
        this.socket.send(JSON.stringify({action: 'toggle_task', task_id: taskId}));
    }
}

// Initialize the FocusSessionManager when the page loads
let focusSessionManager;
document.addEventListener('DOMContentLoaded', (event) => {
    const sessionId = document.getElementById('session-id').dataset.sessionId;
    focusSessionManager = new FocusSessionManager(sessionId);
});
