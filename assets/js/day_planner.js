document.addEventListener('DOMContentLoaded', function () {
    // Re-initialize after HTMX content swap
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        if (evt.detail.target.id === 'schedule-response') {
            initializeSchedule();
            console.log("Schedule re-initialized");
        }
    });
});

let all_listeners = [];

function addListener(element, event_type, callback, human_readable_name) {
    element.addEventListener(event_type, callback);
    all_listeners.push({ element, event_type, callback, human_readable_name });
}

function cleanupAllListeners() {
    all_listeners.forEach(listener => {
        let element = listener.element;
        const human_readable_name = listener.human_readable_name;
        if (element) {
            element.removeEventListener(listener.event_type, listener.callback);
            console.log("Listener removed from ", human_readable_name);
        }
    });
    all_listeners = [];
}

function removeTaskElement(event) {
    console.log("Removing task element");
    console.log(event.target);
    const remove_btn_element = event.target;
    const closest_schedule_item = remove_btn_element.closest('.schedule-item');
    closest_schedule_item.remove();
}

function addNewTaskElement(event) {
    const add_btn_element = event.target;
    const newItem = `
        <div class="relative p-2 rounded-lg schedule-item group cursor-move hover:bg-gray-50">
            <div class="flex items-start space-x-4">
                <!-- Drag Handle -->
                <div class="flex-shrink-0 w-6 flex items-center justify-center text-gray-400">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 6a2 2 0 1 0-4 0 2 2 0 0 0 4 0zM8 12a2 2 0 1 0-4 0 2 2 0 0 0 4 0zM8 18a2 2 0 1 0-4 0 2 2 0 0 0 4 0zM20 6a2 2 0 1 0-4 0 2 2 0 0 0 4 0zM20 12a2 2 0 1 0-4 0 2 2 0 0 0 4 0zM20 18a2 2 0 1 0-4 0 2 2 0 0 0 4 0z" />
                    </svg>
                </div>
                <!-- Time Input -->
                <div class="w-32 flex-shrink-0">
                    <input type="time" 
                           class="text-sm font-medium text-gray-600 border rounded px-2 py-1 time-input w-full" 
                           value="12:00">
                </div>
                
                <!-- Task Input and Action Buttons -->
                <div class="flex-grow">
                    <div class="relative flex items-center">
                        <input type="text"
                               class="text-gray-900 w-full border rounded px-2 py-1 task-input"
                               value="New Task"
                               maxlength="255">
                        
                        <!-- Side Action Buttons -->
                        <div class="flex items-center space-x-2 ml-2">
                            <button class="delete-task-btn text-red-500 hover:text-red-700 p-1 rounded-full">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                            </button>
                            
                            <button title="Save to your Tasks List"
                                    class="add-to-calendar-btn text-green-500 hover:text-green-700 p-1 rounded-full">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Add Task Button -->
            <div class="absolute left-1/2 -bottom-3 transform -translate-x-1/2 opacity-0 transition-opacity duration-200 z-10 group-hover:opacity-100 group-focus-within:opacity-100">
                <button class="add-task-btn inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-500 text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 shadow-lg">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                    </svg>
                </button>
            </div>
        </div>
    `;
    const scheduleItem= add_btn_element.closest('.schedule-item');
    scheduleItem.insertAdjacentHTML('afterend', newItem);
    
    // since we added a new element, we need to re-initialize the listeners
    initializeSchedule();
}

async function addToCalendar(element, task, time) {
    try {
        const response = await fetch('/timetable/tasks-add/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({
                description: task,
                time: time
            })
        });

        const data = await response.json();
        if (response.ok) {
            showToast(`Task scheduled for ${time}`);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('Failed to add task to calendar', 'error');
        console.error('Error adding task:', error);
    }
}

function initializeSchedule() {
    cleanupAllListeners(); // clean all listeners before re-initializing
    const scheduleItems = document.querySelectorAll('.schedule-item');
    const scheduleContainer = document.querySelector('.schedule-items');

    // Initialize Sortable
    if (scheduleContainer) {
        new Sortable(scheduleContainer, {
            animation: 150,
            handle: '.cursor-move',  // Use the cursor-move class as handle
            ghostClass: 'opacity-70',
            dragClass: 'shadow-lg',
            chosenClass: 'bg-gray-50',
            onEnd: function(evt) {
                // Re-initialize listeners after sorting
                initializeSchedule();
            }
        });
    }

    // Add event listeners to each schedule item
    scheduleItems.forEach(item => {
        const timeInput = item.querySelector('.time-input');
        const taskInput = item.querySelector('.task-input');
        const addToCalendarBtn = item.querySelector('.add-to-calendar-btn');
        const deleteTaskBtn = item.querySelector('.delete-task-btn');
        const addTaskBtn = item.querySelector('.add-task-btn');
        console.log("add task element is ", addTaskBtn);

        // Add to calendar button handler
        addListener(addToCalendarBtn, 'click', async (event) => {
            addToCalendar(event.target, taskInput.value, timeInput.value);
        }, human_readable_name = 'Add to calendar');

        // Time input validation
        addListener(timeInput, 'change', function () {
            if (!this.value) {
                this.value = '12:00';
                showToast('Please select a valid time', 'error');
            }
        }, human_readable_name = 'Time input validation');

        // Character limit validation
        addListener(taskInput, 'input', function () {
            if (this.value.length > 255) {
                this.value = this.value.substring(0, 255);
                showToast('Task description cannot exceed 255 characters', 'error');
            }
        }, human_readable_name = 'Character limit validation');

        // Delete task button handler
        addListener(deleteTaskBtn, 'click', removeTaskElement, human_readable_name = 'Delete task');

        // Add new task button handler
        addListener(addTaskBtn, 'click', addNewTaskElement, human_readable_name = 'Add new task');
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

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg transform transition-transform duration-300 z-50 ${type === 'success' ? 'bg-green-500' : 'bg-red-500'
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