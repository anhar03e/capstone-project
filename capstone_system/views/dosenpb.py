# views/dosenpb.py - PERBAIKI LENGKAP

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from ..models import (
    Mahasiswa,
    DosenPembimbing,
    PengajuanDospem,
    JadwalKonsultasi,
    ProposalCapstone,
    Resume,
    RiwayatFeedbackProposal,
    RiwayatFeedbackResume,
)
from ..forms import JadwalForm
from .base import check_role, get_dosen_pb

# =========================================================
# DASHBOARD DOSEN PEMBIMBING
# =========================================================
@login_required
def dosenpb_home(request):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response
    
    dosen_pb = get_dosen_pb(request.user)
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')

    # =========================================================
    # AMBIL PARAMETER FILTER
    # =========================================================
    keyword = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    entries = request.GET.get('entries', '5')

    # =========================================================
    # DATA MAHASISWA BIMBINGAN
    # =========================================================
    mahasiswa_list = Mahasiswa.objects.filter(
        dosen_pembimbing=dosen_pb,
        status='AKTIF'
    ).select_related('user')

    # Filter keyword
    if keyword:
        mahasiswa_list = mahasiswa_list.filter(
            Q(nim__icontains=keyword) |
            Q(user__first_name__icontains=keyword) |
            Q(user__last_name__icontains=keyword)
        )

    mahasiswa_list = mahasiswa_list.order_by('user__first_name')

    # =========================================================
    # PAGINATION
    # =========================================================
    if entries == 'all':
        per_page = None
    else:
        try:
            per_page = int(entries)
            if per_page <= 0:
                per_page = 5
        except ValueError:
            per_page = 5

    if per_page is None:
        class FakePaginator:
            count = mahasiswa_list.count()
            num_pages = 1
            page_range = [1]
        class FakePage:
            def __init__(self, data):
                self.object_list = data
                self.paginator = FakePaginator()
                self.number = 1
                self.has_previous = False
                self.has_next = False
                self.previous_page_number = None
                self.next_page_number = None
                self.start_index = 1
                self.end_index = len(data)
            def __iter__(self):
                return iter(self.object_list)
        page_obj = FakePage(mahasiswa_list)
    else:
        paginator = Paginator(mahasiswa_list, per_page)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

    # =========================================================
    # DATA JADWAL HARI INI
    # =========================================================
    today = timezone.localdate()
    jadwal_hari_ini = JadwalKonsultasi.objects.filter(
        dosen=dosen_pb, 
        tanggal=today
    ).order_by('jam_mulai')
    jadwal_tersedia = sum(j.sisa_kuota for j in jadwal_hari_ini)

    # =========================================================
    # KIRIM KE TEMPLATE
    # =========================================================
    context = {
        'page_obj': page_obj,           # 🔥 PENTING: untuk pagination
        'keyword': keyword,             # 🔥 PENTING: untuk filter
        'entries': entries,             # 🔥 PENTING: untuk show entries
        'status_filter': status_filter, # 🔥 PENTING: untuk filter status
        'jumlah_mahasiswa': mahasiswa_list.count(),
        'jadwal_hari_ini': jadwal_hari_ini,
        'jadwal_tersedia': jadwal_tersedia,
    }

    return render(request, 'dosenpb/home.html', context)


# =========================================================
# LIST MAHASISWA BIMBINGAN
# =========================================================
@login_required
def dosenpb_list_mahasiswa(request):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response
    
    dosen_pb = get_dosen_pb(request.user)
    mahasiswa_list = Mahasiswa.objects.filter(dosen_pembimbing=dosen_pb)

    query = request.GET.get('q')
    if query:
        mahasiswa_list = mahasiswa_list.filter(
            Q(nim__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query)
        )

    return render(request, 'dosenpb/list_mahasiswa.html', {
        'mahasiswa_list': mahasiswa_list,
        'query': query
    })

# =========================================================
# LIST PENGAJUAN DOSPEM
# =========================================================
@login_required
def dosenpb_pengajuan(request):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response
    
    dosen_pb = get_dosen_pb(request.user)
    
    keyword = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    entries = request.GET.get('entries', '5')

    pengajuan_list = PengajuanDospem.objects.select_related(
        'mahasiswa__user', 'resume', 'dosen_pembimbing__dosen__user'
    ).filter(dosen_pembimbing=dosen_pb).order_by('-tanggal_pengajuan')

    # Filter keyword
    if keyword:
        pengajuan_list = pengajuan_list.filter(
            Q(mahasiswa__user__first_name__icontains=keyword) |
            Q(mahasiswa__user__last_name__icontains=keyword) |
            Q(mahasiswa__nim__icontains=keyword)
        )

    # Filter status
    if status_filter:
        pengajuan_list = pengajuan_list.filter(status=status_filter)

    # 🔥 PAGINATION
    if entries == 'all':
        per_page = None
    else:
        try:
            per_page = int(entries)
            if per_page <= 0:
                per_page = 5
        except ValueError:
            per_page = 5

    if per_page is None:
        class FakePaginator:
            count = pengajuan_list.count()
            num_pages = 1
            page_range = [1]
        class FakePage:
            def __init__(self, data):
                self.object_list = data
                self.paginator = FakePaginator()
                self.number = 1
                self.has_previous = False
                self.has_next = False
                self.previous_page_number = None
                self.next_page_number = None
                self.start_index = 1
                self.end_index = len(data)
            def __iter__(self):
                return iter(self.object_list)
        page_obj = FakePage(pengajuan_list)
    else:
        paginator = Paginator(pengajuan_list, per_page)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'keyword': keyword,
        'status_filter': status_filter,
        'entries': entries,
    }

    return render(request, 'dosenpb/pengajuan.html', context)

# =========================================================
# DETAIL MAHASISWA (DARI MENU MAHASISWA)
# =========================================================
@login_required
def dosenpb_detail_mahasiswa(request, id):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response
    
    dosen_pb = get_dosen_pb(request.user)
    mahasiswa = get_object_or_404(
        Mahasiswa.objects.select_related('user'),
        id=id,
        dosen_pembimbing=dosen_pb
    )

    pengajuan = PengajuanDospem.objects.filter(
        mahasiswa=mahasiswa, dosen_pembimbing=dosen_pb
    ).select_related('resume').first()
    resume = pengajuan.resume if pengajuan else None

    return render(request, 'dosenpb/detail_mahasiswa.html', {
        'mahasiswa': mahasiswa,
        'pengajuan': pengajuan,
        'resume': resume
    })

# =========================================================
# DETAIL PENGAJUAN DOSEN PEMBIMBING (DIPERBAIKI)
# =========================================================
@login_required
def dosenpb_detail_pengajuan(request, id):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response
    
    dosen_pb = get_dosen_pb(request.user)
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')  # <-- PERBAIKI INI!

    pengajuan = get_object_or_404(
        PengajuanDospem.objects.select_related('mahasiswa__user', 'resume', 'resume__proposal'),
        id=id,
        dosen_pembimbing=dosen_pb
    )

    mahasiswa = pengajuan.mahasiswa
    resume = pengajuan.resume
    proposal = resume.proposal if resume else None

    if request.method == 'POST':
        aksi = request.POST.get('aksi')
        catatan = request.POST.get('catatan', '').strip()
        status_sekarang = pengajuan.status

        if aksi in ['tolak', 'revisi'] and not catatan:
            messages.error(request, f"Catatan wajib diisi untuk {aksi}!")
            return redirect(request.path)

        if aksi == 'setujui':
            if dosen_pb.jumlah_bimbingan >= dosen_pb.batas_bimbingan:
                messages.error(request, f"Kuota bimbingan penuh! (Maksimal {dosen_pb.batas_bimbingan} mahasiswa)")
                return redirect(request.path)

        if aksi == 'setujui':
            pengajuan.status = 'DISETUJUI'
            pengajuan.catatan_dosen = catatan
            pengajuan.sudah_direview = True
            pengajuan.waktu_direview = timezone.now()

            if proposal:
                proposal.status_pb = 'DITERIMA'
                proposal.catatan_pb = catatan
                proposal.tanggal_review_pb = timezone.now()
                proposal.save()
                RiwayatFeedbackProposal.objects.create(
                    proposal=proposal, reviewer='PB', dosen=dosen_pb.dosen,
                    status='DITERIMA', catatan=catatan
                )

            if resume:
                resume.status = 'DISETUJUI'
                resume.waktu_peninjauan = timezone.now()
                resume.save()
                RiwayatFeedbackResume.objects.create(
                    resume=resume, dosen=dosen_pb.dosen,
                    status='DISETUJUI', catatan=catatan
                )

            mahasiswa.dosen_pembimbing = dosen_pb
            mahasiswa.save()
            dosen_pb.update_status()
            messages.success(request, f"Mahasiswa {mahasiswa.user.get_full_name()} berhasil disetujui!")

        elif aksi == 'tolak':
            if status_sekarang == 'DISETUJUI':
                mahasiswa.dosen_pembimbing = None
                mahasiswa.save()

            pengajuan.status = 'DITOLAK'
            pengajuan.catatan_dosen = catatan
            pengajuan.sudah_direview = True
            pengajuan.waktu_direview = timezone.now()

            if proposal:
                proposal.status_pb = 'DITOLAK'
                proposal.catatan_pb = catatan
                proposal.tanggal_review_pb = timezone.now()
                proposal.save()
                RiwayatFeedbackProposal.objects.create(
                    proposal=proposal, reviewer='PB', dosen=dosen_pb.dosen,
                    status='DITOLAK', catatan=catatan
                )

            if resume:
                resume.status = 'DITOLAK'
                resume.catatan_revisi = catatan
                resume.waktu_peninjauan = timezone.now()
                resume.save()
                RiwayatFeedbackResume.objects.create(
                    resume=resume, dosen=dosen_pb.dosen,
                    status='DITOLAK', catatan=catatan
                )

            dosen_pb.update_status()
            messages.warning(request, f"Pengajuan dari {mahasiswa.user.get_full_name()} ditolak!")

        elif aksi == 'revisi':
            if status_sekarang == 'DISETUJUI':
                mahasiswa.dosen_pembimbing = None
                mahasiswa.save()

            pengajuan.status = 'REVISI'
            pengajuan.catatan_dosen = catatan
            pengajuan.sudah_direview = True
            pengajuan.waktu_direview = timezone.now()
            
            if proposal:
                proposal.status_pb = 'REVISI'
                proposal.catatan_pb = catatan
                proposal.tanggal_review_pb = timezone.now()
                proposal.save()
                RiwayatFeedbackProposal.objects.create(
                    proposal=proposal, reviewer='PB', dosen=dosen_pb.dosen,
                    status='REVISI', catatan=catatan
                )

            if resume:
                resume.status = 'REVISI'
                resume.catatan_revisi = catatan
                resume.waktu_peninjauan = timezone.now()
                resume.save()
                RiwayatFeedbackResume.objects.create(
                    resume=resume, dosen=dosen_pb.dosen,
                    status='REVISI', catatan=catatan
                )

            dosen_pb.update_status()
            messages.info(request, f"Revisi diminta untuk {mahasiswa.user.get_full_name()}!")

        pengajuan.save()
        return redirect('capstone_system:dosenpb_pengajuan')

    return render(request, 'dosenpb/detail_pengajuan.html', {
        'mahasiswa': mahasiswa,
        'pengajuan': pengajuan,
        'resume': resume,
        'proposal': proposal
    })

# =========================================================
# PROFILE DOSEN PEMBIMBING
# =========================================================
@login_required
def dosenpb_profile(request):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response
    
    dosen_pb = get_dosen_pb(request.user)
    dosen = dosen_pb.dosen
    user = request.user

    if request.method == 'POST':
        user.email = request.POST.get('email', '').strip()
        password = request.POST.get('password')
        if password:
            user.set_password(password)
            update_session_auth_hash(request, user)
        user.save()

        if request.FILES.get('foto_profil'):
            dosen.foto_profil = request.FILES['foto_profil']
            dosen.save()

        messages.success(request, "Profil berhasil diperbarui.")
        return redirect('capstone_system:dosenpb_profile')

    return render(request, 'dosenpb/profile.html', {
        'dosen': dosen,
        'user': user,
    })

# =========================================================
# JADWAL KONSULTASI
# =========================================================
# dosenpb.py - Perbaiki fungsi dosenpb_schedule

@login_required
def dosenpb_schedule(request):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response
    
    dosen_pb = get_dosen_pb(request.user)

    # 🔥 PROSES POST (TAMBAH JADWAL)
    if request.method == 'POST':
        tanggal = request.POST.get('tanggal')
        jam_mulai = request.POST.get('jam_mulai')
        jam_selesai = request.POST.get('jam_selesai')
        
        # 🔥 CEK SEMUA FIELD WAJIB DIISI
        if not tanggal or not jam_mulai or not jam_selesai:
            messages.error(request, "Semua field wajib diisi!")
            return redirect('capstone_system:dosenpb_schedule')
        
        # 🔥 CEK APAKAH JADWAL SUDAH ADA
        existing = JadwalKonsultasi.objects.filter(
            dosen=dosen_pb,
            tanggal=tanggal,
            jam_mulai=jam_mulai,
            jam_selesai=jam_selesai
        ).exists()
        
        if existing:
            messages.error(request, f"Jadwal pada tanggal {tanggal} jam {jam_mulai}-{jam_selesai} sudah ada!")
        else:
            # 🔥 BUAT JADWAL BARU
            JadwalKonsultasi.objects.create(
                dosen=dosen_pb,
                tanggal=tanggal,
                jam_mulai=jam_mulai,
                jam_selesai=jam_selesai,
                kuota=3,  # Default kuota 3
                jumlah_dipesan=0
            )
            messages.success(request, f"Jadwal {tanggal} {jam_mulai}-{jam_selesai} berhasil ditambahkan!")
        
        return redirect('capstone_system:dosenpb_schedule')

    # 🔥 AMBIL PARAMETER FILTER
    keyword = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    entries = request.GET.get('entries', '5')

    # 🔥 QUERY JADWAL
    jadwal_list = JadwalKonsultasi.objects.filter(dosen=dosen_pb).order_by('tanggal', 'jam_mulai')

    # Filter keyword (cari tanggal)
    if keyword:
        jadwal_list = jadwal_list.filter(
            Q(tanggal__icontains=keyword)
        )

    # Filter status (tersedia/penuh)
    if status_filter == 'tersedia':
        jadwal_list = jadwal_list.filter(kuota__gt=F('jumlah_dipesan'))
    elif status_filter == 'penuh':
        jadwal_list = jadwal_list.filter(kuota__lte=F('jumlah_dipesan'))

    # 🔥 PAGINATION
    if entries == 'all':
        per_page = None
    else:
        try:
            per_page = int(entries)
            if per_page <= 0:
                per_page = 5
        except ValueError:
            per_page = 5

    if per_page is None:
        class FakePaginator:
            count = jadwal_list.count()
            num_pages = 1
            page_range = [1]
        class FakePage:
            def __init__(self, data):
                self.object_list = data
                self.paginator = FakePaginator()
                self.number = 1
                self.has_previous = False
                self.has_next = False
                self.previous_page_number = None
                self.next_page_number = None
                self.start_index = 1
                self.end_index = len(data)
            def __iter__(self):
                return iter(self.object_list)
        page_obj = FakePage(jadwal_list)
    else:
        paginator = Paginator(jadwal_list, per_page)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'keyword': keyword,
        'status_filter': status_filter,
        'entries': entries,
    }

    return render(request, 'dosenpb/schedule.html', context)

# =========================================================
# HAPUS JADWAL
# =========================================================
@login_required
def dosenpb_hapus_jadwal(request, id):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response
    
    dosen_pb = get_dosen_pb(request.user)
    jadwal = get_object_or_404(JadwalKonsultasi, id=id, dosen=dosen_pb)
    
    # Simpan info untuk pesan
    info = f"{jadwal.tanggal} {jadwal.jam_mulai}-{jadwal.jam_selesai}"
    
    jadwal.delete()

    messages.success(request, f"Jadwal {info} berhasil dihapus")
    return redirect('capstone_system:dosenpb_schedule')