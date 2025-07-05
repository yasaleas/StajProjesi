const NGROK_PUBLIC_URL = 'dfd7-176-88-67-127.ngrok-free.app'; // Burayı her zaman güncel tut!

document.addEventListener('DOMContentLoaded', function() {
    // Top-level DOM elements
    const searchUserInput = document.getElementById('search-user-input');
    const searchUserButton = document.getElementById('search-user-button');
    const userSearchResultsDiv = document.getElementById('user-search-results');
    
    const searchRoomInput = document.getElementById('search-room-input');
    const searchRoomButton = document.getElementById('search-room-button');
    const searchResultsDiv = document.getElementById('search-results');

    const createRoomToggleBtn = document.getElementById('create-room-toggle');
    const createRoomForm = document.getElementById('create-room-form');
    const roomNameInput = document.getElementById('room-name-input');
    const isPrivateCheckbox = document.getElementById('is-private-checkbox');
    const createRoomMessage = document.getElementById('create-room-message');

    // Menu navigation
    const navButtons = document.querySelectorAll('.nav-button');
    const contentSections = document.querySelectorAll('.content-section');
    


    navButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove 'active' from all buttons and sections
            navButtons.forEach(btn => btn.classList.remove('active'));
            contentSections.forEach(section => section.classList.remove('active'));

            // Add 'active' to the clicked button and its corresponding section
            this.classList.add('active');
            const targetId = this.dataset.target;
            document.getElementById(targetId).classList.add('active');
        });
    });

    // Toggle Create Room Form
    if (createRoomToggleBtn) {
        createRoomToggleBtn.addEventListener('click', function() {
            if (createRoomForm.style.display === 'none' || createRoomForm.style.display === '') {
                createRoomForm.style.display = 'block';
                this.textContent = 'Kanal Oluşturmayı Kapat';
            } else {
                createRoomForm.style.display = 'none';
                this.textContent = 'Kanal Oluştur';
            }
        });
    }

    // --- Kanal Oluşturma Formu (Mevcut kodunuzdan) ---
    if (createRoomForm) {
        createRoomForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const roomName = roomNameInput.value.trim();
            const isPrivate = isPrivateCheckbox.checked;

            if (roomName === '') {
                createRoomMessage.textContent = 'Kanal adı boş olamaz.';
                return;
            }

            const formData = new FormData();
            formData.append('room_name', roomName);
            formData.append('is_private', isPrivate);
            formData.append('csrfmiddlewaretoken', document.querySelector('[name="csrfmiddlewaretoken"]').value);

            try {
                const response = await fetch('/create_room/', {
                    method: 'POST',
                    body: formData,
                });
                const data = await response.json();

                if (data.success) {
                    alert('Kanal başarıyla oluşturuldu!');
                    roomNameInput.value = '';
                    isPrivateCheckbox.checked = false;
                    createRoomMessage.textContent = '';
                    // Sayfayı yenileyerek yeni kanalı listede göster
                    window.location.reload(); 
                } else {
                    createRoomMessage.textContent = data.message || 'Kanal oluşturulurken bir hata oluştu.';
                }
            } catch (error) {
                createRoomMessage.textContent = 'Kanal oluşturulurken bir ağ hatası oluştu.';
                console.error('Create room error:', error);
            }
        });
    }

    searchRoomInput.addEventListener('keyup', function(e) {
        if (e.key === 'Enter') {
            searchRoomButton.click(); 
        }
    });

    // --- Kanal Arama (Mevcut kodunuzdan) ---
    if (searchRoomButton) {
        searchRoomButton.addEventListener('click', async function() {
            const query = searchRoomInput.value.trim();
            if (query === '') {
                searchResultsDiv.innerHTML = '';
                return;
            }

            try {
                const response = await fetch(`/search_rooms/?q=${encodeURIComponent(query)}`);
                const data = await response.json();

                if (data.success) {
                    searchResultsDiv.innerHTML = '';
                    if (data.rooms.length > 0) {
                        data.rooms.forEach(room => {
                            const roomElement = document.createElement('div');
                            roomElement.classList.add('search-result-item');
                            roomElement.innerHTML = `
                                <span>${room.name} ${room.is_private ? '🔒 (Özel)' : ''}</span>
                                <button class="join-room-btn" data-slug="${room.slug}" 
                                        ${room.has_pending_request ? 'disabled' : ''} 
                                        ${room.is_participant ? 'disabled' : ''}>
                                    ${room.is_participant ? 'Katıldınız' : (room.has_pending_request ? 'İstek Bekleniyor' : 'Katıl')}
                                </button>
                            `;
                            searchResultsDiv.appendChild(roomElement);
                        });
                        searchResultsDiv.querySelectorAll('.join-room-btn').forEach(button => {
                            button.addEventListener('click', handleJoinRoom);
                        });
                    } else {
                        searchResultsDiv.innerHTML = '<p>Kanal bulunamadı.</p>';
                    }
                } else {
                    searchResultsDiv.innerHTML = `<p style="color: red;">Kanal arama sırasında hata oluştu: ${data.message}</p>`;
                }
            } catch (error) {
                searchResultsDiv.innerHTML = `<p style="color: red;">Kanal arama sırasında bir hata oluştu.</p>`;
                console.error('Room search error:', error);
            }
        });
    }
    



    // handleJoinRoom (Mevcut kodunuzdan)
    async function handleJoinRoom(event) {
        const button = event.target;
        const roomSlug = button.dataset.slug;
        button.disabled = true; // Butonu devre dışı bırak

        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', document.querySelector('[name="csrfmiddlewaretoken"]').value);

        try {
            const response = await fetch(`/join_room/${roomSlug}/`, {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();

            if (data.success) {
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    alert(data.message || 'Katılım isteğiniz gönderildi. Onay bekleniyor.');
                    window.location.reload(); // İsteğin gönderildiğini göstermek için sayfayı yenile
                }
            } else {
                alert(data.message || 'Katılma işlemi başarısız oldu.');
                button.disabled = false; // Hata durumunda butonu tekrar etkinleştir
            }
        } catch (error) {
            alert('Katılma işlemi sırasında bir hata oluştu.');
            button.disabled = false;
            console.error('Join room error:', error);
        }
    }



    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // --- Bildirim WebSocket'i (Mevcut kodunuzdan) ---
    const notificationSocket = new WebSocket(
        protocol + '//' + NGROK_PUBLIC_URL + '/ws/notifications/'
    );
    

    notificationSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        if (data.type === 'notification') {
            console.log('Notification:', data.message);
        } else if (data.type === 'new_message') {
            const slug = data.room_slug;
            const sender = data.sender;
            const lastMessage = data.last_message;
            const timestamp = data.timestamp;
            const unreadCount = data.unread_count;
            

            

            // Son mesaj içeriğini güncelle
            const lastMessageElem = document.querySelector(`.last-message-content-${slug}`);
            if (lastMessageElem) {
                lastMessageElem.textContent = `${sender} : ${lastMessage}`;
                
            }

            // Son mesaj zamanını güncelle
            const timestampElem = document.querySelector(`.last-message-timestamp-${slug}`);
            if (timestampElem) {
                timestampElem.textContent = timestamp;
            }

            // Okunmamış mesaj sayısını güncelle veya oluştur
            let unreadBadge = document.querySelector(`.unread-count-${slug}`);
            if (unreadCount > 0) {
                if (unreadBadge) {
                    unreadBadge.textContent = unreadCount;
                } else {
                    // Badge yoksa, link içine ekle
                    const linkElem = document.querySelector(`a.chat-link[href$="${slug}/"]`);
                    if (linkElem) {
                        const badge = document.createElement('span');
                        badge.classList.add('badge', 'bg-danger', 'rounded-pill', 'ms-2', `unread-count-${slug}`);
                        badge.textContent = unreadCount;
                        linkElem.appendChild(badge);
                    }
                }
            } else {
                // Okunmamış yoksa badge varsa kaldır
                if (unreadBadge) unreadBadge.remove();
            }

            const chatLink = document.querySelector(`a.chat-link[href$="${slug}/"]`);
            if (chatLink) {
                const listItem = chatLink.closest("li.list-group-item");
                if (listItem && listItem.parentNode) {
                    listItem.parentNode.prepend(listItem);
                }
            }
        }
    };

    notificationSocket.onclose = function(e) {
        
    };

    notificationSocket.onerror = function(e) {
        console.error('Notification socket error:', e);
    };



    searchUserInput.addEventListener('keyup', function(e) {
        if (e.key === 'Enter') {
            searchUserButton.click(); // Enter tuşuna basıldığında arama butonuna tıkla
        }
    });

    // --- Kullanıcı Arama ve DM Başlatma (Güncellenmiş) ---
    if (searchUserButton) {
        searchUserButton.addEventListener('click', async function() {
            const query = searchUserInput.value.trim();
            if (query === '') {
                userSearchResultsDiv.innerHTML = '';
                return;
            }

            try {
                const response = await fetch(`/search_users/?q=${encodeURIComponent(query)}`);
                const data = await response.json();

                if (data.success) {
                    userSearchResultsDiv.innerHTML = '';
                    if (data.users.length > 0) {
                        data.users.forEach(user => {
                            const userElement = document.createElement('div');
                            userElement.classList.add('user-search-result-item');
                            
                            // Buton metni backend'den geliyor
                            const buttonText = user.button_text; 
                            let buttonClass = user.has_dm_room ? 'go-to-dm-btn' : 'start-dm-btn';

                            userElement.innerHTML = `
                                <span>${user.username}</span>
                                <button class="${buttonClass}" 
                                        data-username="${user.username}" 
                                        data-slug="${user.dm_room_slug}">${buttonText}</button>
                            `;
                            userSearchResultsDiv.appendChild(userElement);
                        });
                        // Yeni eklenen butonlara event listener ekle
                        userSearchResultsDiv.querySelectorAll('.start-dm-btn').forEach(button => {
                            button.addEventListener('click', handleStartDM);
                        });
                        userSearchResultsDiv.querySelectorAll('.go-to-dm-btn').forEach(button => {
                            button.addEventListener('click', handleGoToDM);
                        });
                    } else {
                        userSearchResultsDiv.innerHTML = '<p>Kullanıcı bulunamadı.</p>';
                    }
                } else {
                    userSearchResultsDiv.innerHTML = `<p style="color: red;">Kullanıcı arama sırasında hata oluştu: ${data.message}</p>`;
                }
            } catch (error) {
                userSearchResultsDiv.innerHTML = `<p style="color: red;">Kullanıcı arama sırasında bir hata oluştu.</p>`;
                console.error('User search error:', error);
            }
        });
    }

    async function handleStartDM(event) {
        const button = event.target;
        const targetUsername = button.dataset.username;
        
        button.disabled = true;

        const formData = new FormData();
        formData.append('username', targetUsername);
        formData.append('csrfmiddlewaretoken', document.querySelector('[name="csrfmiddlewaretoken"]').value);

        try {
            const response = await fetch('/create_or_get_dm/', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (data.success && data.redirect_url) {
                window.location.href = data.redirect_url; // DM odasına yönlendir
            } else {
                alert(data.message || 'DM başlatma başarısız oldu.');
                button.disabled = false;
            }
        } catch (error) {
            alert('DM başlatma sırasında bir hata oluştu.');
            button.disabled = false;
            console.error('Start DM error:', error);
        }
    }

    function handleGoToDM(event) {
        const button = event.target;
        const roomSlug = button.dataset.slug;
        window.location.href = `/chat/${roomSlug}/`; // Mevcut DM odasına git
    }
});