// --- 챗봇 기능 추가 ---
let chatMode = 'QA'; // 'QA' or 'RECOMMEND'

function initChatbot() {
    // 이미 생성되었으면 중단
    if (document.getElementById('chatbotPanel')) return;

    // fe2 챗봇 HTML 구조
    const container = document.createElement('div');
    container.innerHTML = `
<!-- ── 챗봇 플로팅 버튼 ── -->
<button class="chatbot-fab" id="chatbotFab" aria-label="챗봇 열기" title="수강신청 도우미">
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round"
      d="M8 10h.01M12 10h.01M16 10h.01M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2v10z"/>
  </svg>
</button>

<!-- ── 챗봇 패널 ── -->
<div class="chatbot-panel" id="chatbotPanel" role="dialog" aria-label="수강신청 도우미 챗봇">
  <div class="chatbot-header">
    <div class="chatbot-header-avatar">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9m-12 12H5a2 2 0 01-2-2V9m0 0h18"/>
      </svg>
    </div>
    <div class="chatbot-header-info">
      <div class="chatbot-header-title">수강신청 AI 도우미</div>
      <div class="chatbot-header-sub">무강대학교 학사 AI</div>
    </div>
    <button class="chatbot-close-btn" id="chatbotClose" aria-label="닫기">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  </div>

  <div class="chatbot-messages" id="chatbotMessages"></div>

  <div class="chatbot-quick" id="chatbotQuick">
    <button class="quick-btn" data-msg="수강신청 방법이 궁금해요">신청 방법</button>
    <button class="quick-btn" data-mode="recommend" style="border-color:#ff9800; color:#e65100;">🤖 AI 맞춤 과목 추천 (자동 담기)</button>
  </div>

  <div class="chatbot-input-area">
    <textarea class="chatbot-input" id="chatbotInput" placeholder="질문을 입력하세요..." rows="1" maxlength="300"></textarea>
    <button class="chatbot-send-btn" id="chatbotSend" aria-label="전송" disabled>
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 19V5m0 0l-7 7m7-7l7 7"/>
      </svg>
    </button>
  </div>
</div>
    `.trim();

    document.body.appendChild(container.firstElementChild); // fab
    document.body.appendChild(container.lastElementChild);  // panel

    const fab = document.getElementById('chatbotFab');
    const panel = document.getElementById('chatbotPanel');
    const closeBtn = document.getElementById('chatbotClose');
    const messages = document.getElementById('chatbotMessages');
    const input = document.getElementById('chatbotInput');
    const sendBtn = document.getElementById('chatbotSend');
    const quickArea = document.getElementById('chatbotQuick');

    let opened = false;

    // 현재 시간 포맷팅
    function nowTime() {
        const d = new Date();
        const h = String(d.getHours()).padStart(2, '0');
        const m = String(d.getMinutes()).padStart(2, '0');
        return `${h}:${m}`;
    }

    // 채팅 버블 추가 UI
    function appendMsg(role, text, skipAvatar) {
        const wrap = document.createElement('div');
        wrap.className = `chat-msg ${role}`;

        if (role === 'bot' && !skipAvatar) {
            const av = document.createElement('div');
            av.className = 'chat-msg-avatar';
            av.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
            </svg>`;
            wrap.appendChild(av);
        }

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.innerHTML = text.replace(/\n/g, '<br>');
        wrap.appendChild(bubble);

        const time = document.createElement('span');
        time.className = 'chat-time';
        time.textContent = nowTime();
        wrap.appendChild(time);

        messages.appendChild(wrap);
        messages.scrollTop = messages.scrollHeight;
        return wrap;
    }

    // 타이핑(로딩) 인디케이터
    function showTyping() {
        const wrap = document.createElement('div');
        wrap.className = 'chat-msg bot chat-typing';
        wrap.id = 'typingIndicator';

        const av = document.createElement('div');
        av.className = 'chat-msg-avatar';
        av.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
        </svg>`;
        wrap.appendChild(av);

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
        wrap.appendChild(bubble);

        messages.appendChild(wrap);
        messages.scrollTop = messages.scrollHeight;
        return wrap;
    }

    // 실제 전송 로직
    async function handleSend() {
        const text = input.value.trim();
        if (!text) return;

        input.value = '';
        input.style.height = 'auto';
        sendBtn.disabled = true;

        appendMsg('user', text);
        const typing = showTyping();

        try {
            if (chatMode === 'RECOMMEND') {
                // 추천 모드
                const res = await fetch('/api/v1/student/ai/recommend', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: parseInt(userId || 0),
                        preference: text
                    })
                });
                
                typing.remove();
                if (res.ok) {
                    const data = await res.json();
                    appendMsg('bot', `✅ 추천 완료!\n${data.message}\n(장바구니 내역을 확인해주세요)`);
                    if (typeof loadEnrollments === 'function') await loadEnrollments(); // 갱신
                } else {
                    const data = await res.json();
                    appendMsg('bot', `❌ 추천 실패: ${data.detail || '알 수 없는 오류'}`);
                }
                
                // 다시 일반 모드로 복귀
                chatMode = 'QA';
                input.placeholder = "질문을 입력하세요...";
                document.getElementById('chatbotQuick').style.display = 'flex';
                
            } else {
                // 일반 대화 모드
                const res = await fetch('/api/v1/chat/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: parseInt(userId || 0),
                        session_id: `sess_${userId || 'guest'}`,
                        message: text
                    })
                });

                typing.remove();
                if (res.ok) {
                    const data = await res.json();
                    appendMsg('bot', data.reply || '답변이 없습니다.');
                } else {
                    appendMsg('bot', '❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
                }
            }
        } catch (e) {
            console.error(e);
            typing.remove();
            appendMsg('bot', '❌ 서버 연결에 실패했습니다.');
            if (chatMode === 'RECOMMEND') {
                chatMode = 'QA';
                input.placeholder = "질문을 입력하세요...";
                document.getElementById('chatbotQuick').style.display = 'flex';
            }
        }
        
        sendBtn.disabled = input.value.trim().length === 0;
    }

    function openPanel() {
        panel.classList.add('open');
        opened = true;
        fab.setAttribute('aria-label', '챗봇 닫기');
        if (messages.children.length === 0) {
            setTimeout(() => {
                appendMsg('bot', '안녕하세요! 무강대 AI 학사 도우미입니다 👋\n2026학년도 학사 규정이나 수강신청에 대해 무엇이든 물어보세요.');
            }, 300);
        }
        setTimeout(() => input.focus(), 250);
    }

    function closePanel() {
        panel.classList.remove('open');
        opened = false;
        fab.setAttribute('aria-label', '챗봇 열기');
    }

    fab.addEventListener('click', () => opened ? closePanel() : openPanel());
    closeBtn.addEventListener('click', closePanel);

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && opened) closePanel();
    });

    sendBtn.addEventListener('click', handleSend);

    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) handleSend();
        }
    });

    input.addEventListener('input', () => {
        sendBtn.disabled = input.value.trim().length === 0;
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 90) + 'px';
    });

    // 빠른 메뉴 (Quick Buttons)
    quickArea.addEventListener('click', e => {
        const btn = e.target.closest('.quick-btn');
        if (!btn) return;
        
        if (btn.dataset.mode === 'recommend') {
            // 추천 모드로 변경
            chatMode = 'RECOMMEND';
            quickArea.style.display = 'none';
            appendMsg('bot', '🎨 **AI 맞춤 과목 추천 모드**입니다.\n학생의 전공과 이수 학점을 분석하여 이번 학기 최적의 시간표를 장바구니에 자동으로 담아드립니다.\n어떤 조건으로 시간표를 짤까요? (예: "금요일 공강 만들어줘", "오전 수업 위주로")');
            input.placeholder = "요청사항을 입력해주세요...";
            input.focus();
        } else if (btn.dataset.msg) {
            input.value = btn.dataset.msg;
            sendBtn.disabled = false;
            handleSend();
            quickArea.style.display = 'none'; // 일반 질문이더라도 버튼 한번 누르면 감춥니다.
        }
    });
}

// ── 기존 함수명 더미 ──
// dashboard.html 에서 onclick="requestAIRecommend()" 호출이 남아 있을 수 있으니 더미 유지 또는 챗봇 열려있게 유도
window.requestAIRecommend = function() {
    alert("화면 우측 하단의 챗봇 버튼을 통해 AI 맞춤 추천 기능을 이용해주세요.");
};
window.toggleChat = function() {
    const fab = document.getElementById('chatbotFab');
    if(fab) fab.click();
};
window.sendChatMessage = function() {};

