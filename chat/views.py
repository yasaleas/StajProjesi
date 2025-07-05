import uuid 
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.db import IntegrityError, models
from django.template.defaultfilters import slugify
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from .models import ChatRoom,Message
from django.contrib.auth.models import User 
from django.db.models import Max, Q




# Kayıt olma sayfası
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) 
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

# Giriş yapma sayfası
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

# Çıkış yapma
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('login') # Çıkış sonrası giriş sayfasına yönlendir
    # POST isteği olmadan logout yapmayı engellemek için basit bir güvenlik önlemi
    return redirect('home')

# Ana Sayfa (Sohbet Listesi, Arama ve Oluşturma)

@login_required
def home_view(request):  
    direct_message_rooms = ChatRoom.objects.filter(participants=request.user, is_dm=True).annotate(
        last_message_timestamp=Max('messages__timestamp')
    ).order_by('-last_message_timestamp', '-created_at')

    channel_message_rooms = ChatRoom.objects.filter(participants=request.user, is_dm=False).annotate(
        last_message_timestamp=Max('messages__timestamp')
    ).order_by('-last_message_timestamp', '-created_at')

    owned_channels = ChatRoom.objects.filter(owner=request.user, is_dm=False).annotate(
        last_message_timestamp=Max('messages__timestamp')
    ).order_by('-last_message_timestamp', '-created_at')

    dm_room_display_names = []
    for dm_room in direct_message_rooms:
        other_participants = dm_room.participants.exclude(id=request.user.id)
        display_name = ""
        if other_participants.exists():
            display_name = f"{other_participants.first().username}"
        

        dm_room.last_message = Message.objects.filter(chatroom=dm_room).order_by('-timestamp').first()

        unread_count = Message.objects.filter(
            chatroom=dm_room
        ).exclude(Q(sender=request.user) | Q(read_by=request.user)).count()

        dm_room_display_names.append({
        'room': dm_room,
        'display_name': display_name,
        'last_message': dm_room.last_message,
        'unread_count': unread_count,
        })

    channel_room_display_names = []
    for channel_room in channel_message_rooms:
        other_participants = channel_room.participants.exclude(id=request.user.id)
        display_name = channel_room.name  # Normal kanallar için adı kullan
        channel_room.last_message = Message.objects.filter(chatroom=channel_room).order_by('-timestamp').first()
        unread_count = Message.objects.filter(
            chatroom=channel_room
        ).exclude(Q(sender=request.user) | Q(read_by=request.user)).count()
        channel_room_display_names.append({
            'room': channel_room,
            'display_name': display_name,
            'last_message': channel_room.last_message,
            'unread_count': unread_count,
        })

    owned_room_display_names = []
    for owned_channel in owned_channels:
        other_participants = owned_channel.participants.exclude(id=request.user.id)
        display_name = owned_channel.name 
        owned_channel.last_message = Message.objects.filter(chatroom=owned_channel).order_by('-timestamp').first()
        unread_count = Message.objects.filter(
            chatroom=owned_channel
        ).exclude(Q(sender=request.user) | Q(read_by=request.user)).count()
        owned_room_display_names.append({
            'room': owned_channel,
            'display_name': owned_channel.name,
            'last_message': owned_channel.last_message,
            'unread_count': unread_count,
        })
    
    


    return render(request, 'chat/home.html', {
        #'user_channels': user_channels,
        'owned_channels': owned_room_display_names,
        'dm_rooms': dm_room_display_names,
        'channel_rooms': channel_room_display_names,

    })



@login_required
def create_room_view(request):
    if request.method == 'POST':
        room_name = request.POST.get('room_name')


        if not room_name:
            return JsonResponse({'success': False, 'message': 'Kanal adı boş olamaz.'}, status=400)

        room_slug = slugify(room_name)
        if not room_slug: # Slugify boş bir string döndürürse (örn: sadece özel karakterler)
            return JsonResponse({'success': False, 'message': 'Geçerli bir kanal adı girin.'}, status=400)

        try:
            # Kanalı oluştur
            chatroom = ChatRoom.objects.create(
                name=room_name,
                slug=room_slug,
                owner=request.user
            )
            # Kanal sahibi otomatik olarak katılımcı olarak eklenir
            chatroom.participants.add(request.user)
            chatroom.save()

            return JsonResponse({'success': True, 'redirect_url': f'/chat/{room_slug}/'})
        except IntegrityError:
            return JsonResponse({'success': False, 'message': 'Bu isimde bir kanal zaten mevcut.'}, status=409)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Kanal oluşturulurken bir hata oluştu: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405) # Sadece POST isteklerini kabul et



@login_required
def room_view(request, room_slug): # Oda adını URL'den alacak
    chatroom = get_object_or_404(ChatRoom, slug=room_slug)


    
    display_room_name = chatroom.name 

    if chatroom.is_dm:
        other_participants = chatroom.participants.exclude(id=request.user.id)
        if other_participants.exists():
            display_room_name = other_participants.first().username 
        else:
            display_room_name = f"Sohbet: {request.user.username}" # Veya istediğiniz başka bir isim

    # Geçmiş mesajları al
    messages = Message.objects.filter(chatroom=chatroom).order_by('timestamp').prefetch_related('read_by', 'sender')

    # --- YENİ LOGIC ---
    # Odadaki diğer katılımcıların sayısını alalım
    other_participants_count = chatroom.participants.count() - 1
    
    # Her mesaj için özel bir "is_fully_read" durumu ekleyelim
    messages_with_status = []
    for message in messages:
        # Mesajı gönderen dışındaki okuyanların sayısı
        read_by_others_count = message.read_by.exclude(id=message.sender.id).count()
        
        # Eğer mesajı gönderen biz isek ve diğer herkes okuduysa 'tamamen okundu' sayılır
        is_fully_read = (message.sender == request.user and 
                         other_participants_count > 0 and 
                         read_by_others_count >= other_participants_count)
        
        messages_with_status.append({
            'obj': message,
            'is_fully_read': is_fully_read
        })
    # --- YENİ LOGIC SONU ---

    return render(request, 'chat/room.html', {
        'room_name': display_room_name,
        'room_slug': room_slug,
        'username': request.user.username,
        'messages_with_status': messages_with_status, # Değişen context
        'chatroom': chatroom,
    })
    
@login_required
def join_room_view(request, room_slug):
    if request.method == 'POST':
        chatroom = get_object_or_404(ChatRoom, slug=room_slug)

        # Kullanıcının zaten katılımcı olup olmadığını kontrol et (genel veya özel)
        if chatroom.participants.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'message': 'Zaten bu kanala katıldınız.'}, status=400)

        else:
            # Genel kanal ise doğrudan katılımcı yap (yukarıdaki katılımcı kontrolünden geçtiyse)
            chatroom.participants.add(request.user)
            chatroom.save()
            return JsonResponse({'success': True, 'redirect_url': f'/chat/{room_slug}/'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
    




@login_required
def search_rooms_view(request):
    query = request.GET.get('q', '')
    if query:
        # Kanal adı veya slug'ında arama yap
        results = ChatRoom.objects.filter(
            models.Q(name__icontains=query) | models.Q(slug__icontains=query)
        ).distinct().order_by('name')
    else:
        results = ChatRoom.objects.none() # Boş sorguda sonuç yok

    # Her sonuç için gerekli bilgileri dictionary olarak döndür
    room_data = []
    for room in results:
        is_participant = room.participants.filter(id=request.user.id).exists()
        room_data.append({
            'name': room.name,
            'slug': room.slug,
            'is_participant': is_participant,
            'owner_username': room.owner.username,
        })
    
    return JsonResponse({'success': True, 'rooms': room_data})






@login_required
def search_users_view(request):
    query = request.GET.get('q', '')
    if query:
        results = User.objects.filter(
            username__icontains=query
        ).exclude(id=request.user.id).order_by('username')
    else:
        results = User.objects.none()

    user_data = []
    for user_obj in results:
        existing_dm_room = ChatRoom.objects.filter(
            is_dm=True,
            participants=request.user
        ).filter(
            participants=user_obj
        ).first()

        # Buton metnini burada belirleyip frontend'e gönderelim
        button_text = "Sohbete Git" if existing_dm_room else "Sohbet Başlat"
        
        user_data.append({
            'username': user_obj.username,
            'user_id': user_obj.id,
            'has_dm_room': existing_dm_room is not None,
            'dm_room_slug': existing_dm_room.slug if existing_dm_room else None,
            'button_text': button_text, # !!! YENİ: Buton metni !!!
        })
    
    return JsonResponse({'success': True, 'users': user_data})




@login_required
def create_or_get_dm_view(request):
    if request.method == 'POST':
        target_username = request.POST.get('username')
        
        if not target_username:
            return JsonResponse({'success': False, 'message': 'Kullanıcı adı boş olamaz.'}, status=400)

        target_user = get_object_or_404(User, username=target_username)

        if target_user == request.user:
            return JsonResponse({'success': False, 'message': 'Kendinize özel mesaj atamazsınız.'}, status=400)

        # İki kullanıcı arasında zaten bir DM odası var mı kontrol et
        # participants__in kullanarak her iki kullanıcının da dahil olduğu odaları buluruz
        existing_dm_room = ChatRoom.objects.filter(
            is_dm=True,
            participants=request.user
        ).filter(
            participants=target_user
        ).first()

        if existing_dm_room:
            # Zaten bir DM odası varsa, o odaya yönlendir
            return JsonResponse({'success': True, 'redirect_url': f'/chat/{existing_dm_room.slug}/'})
        else:
            # Yeni DM odası oluştur
            try:
                dm_room = ChatRoom.objects.create(
                    is_dm=True,
                    # Name ve owner DM odaları için null olabilir
                    # slug save metodunda otomatik oluşacak
                )
                dm_room.participants.add(request.user, target_user)
                dm_room.save() # Slug'ın oluşması için save() çağrısı önemli
                
                return JsonResponse({'success': True, 'redirect_url': f'/chat/{dm_room.slug}/'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'DM odası oluşturulurken bir hata oluştu: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

