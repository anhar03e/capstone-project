from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from .views import CustomPasswordResetView

app_name = 'capstone_system'

urlpatterns = [

    # ===================== AUTH =====================
    path('', views.home, name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('force-change-password/', views.force_change_password, name='force_change_password'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='auth/password_reset_done.html',), name='password_reset_done',),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='auth/password_reset_confirm.html', success_url=reverse_lazy('capstone_system:password_reset_complete'),), name='password_reset_confirm',),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='auth/password_reset_complete.html',), name='password_reset_complete',),

    # ===================== MAHASISWA =====================
    path('mahasiswa/', views.mahasiswa_home, name='mahasiswa_home'),
    path('mahasiswa/dospem/', views.list_dospem, name='list_dospem'),
    path('mahasiswa/upload-proposal/', views.upload_proposal, name='upload_proposal'),
    path('mahasiswa/upload-resume/', views.upload_resume, name='upload_resume'),
    path('mahasiswa/status/', views.cek_status, name='cek_status'),
    path('mahasiswa/profile/', views.mahasiswa_profile, name='mahasiswa_profile'),
    path('search-mahasiswa/', views.search_mahasiswa, name='search_mahasiswa'),
    path('mahasiswa/buat-tim/', views.buat_tim, name='buat_tim'),
    path('undangan-tim/', views.undangan_tim, name='undangan_tim'),
    path('mahasiswa/jadwal-bimbingan/',views.mahasiswa_jadwal_bimbingan,name='mahasiswa_jadwal'),
    path('mahasiswa/jadwal/book/<int:jadwal_id>/', views.booking_jadwal, name='booking_jadwal'),
    path('mahasiswa/jadwal/cancel/<int:booking_id>/',views.cancel_booking,name='cancel_booking'),
    
    # ===================== DOSEN CP =====================
    path('dosencp/', views.dosencp_home, name='dosencp_home'),
    path('dosencp/proposal/', views.dosencp_list_proposal, name='dosencp_list_proposal'),
    path('dosencp/proposal/<int:proposal_id>/', views.dosencp_detail_proposal, name='dosencp_detail_proposal'),
    path('dosencp/profile/', views.dosencp_profile, name='dosencp_profile'),

    # ===================== DOSEN PEMBIMBING =====================
    path('dosenpb/', views.dosenpb_home, name='dosenpb_home'),
    path('dosenpb/mahasiswa/', views.dosenpb_list_mahasiswa, name='dosenpb_list_mahasiswa'),
    path('dosenpb/mahasiswa/<int:id>/', views.dosenpb_detail_mahasiswa, name='dosenpb_detail_mahasiswa'),
    path('dosenpb/pengajuan/', views.dosenpb_pengajuan, name='dosenpb_pengajuan'),
    path('dosenpb/pengajuan/<int:id>/', views.dosenpb_detail_pengajuan, name='dosenpb_detail_pengajuan'),
    path('dosenpb/profile/', views.dosenpb_profile, name='dosenpb_profile'),
    path('dosenpb/schedule/', views.dosenpb_schedule, name='dosenpb_schedule'),
    path('dosenpb/schedule/delete/<int:id>/', views.dosenpb_hapus_jadwal, name='dosenpb_hapus_jadwal'),
    
    # ===================== KAPRODI =====================
    path('kaprodi/', views.kaprodi_home, name='kaprodi_home'),
    path('kaprodi/mahasiswa/', views.kaprodi_list_mahasiswa, name='kaprodi_mahasiswa'),
    path('kaprodi/mahasiswa/arsip-tahunan/', views.arsip_tahunan, name='arsip_tahunan'),
    path('kaprodi/mahasiswa/tambah/', views.tambah_mahasiswa, name='tambah_mahasiswa'),
    path('kaprodi/mahasiswa/<int:id>/', views.detail_mahasiswa, name='detail_mahasiswa'),
    path('kaprodi/mahasiswa/<int:id>/edit/', views.edit_mahasiswa, name='edit_mahasiswa'),
    path('kaprodi/mahasiswa/<int:id>/aktif/', views.aktifkan_mahasiswa, name='aktifkan_mahasiswa'),
    path('kaprodi/mahasiswa/<int:id>/nonaktif/', views.nonaktifkan_mahasiswa, name='nonaktifkan_mahasiswa'),
    path('kaprodi/dosen/tambah/', views.tambah_dosen, name='tambah_dosen'),
    path('kaprodi/dosen/<int:id>/edit/', views.edit_dosen, name='edit_dosen'),
    path('kaprodi/dospem/', views.kaprodi_manage_dospem, name='kaprodi_dospem'),
    path('kaprodi/dosen/', views.kaprodi_list_dosen, name='kaprodi_dosen'),
    path('kaprodi/dosen/<int:id>/aktif/', views.aktifkan_dosen, name='aktifkan_dosen'),
    path('kaprodi/dosen/<int:id>/nonaktif/', views.nonaktifkan_dosen, name='nonaktifkan_dosen'),
    path('kaprodi/tim/', views.kaprodi_list_tim, name='kaprodi_tim'),
    path('kaprodi/tim/<int:tim_id>/', views.kaprodi_detail_tim, name='kaprodi_detail_tim'),
    
    # PROPOSAL
    path('kaprodi/proposal/', views.kaprodi_list_proposal, name='kaprodi_proposal'),
    path('kaprodi/proposal/<int:proposal_id>/', views.kaprodi_detail_proposal, name='kaprodi_detail_proposal'),
    path('kaprodi/proposal/<int:proposal_id>/update/', views.kaprodi_update_proposal, name='kaprodi_update_proposal'),
    path('kaprodi/proposal/<int:proposal_id>/delete/', views.kaprodi_delete_proposal, name='kaprodi_delete_proposal'),
    
    path('kaprodi/monitoring/', views.kaprodi_monitoring, name='kaprodi_monitoring'),
    
    # RESUME
    path('kaprodi/resume/', views.kaprodi_list_resume, name='kaprodi_resume'),
    path('kaprodi/resume/<int:resume_id>/', views.kaprodi_detail_resume, name='kaprodi_detail_resume'),
    
    path('kaprodi/pengajuan/', views.kaprodi_pengajuan, name='kaprodi_pengajuan'),
    path('kaprodi/laporan/', views.kaprodi_laporan, name='kaprodi_laporan'),
    path('kaprodi/profile/', views.kaprodi_profile, name='kaprodi_profile'),
    path('kaprodi/arsip-mahasiswa/', views.arsip_mahasiswa, name='arsip_mahasiswa'),
    path("kaprodi/dosen-capstone/", views.kaprodi_dosen_cp, name="kaprodi_dosencp"),
    path("kaprodi/dospem/<int:id>/edit-batas/", views.edit_batas_dospem, name="edit_batas_dospem"),
    path("kaprodi/dosen/<int:id>/hapus/", views.hapus_dosen, name="hapus_dosen"),
    
    # UPLOAD MAHASISWA - PERBAIKI INI!
    path('kaprodi/upload-mahasiswa/', views.upload_mahasiswa_view, name='kaprodi_upload_mahasiswa'),
    path('kaprodi/upload-mahasiswa/process/', views.upload_mahasiswa_process, name='kaprodi_upload_mahasiswa_process'),
    path('kaprodi/download-template/', views.download_template_mahasiswa, name='kaprodi_download_template'),

    # ARSIP
    path('mahasiswa/kembalikan-arsip/<int:id>/', views.kembalikan_dari_arsip, name='kembalikan_dari_arsip'),
    path('mahasiswa/kembalikan-semua-arsip/', views.kembalikan_semua_arsip, name='kembalikan_semua_arsip'),

    # CHOOSE ROLE
    path('choose-role/', views.choose_role, name='choose_role'),

]