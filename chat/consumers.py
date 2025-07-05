import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from .models import ChatRoom, Message
from django.utils import timezone
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync





online_users = {}
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_slug = self.scope['url_route']['kwargs']['room_slug']
        self.room_group_name = 'chat_%s' % self.room_slug
        self.user = self.scope['user']

        # Sadece giriş yapmış kullanıcılar bağlanabilir
        if not self.user.is_authenticated:
            await self.close()
            return


        self.chatroom = await sync_to_async(ChatRoom.objects.get)(slug=self.room_slug)
        
        # Kanal grubuna katıl
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        read_message_ids = await self.mark_unread_messages_as_read()


        if read_message_ids:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'messages_read_event',  # Yeni olay türümüz
                    'message_ids': read_message_ids,
                    'username': self.user.username  # Kimin okuduğu bilgisi
                }
            )


        if self.room_slug not in online_users:
            online_users[self.room_slug] = {}


        



        

        online_users[self.room_slug][self.user.username] = self.channel_name


        await self.send_online_users_to_room()



        if self.chatroom.is_dm:
            other_participants = await sync_to_async(list)(self.chatroom.participants.exclude(id=self.user.id))
            if other_participants:
                other_user = other_participants[0]
                if other_user.username in online_users[self.room_slug]:
                    # Eğer diğer kullanıcı da bu odada çevrimiçi ise, ona da online bilgisi gönder
                    # Bu, karşıdaki kişi "Offline" iken senin odaya girince "Online" olmasını sağlar
                    await self.channel_layer.send(
                        online_users[self.room_slug][other_user.username],
                        {
                            'type': 'status_update',
                            'username': self.user.username,
                            'is_online': True
                        }
                    )


    async def disconnect(self, close_code):


        if self.room_slug in online_users and self.user.username in online_users[self.room_slug]:
            del online_users[self.room_slug][self.user.username]
            if not online_users[self.room_slug]: # Oda boşaldıysa dictionary'den kaldır
                del online_users[self.room_slug]
        
        await self.send_online_users_to_room()

        if self.chatroom.is_dm:
            other_participants = await sync_to_async(list)(self.chatroom.participants.exclude(id=self.user.id))
            if other_participants:
                other_user = other_participants[0]
                if other_user.username in online_users.get(self.room_slug, {}): # Diğer kullanıcı hala bu odada mı?
                    await self.channel_layer.send(
                        online_users[self.room_slug][other_user.username],
                        {
                            'type': 'status_update',
                            'username': self.user.username,
                            'is_online': False
                        }
                    )
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def status_update(self, event):
        username = event['username']
        is_online = event['is_online']

        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'username': username,
            'is_online': is_online
        }))

    # WebSocket'ten mesaj al
    async def receive(self, text_data):
        data_json = json.loads(text_data)
        message_type = data_json.get('type')
        
        if message_type == 'chat_message':
            # ... (mesaj kaydetme ve gruba gönderme kısmı aynı kalabilir) ...
            message_content = data_json['message']
            sender_username = self.user.username
            message_id = await self.save_message(sender_username, message_content)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_content,
                    'sender': sender_username,
                    'timestamp': timezone.now().strftime("%H:%M"),
                    'message_id': message_id,
                    'room_slug': self.room_slug
                }
            )

            # Ana sayfa için bildirim gönderme mantığı GÜNCELLENDİ
            channel_layer = get_channel_layer()
            participants = await sync_to_async(list)(self.chatroom.participants.all())

            for participant in participants:
                if participant.username != sender_username:
                    # --- YENİ HESAPLAMA ---
                    # Katılımcının okumadığı VE göndermediği mesajları say
                    unread_count = await sync_to_async(
                        lambda p: Message.objects.filter(
                            chatroom=self.chatroom
                        ).exclude(Q(sender=p) | Q(read_by=p)).count()
                    )(participant)
                    # --- YENİ HESAPLAMA SONU ---

                    user_group_name = f'user_notifications_{participant.username}'
                    await channel_layer.group_send(
                        user_group_name,
                        {
                            'type': 'send_notification',
                            'message': {
                                'type': 'new_message',
                                'room_slug': self.room_slug,
                                'last_message': message_content,
                                'sender': sender_username,
                                'timestamp': timezone.now().strftime("%H:%M"),
                                'unread_count': unread_count,
                                'is_dm_room': self.chatroom.is_dm,
                            }
                        }
                    )


        elif message_type == 'typing_status':
            is_typing = data_json['is_typing']
            
            # Kendi "yazıyor" durumumuzu kendimize göndermeye gerek yok
            if self.user.username in online_users.get(self.room_slug, {}):
                current_channel_name = online_users[self.room_slug][self.user.username]
                
                for username_in_room, channel_name_in_room in online_users[self.room_slug].items():
                    if username_in_room != self.user.username: # Sadece diğer kullanıcılara gönder
                        await self.channel_layer.send(
                            channel_name_in_room,
                            {
                                'type': 'typing_status',
                                'username': self.user.username,
                                'is_typing': is_typing
                            }
                        )
        

        elif message_type == 'read_receipt':
            message_id = data_json['message_id']
            changed = await self.mark_message_as_read(message_id)
            
            if changed:
                # Bu okuma işlemiyle mesajın tamamen okunup okunmadığını kontrol et
                fully_read_ids = await self.check_if_messages_are_fully_read([message_id])
                
                # Eğer tamamen okunduysa, gruba özel olayı gönder
                if fully_read_ids:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'message_fully_read_event', # Aşağıda handler'ını ekleyeceğiz
                            'message_id': fully_read_ids[0]
                        }
                    )


    async def chat_message(self, event):
        print(f"[DEBUG] chat_message handler triggered: {event}")
        message_content = event['message']
        sender = event['sender']
        timestamp = event['timestamp']
        is_system = event.get('is_system', False)
        
        
        

        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message_content,
            'sender': sender,
            'timestamp': timestamp,
            'is_system': is_system,
            'message_id': event.get('message_id')  # Eğer varsa message_id gönder
            
        }))

    # Veritabanına mesajı asenkron olarak kaydetmek için
    

    # Kanal grubundan mesaj al
    async def chat_message_event(self, event):
        # Mesajı WebSocket'e gönder
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'username': event['username']
        }))

    async def typing_status(self, event):
        username = event['username']
        is_typing = event['is_typing']

        if username == self.user.username:
            return

        await self.send(text_data=json.dumps({
            'type': 'typing_status',
            'username': username,
            'is_typing': is_typing
        }))
            
    async def read_receipt_event(self, event):
        # Okundu bilgisini WebSocket'e gönder
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'username': event['username']
        }))

    async def messages_read_event(self, event):

        await self.send(text_data=json.dumps({
            'type': 'messages_read',  # İstemci tarafında bu type'ı yakalayacağız
            'message_ids': event['message_ids'],
            'username': event['username']
        }))

    async def online_user_list(self, event):
        online_usernames = event['online_usernames']
        is_dm_room = event['is_dm_room']
        current_username = self.user.username # Mevcut kullanıcının adı

        if is_dm_room:
            # DM odasında sadece karşıdaki kişinin online olup olmadığını göster
            other_user_online = False
            other_username = None
            other_participants = await sync_to_async(list)(self.chatroom.participants.exclude(id=self.user.id))
            if other_participants:
                other_username = other_participants[0].username
                if other_username in online_usernames:
                    other_user_online = True

            await self.send(text_data=json.dumps({
                'type': 'online_status',
                'is_dm_room': True,
                'other_user_username': other_username, # Karşıdaki kullanıcının adı
                'other_user_online': other_user_online
            }))
        else:
            # Toplu odalarda tüm online listesini gönder
            await self.send(text_data=json.dumps({
                'type': 'online_status',
                'is_dm_room': False,
                'online_users': online_usernames,
                'online_count': len(online_usernames)
            }))


    async def send_online_users_to_room(self):
        online_usernames_in_room = list(online_users.get(self.room_slug, {}).keys())
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'online_user_list',
                'online_usernames': online_usernames_in_room,
                'is_dm_room': self.chatroom.is_dm
            }
        )


    @sync_to_async
    def save_message(self, sender_username, message_content):
        print(f"[DEBUG] save_message çağrıldı - sender: {sender_username}, content: {message_content}")
        try:
            sender_user_instance = User.objects.get(username=sender_username)
            room = ChatRoom.objects.get(slug=self.room_slug)
            message = Message.objects.create(
                chatroom=room,
                sender=sender_user_instance, 
                content=message_content, 
            )
            print(f"[DEBUG] Mesaj veritabanına kaydedildi: {message.id}")
            return message.id
        except Exception as e:
            print(f"[ERROR] Mesaj kaydedilirken hata: {e}")
            return None


    @sync_to_async
    def mark_message_as_read(self, message_id):
        """Tek bir mesajı mevcut kullanıcı için 'okundu' olarak işaretler."""
        try:
            message = Message.objects.get(id=message_id)
            # Eğer kullanıcı mesajı zaten okumadıysa ekle
            if self.user not in message.read_by.all():
                message.read_by.add(self.user)
                return True # Durum değişti
            return False # Durum değişmedi
        except Message.DoesNotExist:
            return False

    @sync_to_async
    def mark_unread_messages_as_read(self):
        """Odadaki, mevcut kullanıcının okumadığı tüm mesajları okundu olarak işaretler."""
        # Mevcut kullanıcının göndermediği ve okumadığı mesajları bul
        messages_to_mark = Message.objects.filter(
            chatroom=self.chatroom
        ).exclude(sender=self.user).exclude(read_by=self.user)
        
        message_ids = list(messages_to_mark.values_list('id', flat=True))

        if not message_ids:
            return [] # Güncellenecek mesaj yok

        # Mevcut kullanıcıyı bu mesajların 'read_by' listesine ekle
        for message in messages_to_mark:
            message.read_by.add(self.user)
            
        return message_ids


    async def read_receipt_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'username': event['username'],
        }))


    async def messages_read_event(self, event):
        """
        Bir kullanıcı odaya girdiğinde ve toplu okuma yaptığında tetiklenir.
        Bu olay, odadaki HERKESE gönderilir.
        """
        message_ids = event['message_ids']
        reader_username = event['username']

        # Eğer mesajları okuyan kişi biz isek, bu olayı kendimize göndermeye gerek yok.
        # İkon güncellemesi sadece bizim gönderdiğimiz mesajlar için geçerlidir.
        if reader_username == self.user.username:
            return

        # Okunan her mesaj için, "tamamen okundu" durumunu kontrol et
        # Bu işlem veritabanı sorgusu gerektirdiği için sync_to_async kullanıyoruz.
        fully_read_message_ids = await self.check_if_messages_are_fully_read(message_ids)

        # Sadece durumu "tamamen okundu"ya dönen mesajlar için bildirim gönder
        for msg_id in fully_read_message_ids:
             await self.send(text_data=json.dumps({
                'type': 'message_fully_read', # YENİ, ÖZEL OLAY TÜRÜ
                'message_id': msg_id,
            }))


        
    @sync_to_async
    def check_if_messages_are_fully_read(self, message_ids):
        """Verilen mesaj ID listesinden hangilerinin tamamen okunduğunu kontrol eder."""
        fully_read_ids = []
        
        # Odadaki katılımcı sayısını al (gönderici hariç)
        other_participants_count = self.chatroom.participants.count() - 1
        if other_participants_count <= 0:
            return [] # Başka katılımcı yoksa kontrol anlamsız

        messages = Message.objects.filter(id__in=message_ids).prefetch_related('read_by')

        for message in messages:
            # Mesajı gönderen dışındaki okuyanların sayısı
            read_by_others_count = message.read_by.exclude(id=message.sender.id).count()
            
            if read_by_others_count >= other_participants_count:
                fully_read_ids.append(message.id)
                
        return fully_read_ids


    async def message_fully_read_event(self, event):
        """Gruba gönderilen 'tamamen okundu' olayını tekil istemcilere dağıtır."""
        await self.send(text_data=json.dumps({
            'type': 'message_fully_read',
            'message_id': event['message_id'],
        }))















class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()

        self.user_group_name = f'user_notifications_{self.user.username}'

        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )

    async def send_notification(self, event): # views.py'den gelen event
        message = event['message']
        await self.send(text_data=json.dumps(message))
        