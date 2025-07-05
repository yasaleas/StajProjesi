document.addEventListener('DOMContentLoaded', function() {
    const chatLog = document.querySelector('#chat-log');
    const messageInput = document.querySelector('#chat-message-input');
    const messageSubmit = document.querySelector('#chat-message-submit');
    const typingIndicator = document.getElementById('typing-indicator');
    

    const dmOnlineStatus = document.getElementById('dm-online-status');
    const onlineUsersCount = document.getElementById('online-users-count');
    const onlineUsersList = document.getElementById('online-users-list');


    const username = window.currentUsername;
    const roomSlug = window.roomSlug;
    const isDmRoom = window.isDmRoom;
    

    const NGROK_PUBLIC_URL = '7f26-176-88-67-127.ngrok-free.app'; // BURAYI KENDİ GÜNCEL Ngrok URL'nizle değiştirin!

    const ws_protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const chatSocket = new WebSocket(`${ws_protocol}${NGROK_PUBLIC_URL}/ws/chat/${roomSlug}/`);

    let typingTimer;
    const TYPING_DELAY = 1500;
    const typingUsers = new Set();
    const unreadMessages = new Set(); // Okunmamış mesajların ID'lerini tutar

    chatSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        console.log("Received WebSocket data:", data);

        if (data.type === 'chat_message') {
            const { sender, message, timestamp, is_system, message_id, is_read } = data;
            

            if (typingUsers.has(sender)) {
                typingUsers.delete(sender);
                updateTypingIndicator();
            }
            
            if (is_system) {
                appendSystemMessage(message);
            } else {
                appendChatMessage(sender, message, timestamp, message_id, is_read);
                // Eğer mesajı başkası gönderdiyse ve görünürde ise, okundu bilgisi gönder
                if (sender !== username && isElementInViewport(document.querySelector(`.message-bubble[data-message-id="${message_id}"]`))) {
                    console.log(`[DEBUG] Marking message ${message_id} as read immediately after receiving.`);
                    sendReadReceipt(message_id);
                }
            }

            if (typeof data.unread_count !== "undefined" && data.room_slug) {
                const badge = document.querySelector(`.unread-count-${data.room_slug}`);
                if (badge) {
                    if (data.unread_count > 0) {
                        badge.textContent = data.unread_count;
                        badge.classList.remove("d-none");
                    } else {
                        badge.classList.add("d-none");
                    }
                } else {
                    console.log("Badge element not found");
                }
            }
            
        } else if (data.type === 'typing_status') {
            const { username: typingUsername, is_typing } = data;
            if (typingUsername === username) return;

            if (is_typing) {
                typingUsers.add(typingUsername);
            } else {
                typingUsers.delete(typingUsername);
            }
            updateTypingIndicator();

        } else if (data.type === 'online_status') {
            if (isDmRoom) {
                updateDmOnlineStatus(data.other_user_online);
            } else {
                updateGroupOnlineStatus(data.online_count, data.online_users);
            }
        } else if (data.type === 'read_receipt') {
            const messageEl = document.querySelector(`.message-bubble[data-message-id="${data.message_id}"]`);
            // Sadece benim gönderdiğim bir mesaj başkası tarafından okunduysa işlem yap
            if (messageEl && messageEl.dataset.sender === username && data.username !== username) {
                // Bu noktada mesajın "tamamen" mi okunduğunu bilemeyiz.
                // Ama en az bir kişi tarafından okunduysa çift tik gösterebiliriz.
                // Daha doğru bir implementasyon için backend'den 'is_fully_read' bayrağı beklemek gerekir.
                const statusSpan = messageEl.querySelector('.read-status');
                if (statusSpan) {
                    statusSpan.classList.remove('text-secondary');
                    statusSpan.classList.add('text-success');
                    const icon = statusSpan.querySelector('i');
                    if (icon) {
                        icon.classList.remove('fa-check');
                        icon.classList.add('fa-check-double');
                    }
                }
            }
        } else if (data.type === 'message_fully_read') {
            const messageId = data.message_id;
            const messageEl = document.querySelector(`.message-bubble[data-message-id="${messageId}"]`);

            // Sadece benim gönderdiğim bir mesajın durumunu güncelle
            if (messageEl && messageEl.dataset.sender === username) {
                const statusSpan = messageEl.querySelector('.read-status');
                const statusIcon = statusSpan ? statusSpan.querySelector('i') : null;

                if (statusSpan && statusIcon) {
                    statusSpan.classList.remove('text-secondary');
                    statusSpan.classList.add('text-success');
                    statusIcon.classList.remove('fa-check');
                    statusIcon.classList.add('fa-check-double');
                }
            }
        }
        
    };

    chatSocket.onopen = function(e) {
        console.log('Chat socket opened successfully');
        messageInput.focus();
        scrollToBottom();
        
    };

    chatSocket.onclose = function(e) {
        appendSystemMessage('Bağlantı kesildi. Sayfayı yenilemeyi deneyin.');
    };

    chatSocket.onerror = function(e) {
        console.error('Chat socket error:', e);
    };

    messageInput.addEventListener('keyup', function(e) {
        if (e.key === 'Enter') {
            messageSubmit.click();
            clearTimeout(typingTimer);
            sendTypingStatus(false);
        } else {
            clearTimeout(typingTimer);
            sendTypingStatus(true);
            typingTimer = setTimeout(() => {
                sendTypingStatus(false);
            }, TYPING_DELAY);
        }
    });

    messageSubmit.addEventListener('click', function(e) {
        const message = messageInput.value.trim();
        if (message === '') return;

        console.log("Mesaj gönderiliyor:", message);
        chatSocket.send(JSON.stringify({
            'type': 'chat_message',
            'message': message,
            'sender': username
        }));
        messageInput.value = '';
        clearTimeout(typingTimer);
        sendTypingStatus(false);
    });

    function appendChatMessage(sender, messageContent, timestamp, messageId, is_read) {
        const messageBubble = document.createElement('div');
        messageBubble.classList.add('message-bubble');
        messageBubble.classList.add(sender === username ? 'my-message' : 'other-message');
        if (messageId) {
            messageBubble.dataset.messageId = messageId;
        }
        messageBubble.dataset.sender = sender;

        let contentHtml = '';
        if (sender !== username) {
            contentHtml += `<span class="sender-name">${sender}</span>`;
        }
        contentHtml += `<span class="message-text">${messageContent}</span>`;
        contentHtml += `<span class="timestamp">${timestamp}</span>`;
        

        if (sender === username) {
            // Yeni gönderilen her mesaj için başlangıçta 'okunmadı' ikonu eklenir.
            const statusClass = is_read ? 'text-success' : 'text-secondary';
            const iconClass = is_read ? 'fa-check-double' : 'fa-check';
            contentHtml += `<span class="read-status ${statusClass}"><i class="fas ${iconClass}"></i></span>`;
            
            // Ana bubble'a da durumu belirten class'ı ekleyelim
            if (is_read) {
                messageBubble.classList.add("read");
            } else {
                messageBubble.classList.add("unread");
            }
        }
        

        messageBubble.innerHTML = contentHtml;
        chatLog.appendChild(messageBubble);
        scrollToBottom();
    }
    
    function appendSystemMessage(message) {
        const messageEl = document.createElement('div');
        messageEl.className = 'system-message';
        messageEl.textContent = message;
        chatLog.appendChild(messageEl);
        scrollToBottom();
    }

    function sendTypingStatus(isTyping) {
        if (chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.send(JSON.stringify({
                'type': 'typing_status',
                'is_typing': isTyping
            }));
        }
    }

    

    function isElementInViewport(el) {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.innerWidth)
        );
    }

    

    function updateTypingIndicator() {
        if (!typingIndicator) return;

        if (typingUsers.size > 0) {
            const usersArray = Array.from(typingUsers);
            let text = "";
            if (usersArray.length === 1) {
                text = `${usersArray[0]} yazıyor...`;
            } else {
                text = "Birden fazla kişi yazıyor...";
            }
            typingIndicator.textContent = text;
            typingIndicator.style.display = 'block';
        } else {
            typingIndicator.style.display = 'none';
        }
    }

    function updateDmOnlineStatus(isOnline) {
        if (!dmOnlineStatus) return;
        const badge = dmOnlineStatus.querySelector('.badge');
        if (isOnline) {
            badge.textContent = 'Çevrimiçi';
            badge.classList.remove('text-bg-secondary');
            badge.classList.add('text-bg-primary');
            
        } else {
            badge.textContent = 'Çevrimdışı';
            badge.classList.remove('text-bg-primary');
            badge.classList.add('text-bg-secondary');
        }
    }

    function updateGroupOnlineStatus(count, users) {
        if (onlineUsersCount) {
            onlineUsersCount.textContent = count;
        }
        if (onlineUsersList) {
            onlineUsersList.innerHTML = '';
            if (users && users.length > 0) {
                users.forEach(user => {
                    const listItem = document.createElement('li');
                    listItem.innerHTML = `<span class="dropdown-item-text">${user}</span>`;
                    onlineUsersList.appendChild(listItem);
                });
            } else {
                const listItem = document.createElement('li');
                listItem.innerHTML = '<span class="dropdown-item-text">Kimse çevrimiçi değil.</span>';
                onlineUsersList.appendChild(listItem);
            }
        }
    }



    function sendReadReceipt(messageId) {
        if (chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.send(JSON.stringify({
                'type': 'read_receipt',
                'message_id': messageId
            }));
        }
    }

    
    function scrollToBottom() {
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    scrollToBottom();
});