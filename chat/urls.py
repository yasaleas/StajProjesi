from django.urls import path, re_path, include
from . import views
from django.contrib import admin


urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.home_view, name='home'),

    re_path(r'^chat/(?P<room_slug>[^/]+)/$', views.room_view, name='room'), 
    
    path('create_room/', views.create_room_view, name='create_room'),
    path('join_room/<str:room_slug>/', views.join_room_view, name='join_room'),
    path('search_rooms/', views.search_rooms_view, name='search_rooms'),

    # !!! YENİ URL'LER: DM İÇİN !!!
    path('search_users/', views.search_users_view, name='search_users'),
    path('create_or_get_dm/', views.create_or_get_dm_view, name='create_or_get_dm'),
    


]
