/* Photo viewer modal */
const modal = document.getElementById('photo-viewer');

if (modal) { // Check if modal exists on the page
    const modalImg = document.getElementById('full-photo');
    const photoItems = document.querySelectorAll('.photo-item img');
    const closeModal = document.querySelector('.close');

    photoItems.forEach(item => {
        item.addEventListener('click', () => {
            modal.style.display = 'block';
            modalImg.src = item.src;
        });
    });

    if (closeModal) {
        closeModal.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    }

    // Also close modal on clicking outside the image
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
        // Display user message
        const userMessageDiv = document.createElement('div');
        userMessageDiv.classList.add('chat-message', 'user-message');
        userMessageDiv.innerHTML = `<p>${userMessage}</p>`;
        chatWindow.appendChild(userMessageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        // Clear input
        userInput.value = '';

        // Send to backend and get response
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