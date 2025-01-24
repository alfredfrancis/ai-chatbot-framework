(() => {
  const styles = `
    .iky-chat-widget {
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 1000;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    }

    .iky-chat-button {
      width: 60px;
      height: 60px;
      border-radius: 30px;
      background-color: #22c55e;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s;
    }

    .iky-chat-button:hover {
      transform: scale(1.05);
    }

    .iky-chat-button svg {
      width: 28px;
      height: 28px;
      fill: white;
    }

    .iky-chat-window {
      position: fixed;
      bottom: 90px;
      right: 20px;
      width: 380px;
      height: 600px;
      background: white;
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      transition: all 0.3s;
      opacity: 0;
      transform: translateY(20px);
      pointer-events: none;
    }

    .iky-chat-window.open {
      opacity: 1;
      transform: translateY(0);
      pointer-events: all;
    }

    .iky-chat-header {
      padding: 20px;
      background: #22c55e;
      color: white;
    }

    .iky-chat-title {
      font-size: 18px;
      font-weight: 600;
      margin: 0;
    }

    .iky-chat-subtitle {
      font-size: 14px;
      opacity: 0.8;
      margin: 4px 0 0;
    }

    .iky-chat-messages {
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .iky-message {
      max-width: 80%;
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.4;
      animation: messageSlideIn 0.3s ease;
    }

    .iky-message.bot {
      background: #f3f4f6;
      border-bottom-left-radius: 4px;
      align-self: flex-start;
    }

    .iky-message.user {
      background: #22c55e;
      color: white;
      border-bottom-right-radius: 4px;
      align-self: flex-end;
    }

    .iky-chat-input {
      padding: 20px;
      border-top: 1px solid #e5e7eb;
      background: white;
    }

    .iky-input-form {
      display: flex;
      gap: 8px;
    }

    .iky-input-field {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid #e5e7eb;
      border-radius: 24px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }

    .iky-input-field:focus {
      border-color: #22c55e;
    }

    .iky-send-button {
      width: 40px;
      height: 40px;
      border-radius: 20px;
      background: #22c55e;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background-color 0.2s;
    }

    .iky-send-button:hover {
      background: #16a34a;
    }

    .iky-send-button svg {
      width: 20px;
      height: 20px;
      fill: white;
    }

    .iky-typing {
      display: flex;
      gap: 4px;
      padding: 12px 16px;
      background: #f3f4f6;
      border-radius: 16px;
      border-bottom-left-radius: 4px;
      align-self: flex-start;
      max-width: 80%;
    }

    .iky-typing-dot {
      width: 8px;
      height: 8px;
      background: #9ca3af;
      border-radius: 4px;
      animation: typingBounce 0.5s infinite;
    }

    .iky-typing-dot:nth-child(2) { animation-delay: 0.1s; }
    .iky-typing-dot:nth-child(3) { animation-delay: 0.2s; }

    @keyframes messageSlideIn {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @keyframes typingBounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-4px); }
    }

    @media (max-width: 480px) {
      .iky-chat-window {
        width: calc(100vw - 40px);
        height: calc(100vh - 120px);
      }
    }
  `;

  class ChatWidget {
    constructor() {
      this.isOpen = false;
      this.isTyping = false;
      this.currentState = {
        thread_id: this.uuid(),
        text: "/init_conversation",
        context: {},
      };
      this.response = [];
      this.createElements();
      this.attachEventListeners();
      this.initChat();
    }

    createElements() {
      // Add styles
      const styleSheet = document.createElement('style');
      styleSheet.textContent = styles;
      document.head.appendChild(styleSheet);

      // Create widget container
      this.container = document.createElement('div');
      this.container.className = 'iky-chat-widget';

      // Create chat button
      this.button = document.createElement('div');
      this.button.className = 'iky-chat-button';
      this.button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>';

      // Create chat window
      this.window = document.createElement('div');
      this.window.className = 'iky-chat-window';
      this.window.innerHTML = `
        <div class="iky-chat-header">
          <h2 class="iky-chat-title">Chat with us</h2>
          <p class="iky-chat-subtitle">You are talking to an AI chatbot</p>
        </div>
        <div class="iky-chat-messages"></div>
        <div class="iky-chat-input">
          <form class="iky-input-form">
            <input type="text" class="iky-input-field" placeholder="Type your message...">
            <button type="submit" class="iky-send-button">
              <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            </button>
          </form>
        </div>
      `;

      // Append elements
      this.container.appendChild(this.window);
      this.container.appendChild(this.button);
      document.body.appendChild(this.container);

      // Store references to elements
      this.messages = this.window.querySelector('.iky-chat-messages');
      this.form = this.window.querySelector('.iky-input-form');
      this.input = this.window.querySelector('.iky-input-field');
    }

    attachEventListeners() {
      // Toggle chat window
      this.button.addEventListener('click', () => this.toggleChat());

      // Handle form submission
      this.form.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = this.input.value.trim();
        if (message) {
          this.sendMessage(message);
          this.input.value = '';
        }
      });
    }

    toggleChat() {
      this.isOpen = !this.isOpen;
      this.window.classList.toggle('open', this.isOpen);
      if (this.isOpen) {
        this.input.focus();
      }
    }

    addMessage(content, isUser = false) {
      const message = document.createElement('div');
      message.className = `iky-message ${isUser ? 'user' : 'bot'}`;
      message.innerHTML = content; // Changed from textContent to innerHTML to render HTML content
      this.messages.appendChild(message);
      this.scrollToBottom();
    }

    showTyping() {
      if (this.isTyping) return;
      this.isTyping = true;

      const typing = document.createElement('div');
      typing.className = 'iky-typing';
      typing.innerHTML = `
        <div class="iky-typing-dot"></div>
        <div class="iky-typing-dot"></div>
        <div class="iky-typing-dot"></div>
      `;
      this.messages.appendChild(typing);
      this.scrollToBottom();
    }

    hideTyping() {
      this.isTyping = false;
      const typing = this.messages.querySelector('.iky-typing');
      if (typing) {
        typing.remove();
      }
    }

    scrollToBottom() {
      this.messages.scrollTop = this.messages.scrollHeight;
    }

    uuid() {
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
          var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
          return v.toString(16);
      });
    }

    async initChat() {
      try {
        const response = await fetch(`${window.iky_base_url}/bots/channels/rest/webbook`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(this.currentState),
        });

        const data = await response.json();
        this.response = { ...data };

        // Add bot response(s)
        if (Array.isArray(data)) {
          data.forEach((response, index) => {
            setTimeout(() => {
              this.addMessage(response.text);
            }, index * 500);
          });
        } else if (data) {
          this.addMessage(data.text);
        }
      } catch (error) {
        console.error('Error initializing chat:', error);
        this.addMessage('Sorry, I had trouble starting up. Please try refreshing the page.');
      }
    }

    async sendMessage(message) {
      // Add user message
      this.addMessage(message, true);

      // Show typing indicator
      this.showTyping();

      try {
        const response = await fetch(`${window.iky_base_url}/bots/channels/rest/webbook`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            ...this.currentState,
            text: message
          }),
        });

        const data = await response.json();
        this.response = { ...data };

        // Hide typing indicator
        this.hideTyping();

        // Add bot response(s)
        if (Array.isArray(data)) {
          data.forEach((response, index) => {
            setTimeout(() => {
              this.addMessage(response.text);
            }, index * 500);
          });
        } else if (data) {
          this.addMessage(data.text);
        }
      } catch (error) {
        console.error('Error sending message:', error);
        this.hideTyping();
        this.addMessage('Sorry, something went wrong. Please try again later.');
      }
    }
  }

  // Initialize widget
  window.addEventListener('load', () => {
    new ChatWidget();
  });
})();