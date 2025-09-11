/* Dark Mode Toggle */
const darkModeToggle = document.getElementById('dark-mode-checkbox');
const body = document.body;

const enableDarkMode = () => {
    body.classList.add('dark-mode');
    if(darkModeToggle) darkModeToggle.checked = true;
    localStorage.setItem('darkMode', 'enabled');
}

const disableDarkMode = () => {
    body.classList.remove('dark-mode');
    if(darkModeToggle) darkModeToggle.checked = false;
    localStorage.setItem('darkMode', 'disabled');
}

// Check for saved preference on page load
if (localStorage.getItem('darkMode') === 'enabled') {
    enableDarkMode();
} else if (localStorage.getItem('darkMode') === 'disabled') {
    disableDarkMode();
} else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    enableDarkMode();
}

if (darkModeToggle) {
    darkModeToggle.addEventListener('change', () => {
        if (darkModeToggle.checked) {
            enableDarkMode();
        } else {
            disableDarkMode();
        }
    });
}

/* Photo viewer modal */
const modal = document.getElementById('photo-viewer');

if (modal) { // Check if modal exists on the page
    const modalImg = document.getElementById('full-photo');
    const closeModal = modal.querySelector('.close');

    // Function to open the modal
    const openModal = (src) => {
        modalImg.src = src;
        modal.style.display = 'block';
    };

    // --- For Photos Page ---
    const photoItems = document.querySelectorAll('.photo-item');
    photoItems.forEach(item => {
        item.addEventListener('click', () => {
            const img = item.querySelector('img');
            if (img) {
                openModal(img.src);
            }
        });
    });

    // --- For Memories Page ---
    const memoryPhotoThumbs = document.querySelectorAll('.memory-photo-thumb');
    memoryPhotoThumbs.forEach(thumb => {
        thumb.addEventListener('click', (event) => {
            event.stopPropagation(); // Prevent card click event if any
            openModal(thumb.src);
        });
    });

    // --- Close Modal Logic ---
    if (closeModal) {
        closeModal.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    }

    window.addEventListener('click', (event) => {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    });
}



document.addEventListener("DOMContentLoaded", function() {
    // Hide loader
    const loader = document.querySelector('.loader');
    if (loader) {
        loader.style.display = 'none';
    }

    // Active Nav Link
    const links = document.querySelectorAll('.nav-link');
    const currentPath = window.location.pathname;

    links.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });

    // Chatbot logic
    const chatWindow = document.querySelector('.chat-window');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const collageContainer = document.getElementById('collage-container');

    if (sendBtn) { // Check if the button exists on the page
        sendBtn.addEventListener('click', handleUserMessage);
    }
    if (userInput) {
        userInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                handleUserMessage();
            }
        });
    }

    async function handleUserMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        appendMessage(message, 'user-message');
        userInput.value = '';
        if (collageContainer) {
            collageContainer.innerHTML = ''; // Clear previous collage
        }

        const thinkingIndicator = appendMessage('<i class="fas fa-spinner fa-spin"></i>', 'bot-message thinking');

        try {
            const response = await fetch('/api/chatbot?message=' + encodeURIComponent(message), {
                method: 'GET',
            });

            thinkingIndicator.remove();

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const eventData = JSON.parse(line.substring(6));
                        if (eventData.type === 'thought') {
                            appendMessage(`<i>${eventData.data}</i>`, 'bot-message thought-message');
                        } else if (eventData.type === 'final_response') {
                            handleFinalResponse(eventData.data);
                        } else if (eventData.type === 'error') {
                            appendMessage(`Sorry, I encountered an error: ${eventData.data.message}`, 'bot-message error-message');
                        }
                    }
                }
            }
        } catch (err) {
            console.error("Fetch stream failed:", err);
            thinkingIndicator.remove();
            appendMessage("Sorry, I lost connection with the server.", 'bot-message error-message');
        }
    }

    function handleFinalResponse(data) {
        const gcsUriRegex = /(gs:\/\/[^\s,]+)/;
        const match = data.match(gcsUriRegex);

        if (match) {
            const gcsUri = match[0];
            appendMessage("I've created a collage for you! You can find it at: " + gcsUri, 'bot-message');
        } else {
            appendMessage(data, 'bot-message');
        }
    }

    function appendMessage(content, className) {
        if(!chatWindow) return;
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${className}`;
        const p = document.createElement('p');
        p.innerHTML = content;
        messageDiv.appendChild(p);
        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
        return messageDiv;
    }
});