(function() {
  const QUICK_ACTIONS = [
    { label: '📦 Low stock',     msg: 'Which medicines are low on stock right now?' },
    { label: '🧾 New bill',      msg: 'How do I create a new bill?' },
    { label: '⚠️ Expiry check', msg: 'Are there any medicines expiring soon?' },
    { label: '👤 Customer info', msg: 'How do I look up a customer balance?' },
    { label: '📊 Today stats',   msg: 'Give me a summary of pharmacy stats.' }
  ];

  let state = {
    isOpen: false,
    history: [],
    contextFetched: false,
    isWaiting: false
  };

  function init() {
    // Inject DOM
    const container = document.createElement('div');
    container.innerHTML = `
      <div id="mv-chat-bubble">
        <i class="fas fa-comment-dots"></i>
      </div>
      <div id="mv-chat-window">
        <div class="mv-cw-header">
          <div class="mv-cw-header-avatar"><i class="fas fa-robot"></i></div>
          <div class="mv-cw-header-title">
            <h4>Medi Vision AI</h4>
            <span>● Online</span>
          </div>
          <i class="fas fa-xmark mv-cw-close" id="mv-cw-close"></i>
        </div>
        <div class="mv-stats-bar" id="mv-stats-bar">
          <div class="mv-stat-col"><div class="mv-stat-val" id="stat-meds">-</div><div class="mv-stat-lbl">Meds</div></div>
          <div class="mv-stat-col"><div class="mv-stat-val" id="stat-low">-</div><div class="mv-stat-lbl">Low Stock</div></div>
          <div class="mv-stat-col"><div class="mv-stat-val" id="stat-bills">-</div><div class="mv-stat-lbl">Bills</div></div>
          <div class="mv-stat-col"><div class="mv-stat-val" id="stat-rev">-</div><div class="mv-stat-lbl">Revenue</div></div>
        </div>
        <div class="mv-messages" id="mv-messages">
          <div class="mv-bubble bot">Hi! I'm your Medi Vision AI assistant. I have live access to the pharmacy database. How can I help you today?</div>
        </div>
        <div class="mv-quick-actions" id="mv-quick-actions"></div>
        <div class="mv-input-area">
          <input type="text" id="mv-chat-input" placeholder="Type a message..." autocomplete="off"/>
          <button class="mv-send-btn" id="mv-chat-send"><i class="fas fa-paper-plane"></i></button>
        </div>
      </div>
    `;
    document.body.appendChild(container);

    // Bind Quick Actions
    const quickArea = document.getElementById('mv-quick-actions');
    QUICK_ACTIONS.forEach(action => {
      const btn = document.createElement('button');
      btn.className = 'mv-quick';
      btn.textContent = action.label;
      btn.onclick = () => sendMessage(action.msg);
      quickArea.appendChild(btn);
    });

    // Bind Events
    document.getElementById('mv-chat-bubble').addEventListener('click', toggleChat);
    document.getElementById('mv-cw-close').addEventListener('click', toggleChat);
    
    const input = document.getElementById('mv-chat-input');
    const sendBtn = document.getElementById('mv-chat-send');
    
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !state.isWaiting) sendMessage(input.value);
    });
    
    sendBtn.addEventListener('click', () => {
      if (!state.isWaiting) sendMessage(input.value);
    });
  }

  function toggleChat() {
    state.isOpen = !state.isOpen;
    const win = document.getElementById('mv-chat-window');
    
    if (state.isOpen) {
      win.classList.add('mv-open');
      document.getElementById('mv-chat-input').focus();
      if (!state.contextFetched) fetchContext();
    } else {
      win.classList.remove('mv-open');
    }
  }

  async function fetchContext() {
    try {
      const res = await fetch('/api/chat/context');
      if (res.ok) {
        const data = await res.json();
        updateStats(data.total_medicines, data.low_stock_items?.length, data.total_bills, data.total_revenue);
        state.contextFetched = true;
      }
    } catch (err) {
      console.error('Failed to fetch chat context', err);
    }
  }

  function updateStats(meds, low, bills, rev) {
    document.getElementById('stat-meds').textContent = meds !== undefined ? meds : '-';
    document.getElementById('stat-low').textContent = low !== undefined ? low : '-';
    document.getElementById('stat-bills').textContent = bills !== undefined ? bills : '-';
    document.getElementById('stat-rev').textContent = rev !== undefined ? '₹' + Math.floor(rev) : '-';
  }

  function formatText(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  function appendMessage(role, text) {
    const msgArea = document.getElementById('mv-messages');
    const bubble = document.createElement('div');
    bubble.className = `mv-bubble ${role}`;
    
    if (role === 'bot') {
      bubble.innerHTML = formatText(text);
    } else {
      bubble.textContent = text;
    }
    
    msgArea.appendChild(bubble);
    msgArea.scrollTop = msgArea.scrollHeight;
  }

  function showTyping() {
    const msgArea = document.getElementById('mv-messages');
    const bubble = document.createElement('div');
    bubble.className = 'mv-bubble bot mv-typing-bubble';
    bubble.id = 'mv-typing-indicator';
    bubble.innerHTML = `<div class="mv-typing"><div class="mv-dot"></div><div class="mv-dot"></div><div class="mv-dot"></div></div>`;
    msgArea.appendChild(bubble);
    msgArea.scrollTop = msgArea.scrollHeight;
  }

  function removeTyping() {
    const typing = document.getElementById('mv-typing-indicator');
    if (typing) typing.remove();
  }

  async function sendMessage(text) {
    text = text.trim();
    if (!text) return;

    const input = document.getElementById('mv-chat-input');
    input.value = '';
    
    appendMessage('user', text);
    state.history.push({ role: 'user', content: text });
    
    // Hide quick actions after first message
    document.getElementById('mv-quick-actions').style.display = 'none';
    
    state.isWaiting = true;
    showTyping();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: state.history.slice(-14)
        })
      });
      
      removeTyping();
      
      if (res.ok) {
        const data = await res.json();
        appendMessage('bot', data.reply);
        state.history.push({ role: 'model', content: data.reply });
        
        if (data.live_data_snapshot) {
           updateStats(
             data.live_data_snapshot.medicines,
             data.live_data_snapshot.low_stock_count,
             data.live_data_snapshot.total_bills,
             data.live_data_snapshot.total_revenue
           );
        }
      } else {
        appendMessage('bot', 'Sorry, I encountered an error. Please try again.');
      }
    } catch (err) {
      removeTyping();
      appendMessage('bot', 'Network error. Please check your connection.');
    } finally {
      state.isWaiting = false;
      input.focus();
    }
  }

  window._mvChat = { toggle: toggleChat };

  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
