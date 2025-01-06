
document.addEventListener('DOMContentLoaded', function () {
    // Re-initialize after HTMX content swap
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        if (evt.detail.target.id === 'schedule-response') {
            cleanupListeners();
            initializeSchedule();
            console.log("Schedule re-initialized");
        }
    });
});

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg transform transition-transform duration-300 z-50 ${
        type === 'success' ? 'bg-green-500' : 'bg-red-500'
    } text-white`;
    toast.innerHTML = `
        <div class="flex items-center space-x-2">
            <span>${message}</span>
            <button class="ml-4 hover:text-gray-200" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    document.body.appendChild(toast);
    
    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.style.transform = 'translateX(150%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function initializeSchedule() {
    const scheduleItems = document.querySelectorAll('.schedule-item');
    const addTaskBtn = document.getElementById('add-task-btn');

    // Add event listeners to each schedule item
    scheduleItems.forEach(item => {
        const timeInput = item.querySelector('.time-input');
        const taskInput = item.querySelector('.task-input');
        const addToCalendarBtn = item.querySelector('.add-to-calendar-btn');

        // Add to calendar button handler
        addListener(addToCalendarBtn, 'click', async () => {
            try {
                const response = await fetch('/timetable/tasks-add/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify({
                        description: taskInput.value,
                        time: timeInput.value
                    })
                });
                
                const data = await response.json();
                if (response.ok) {
                    showToast(`Task scheduled for ${timeInput.value}`);
                } else {
                    showToast(data.message, 'error');
                }
            } catch (error) {
                showToast('Failed to add task to calendar', 'error');
                console.error('Error adding task:', error);
            }
        });

        // Time input validation
        addListener(timeInput, 'change', function() {
            if (!this.value) {
                this.value = '12:00';
                showToast('Please select a valid time', 'error');
            }
        });

        // Character limit validation
        addListener(taskInput, 'input', function() {
            if (this.value.length > 255) {
                this.value = this.value.substring(0, 255);
                showToast('Task description cannot exceed 255 characters', 'error');
            }
        });
    });

    // Add new task button handler
    addListener(addTaskBtn, 'click', () => {
        const newItem = `
            <div class="flex items-start space-x-4 p-2 rounded-lg schedule-item group">
                <div class="w-32">
                    <input type="time" 
                           class="text-sm font-medium text-gray-600 border rounded px-2 py-1 time-input" 
                           value="12:00">
                </div>
                <div class="flex-grow flex items-start space-x-2 relative">
                    <input type="text"
                           class="text-gray-900 w-full border rounded px-2 py-1 task-input"
                           value="New Task"
                           maxlength="255">
                    <button class="add-to-calendar-btn absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-green-500 text-white px-2 py-1 rounded-md flex items-center space-x-1">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        <span class="text-sm">Add</span>
                    </button>
                </div>
            </div>
        `;
        
        document.getElementById('schedule-items').insertAdjacentHTML('beforeend', newItem);
        cleanupListeners();
        initializeSchedule();
    });
}

// Initialize Select2
$('.select2-multi').select2({
    placeholder: 'Select techniques...',
    allowClear: true,
    closeOnSelect: false,
    width: '100%'
});

// Ctrl + Enter to submit form feature
document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('#schedule-form');
    const textarea = document.querySelector('#thoughts');
    if (textarea && form) {
        textarea.addEventListener('keydown', function (e) {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                form.submit();
            }
        });
    }
});
