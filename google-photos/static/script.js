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

/* Chatbot */
const sendBtn = document.getElementById('send-btn');
const userInput = document.getElementById('user-input');
const chatWindow = document.querySelector('.chat-window');

function sendMessage() {
    const userMessage = userInput.value.trim();
    if (userMessage && chatWindow) {
        const userMessageDiv = document.createElement('div');
        userMessageDiv.classList.add('chat-message', 'user-message');
        userMessageDiv.innerHTML = `<p>${userMessage}</p>`;
        chatWindow.appendChild(userMessageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        userInput.value = '';

        fetch('/api/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: userMessage }),
        })
        .then(response => response.json())
        .then(data => {
            const botMessage = data.response;
            const botMessageDiv = document.createElement('div');
            botMessageDiv.classList.add('chat-message', 'bot-message');
            botMessageDiv.innerHTML = `<p>${botMessage}</p>`;
            chatWindow.appendChild(botMessageDiv);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        })
        .catch((error) => {
            console.error('Error:', error);
            const errorMessageDiv = document.createElement('div');
            errorMessageDiv.classList.add('chat-message', 'bot-message');
            errorMessageDiv.innerHTML = `<p>Sorry, I encountered an error. Please try again.</p>`;
            chatWindow.appendChild(errorMessageDiv);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        });
    }
}

if (sendBtn) {
    sendBtn.addEventListener('click', sendMessage);
}

if (userInput) {
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            sendMessage();
        }
    });
}

/* Page Load and Nav Link Logic */
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
});