from django.db import models
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
import uuid


class ChatRoom(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=True, null=True) # DM'ler için isim null olabilir
    slug = models.SlugField(unique=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_chatrooms', null=True, blank=True) # DM'lerde owner boş olabilir
    participants = models.ManyToManyField(User, related_name='joined_chatrooms', blank=True)
    is_dm = models.BooleanField(default=False) # !!! YENİ EKLENEN ALAN: DM odası mı? !!!
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        if self.is_dm:
            return f"DM Room ({self.slug})"
        return self.name if self.name else f"Sohbet Odası ({self.slug})"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            if self.is_dm or not self.name:
                self.slug = uuid.uuid4().hex # Benzersiz rastgele bir slug
            else: 
                self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    
    def get_dm_name(self, current_user):
        if not self.is_dm:
            return self.name # Normal oda ise kendi adını döndür
        
        # DM odası ise, mevcut kullanıcı hariç diğer katılımcıyı bul
        other_participants = self.participants.exclude(id=current_user.id)
        if other_participants.exists():
            return other_participants.first().username
        else:
            # Eğer DM odasında tek kişi varsa (kendi kendine DM) veya beklenmedik bir durum
            return f"Sohbet: {current_user.username}"

class Message(models.Model):
    chatroom = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_system = models.BooleanField(default=False) # !!! YENİ EKLENECEK ALAN: Sistem mesajı mı? !!!
    read_by = models.ManyToManyField(User, related_name='read_messages', blank=True)
    

    class Meta:
        ordering = ('timestamp',)

    def __str__(self):
        return f'{self.sender.username} - {self.timestamp.strftime("%H:%M")}'

    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender.username,
            'timestamp': self.timestamp.strftime("%H:%M"),
            'content': self.content,
            'is_system': self.is_system, # is_system bilgisini de ekle
            
            
        }



