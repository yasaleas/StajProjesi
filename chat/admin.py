# core/admin.py

from django.contrib import admin
from .models import ChatRoom, Message

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug',  'owner', 'created_at', 'is_dm')
    search_fields = ('name', 'slug', 'owner__username')
    prepopulated_fields = {'slug': ('name',)} 
    filter_horizontal = ('participants',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'chatroom', 'timestamp', 'content', 'get_read_by_users')
    search_fields = ('content', 'sender__username', 'chatroom__name')
    date_hierarchy = 'timestamp'
    filter_horizontal = ('read_by',)
    def get_read_by_users(self, obj):
        return ", ".join([user.username for user in obj.read_by.all()])
    get_read_by_users.short_description = 'Okuyanlar'

