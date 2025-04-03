// DOM elements
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const chatMessages = document.getElementById('chat-messages');
const loadingIndicator = document.getElementById('loading-indicator');
const newChatButton = document.getElementById('new-chat');
const chatHistoryList = document.getElementById('chat-history-list');

// Message history
let messageHistory = [];
let chatSessions = [];
let currentSessionId = Date.now();

// Initialize the chat interface
function initChat() {
    // Add event listener for form submission
    if (userInput) {
    userInput.addEventListener('keydown', function(event) {
        // Check if Enter was pressed without Shift key (Shift+Enter will allow for line breaks)
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevent default behavior (new line)
            chatForm.dispatchEvent(new Event('submit')); // Trigger form submission
        }
    });
}

    if (chatForm) {
        chatForm.addEventListener('submit', handleChatSubmit);
    }

    // Add event listener for new chat button
    if (newChatButton) {
        newChatButton.addEventListener('click', startNewChat);
    }

    // Auto-resize textarea
    if (userInput) {
        userInput.addEventListener('input', autoResizeTextarea);
    }

    // Load chat sessions from local storage
    loadChatSessions();

    // Display welcome message in new chat
    if (chatMessages.children.length === 0) {
        displayMessage({
            role: 'assistant',
            content: 'Hello! I am Misteral, what would you like to know including your AWS costs?'
        });
    }
}

// Load chat sessions from local storage
function loadChatSessions() {
    try {
        const savedSessions = localStorage.getItem('awsCostChatSessions');
        if (savedSessions) {
            chatSessions = JSON.parse(savedSessions);
            renderChatHistory();
        }
    } catch (e) {
        console.error('Error loading chat sessions:', e);
    }
}

// Save chat sessions to local storage
function saveChatSessions() {
    try {
        localStorage.setItem('awsCostChatSessions', JSON.stringify(chatSessions));
    } catch (e) {
        console.error('Error saving chat sessions:', e);
    }
}

// Render chat history in sidebar
function renderChatHistory() {
    if (!chatHistoryList) return;

    chatHistoryList.innerHTML = '';

    chatSessions.forEach(session => {
        const historyItem = document.createElement('div');
        historyItem.className = 'chat-history-item';
        if (session.id === currentSessionId) {
            historyItem.classList.add('active');
        }

        // Use first message as title or default title
        const title = session.title || 'New Conversation';

        historyItem.innerHTML = `
            <i class="fas fa-comment"></i>
            <span>${title}</span>
        `;

        historyItem.addEventListener('click', () => loadChatSession(session.id));
        chatHistoryList.appendChild(historyItem);
    });
}

// Start a new chat session
function startNewChat() {
    // Save current session if it has messages
    saveCurrentSession();

    // Clear messages and create new session
    chatMessages.innerHTML = '';
    messageHistory = [];
    currentSessionId = Date.now();

    // Display welcome message
    displayMessage({
        role: 'assistant',
        content: 'Hello! I am Misteral, what would you like to know including your AWS costs?'
    });

    // Update history
    renderChatHistory();
}

// Save current chat session
function saveCurrentSession() {
    if (messageHistory.length > 0) {
        // Find if session already exists
        const existingSessionIndex = chatSessions.findIndex(s => s.id === currentSessionId);

        // Get title from first user message
        const firstUserMessage = messageHistory.find(m => m.role === 'user');
        const title = firstUserMessage ?
            (firstUserMessage.content.length > 30 ?
                firstUserMessage.content.substring(0, 30) + '...' :
                firstUserMessage.content) :
            'New Conversation';

        if (existingSessionIndex >= 0) {
            // Update existing session
            chatSessions[existingSessionIndex].messages = messageHistory;
            chatSessions[existingSessionIndex].title = title;
        } else {
            // Create new session
            chatSessions.unshift({
                id: currentSessionId,
                title: title,
                messages: messageHistory,
                timestamp: Date.now()
            });
        }

        // Keep only last 10 sessions
        if (chatSessions.length > 10) {
            chatSessions = chatSessions.slice(0, 10);
        }

        // Save to local storage
        saveChatSessions();
    }
}

// Load a chat session
function loadChatSession(sessionId) {
    // Save current session
    saveCurrentSession();

    // Find session
    const session = chatSessions.find(s => s.id === sessionId);
    if (session) {
        // Load session
        currentSessionId = sessionId;
        messageHistory = [...session.messages];

        // Render messages
        chatMessages.innerHTML = '';
        messageHistory.forEach(message => {
            displayMessage(message);
        });

        // Update history
        renderChatHistory();
    }
}

// Handle chat form submission
async function handleChatSubmit(event) {
    event.preventDefault();

    const message = userInput.value.trim();
    if (!message) return;

    // Display user message
    displayMessage({
        role: 'user',
        content: message
    });

    // Reset textarea height
    userInput.style.height = 'auto';

    // Clear input field
    userInput.value = '';

    // Add user message to history
    messageHistory.push({
        role: 'user',
        content: message
    });

    // Show loading indicator
    showLoading(true);

    try {
        console.log('Sending request to /api/chat...');
        // Send message to backend
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                messages: messageHistory
            })
        });

        console.log('Response status:', response.status);
        console.log('Response headers:', Object.fromEntries(response.headers.entries()));

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error response:', errorText);
            throw new Error(`HTTP error: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        console.log('Response data:', data);

        // Add assistant response to history
        if (data.message) {
            messageHistory.push(data.message);
            displayMessage(data.message);

            // Save session after receiving response
            saveCurrentSession();
        } else if (data.error) {
            displayError(data.error);
        }
    } catch (error) {
        console.error('Error details:', error);
        displayError(`Failed to communicate with the server: ${error.message}`);
    } finally {
        // Hide loading indicator
        showLoading(false);
    }
}

// Auto-resize textarea as user types
function autoResizeTextarea() {
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';

    // Limit max height
    if (parseInt(userInput.style.height) > 200) {
        userInput.style.height = '200px';
    }
}

// Display a message in the chat interface
function displayMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${message.role}`;

    // Create message content container
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';

    // Parse Markdown content if it's from the assistant
    if (message.role === 'assistant') {
        contentElement.innerHTML = marked.parse(message.content);
    } else {
        // For user messages, we may want to escape HTML and preserve line breaks
        contentElement.textContent = message.content;
    }

    messageElement.appendChild(contentElement);
    chatMessages.appendChild(messageElement);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Display error message
function displayError(errorMessage) {
    const messageElement = document.createElement('div');
    messageElement.className = 'message system';
    messageElement.innerHTML = `
        <div class="message-name">System</div>
        <div class="message-bubble error">
            <p>${escapeHtml(errorMessage)}</p>
        </div>
    `;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Show or hide loading indicator
function showLoading(isLoading) {
    if (loadingIndicator) {
        loadingIndicator.style.display = isLoading ? 'flex' : 'none';
    }
}

// Helper function to escape HTML
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Format code blocks in the message content
function formatCodeBlocks(content) {
    // First, handle multiline code blocks with language specification
    content = content.replace(/```([a-zA-Z0-9]*)\n([\s\S]*?)\n```/g, function(match, language, code) {
        return `<pre>${language ? `<code class="language-${language}">` : '<code>'}${escapeHtml(code)}</code></pre>`;
    });

    // Then handle inline code
    content = content.replace(/`([^`]+)`/g, '<code>$1</code>');

    return content;
}

// Format tables in the message content
function formatTables(content) {
    let inTable = false;
    let tableContent = '';
    let formattedContent = '';

    const lines = content.split('\n');

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
            // This line is part of a table
            if (!inTable) {
                // Start of a new table
                inTable = true;
                tableContent = '';
            }

            // Process table row
            const cells = line.split('|').slice(1, -1);

            if (tableContent === '') {
                // Table header
                tableContent += '<thead><tr>';
                cells.forEach(cell => {
                    tableContent += `<th>${cell.trim()}</th>`;
                });
                tableContent += '</tr></thead><tbody>';
            } else if (line.includes('--') && line.includes('|')) {
                // Separator line, skip it
                continue;
            } else {
                // Table row
                tableContent += '<tr>';
                cells.forEach(cell => {
                    tableContent += `<td>${cell.trim()}</td>`;
                });
                tableContent += '</tr>';
            }
        } else {
            // Not a table line
            if (inTable) {
                // End of table
                inTable = false;
                formattedContent += `<table>${tableContent}</tbody></table>\n`;
                tableContent = '';
            }

            formattedContent += line + '\n';
        }
    }

    // If we ended while still in a table
    if (inTable) {
        formattedContent += `<table>${tableContent}</tbody></table>\n`;
    }

    return formattedContent;
}

// Format lists in the message content
function formatLists(content) {
    // Format unordered lists
    content = content.replace(/^[\s]*[-*] (.+)$/gm, '<li>$1</li>');
    content = content.replace(/(<li>.*<\/li>\n)+/g, '<ul>$&</ul>');

    // Format ordered lists
    content = content.replace(/^[\s]*(\d+)\. (.+)$/gm, '<li>$2</li>');
    content = content.replace(/(<li>.*<\/li>\n)+/g, '<ol>$&</ol>');

    return content;
}

// Format headers in the message content
function formatHeaders(content) {
    content = content.replace(/^#{6} (.+)$/gm, '<h6>$1</h6>');
    content = content.replace(/^#{5} (.+)$/gm, '<h5>$1</h5>');
    content = content.replace(/^#{4} (.+)$/gm, '<h4>$1</h4>');
    content = content.replace(/^#{3} (.+)$/gm, '<h3>$1</h3>');
    content = content.replace(/^#{2} (.+)$/gm, '<h2>$1</h2>');
    content = content.replace(/^#{1} (.+)$/gm, '<h1>$1</h1>');

    return content;
}

// Initialize the chat interface when the page loads
document.addEventListener('DOMContentLoaded', initChat);