# views/dosenpb.py - FIX LENGKAP FINAL

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import F, Q
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from ..models import (
    Mahasiswa, DosenPembimbing, PengajuanDospem,
    JadwalKonsultasi, ProposalCapstone, Resume,
    RiwayatFeedbackProposal, RiwayatFeedbackResume,
)
from ..forms import JadwalForm
from .base import check_role, get_dosen_pb


# =========================================================
# 🔥 HELPER: HITUNG JUMLAH BIMBINGAN REAL-TIME
# =========================================================
def hitung_jumlah_bimbingan(dosen_pb):
    """
    Hit langsung dari PengajuanDospem yang DISETUJUI.
    Sumber kebenaran tunggal, tidak pakai property model.
    """
    return PengajuanDospem.objects.filter(
        dosen_pembimbing=dosen_pb,
        status='DISETUJUI'
    ).count()


def hitung_sisa_kuota(dosen_pb):
    terpakai = hitung_jumlah_bimbingan(dosen_pb)
    return max(0, dosen_pb.batas_bimbingan - terpakai)


def is_kuota_penuh(dosen_pb):
    return hitung_jumlah_bimbingan(dosen_pb) >= dosen_pb.batas_bimbingan


# =========================================================
# 🔥 HELPER: LEPASKAN MAHASISWA DARI DOSEN
# =========================================================
def lepaskan_mahasiswa(mahasiswa, dosen_pb):
    """
    Reset mahasiswa.dosen_pembimbing = None kalau nempel di dosen ini.
    Dipanggil saat tolak/revisi.
    """
    if not mahasiswa or not dosen_pb:
        return
    if mahasiswa.dosen_pembimbing_id == dosen_pb.id:
        mahasiswa.dosen_pembimbing = None
        mahasiswa.save(update_fields=['dosen_pembimbing'])


# =========================================================
# 🔥 HELPER: SYNC STATUS DOSEN (HIT REAL-TIME)
# =========================================================
def sync_status_dosen(dosen_pb):
    """
    Sinkronkan field status dosen (OPEN/FULL) berdasarkan hit real-time.
    """
    if dosen_pb.status == 'CLOSED':
        return
    
    disetujui = hitung_jumlah_bimbingan(dosen_pb)
    status_baru = 'FULL' if disetujui >= dosen_pb.batas_bimbingan else 'OPEN'
    
    if dosen_pb.status != status_baru:
        dosen_pb.status = status_baru
        dosen_pb.save(update_fields=['status'])


# =========================================================
# 🔥 HELPER: MAHASISWA BIMBINGAN (HANYA YANG DISETUJUI)
# =========================================================
def get_mahasiswa_bimbingan(dosen_pb):
    """
    Mahasiswa yang SUDAH DITERIMA.
    🔥 Relasi dari Mahasiswa ke PengajuanDospem = 'pengajuan_dospem'.
    """
    return Mahasiswa.objects.filter(
        dosen_pembimbing=dosen_pb,
        pengajuan_dospem__dosen_pembimbing=dosen_pb,   # ✅ pakai pengajuan_dospem
        pengajuan_dospem__status='DISETUJUI'           # ✅ pakai pengajuan_dospem
    ).select_related('user').distinct()


# =========================================================
# HELPER: PAGINATION
# =========================================================
def paginate_queryset(request, queryset, default_per_page=5):
    entries = request.GET.get('entries', str(default_per_page))

    if entries == 'all':
        class FakePaginator:
            def __init__(self, count):
                self.count = count
                self.num_pages = 1
                self.page_range = [1]
        class FakePage:
            def __init__(self, data):
                self.object_list = data
                self.paginator = FakePaginator(len(data))
                self.number = 1
                self.has_previous = False
                self.has_next = False
                self.has_other_pages = False
                self.previous_page_number = None
                self.next_page_number = None
                self.start_index = 1
                self.end_index = len(data)
            def __iter__(self):
                return iter(self.object_list)
        return FakePage(list(queryset)), entries

    try:
        per_page = int(entries)
        if per_page <= 0:
            per_page = default_per_page
    except (ValueError, TypeError):
        per_page = default_per_page

    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return page_obj, entries


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

    keyword = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    entries = request.GET.get('entries', '5')

    mahasiswa_list = get_mahasiswa_bimbingan(dosen_pb)

    if keyword:
        mahasiswa_list = mahasiswa_list.filter(
            Q(nim__icontains=keyword) |
            Q(user__first_name__icontains=keyword) |
            Q(user__last_name__icontains=keyword)
        )

    mahasiswa_list = mahasiswa_list.order_by('user__first_name')
    page_obj, entries = paginate_queryset(request, mahasiswa_list, default_per_page=5)

    today = timezone.localdate()
    jadwal_hari_ini = JadwalKonsultasi.objects.filter(
        dosen=dosen_pb, tanggal=today
    ).order_by('jam_mulai')
    jadwal_tersedia = sum(j.sisa_kuota for j in jadwal_hari_ini)

    total_pengajuan_menunggu = PengajuanDospem.objects.filter(
        dosen_pembimbing=dosen_pb, status='PENDING'
    ).count()

    jumlah_bimbingan_aktual = hitung_jumlah_bimbingan(dosen_pb)
    sisa_kuota_aktual = hitung_sisa_kuota(dosen_pb)

    context = {
        'page_obj': page_obj,
        'mahasiswa_list': page_obj,
        'keyword': keyword,
        'entries': entries,
        'status_filter': status_filter,
        'jumlah_mahasiswa': jumlah_bimbingan_aktual,
        'jadwal_hari_ini': jadwal_hari_ini,
        'jadwal_tersedia': jadwal_tersedia,
        'total_pengajuan_menunggu': total_pengajuan_menunggu,
        'jumlah_bimbingan': jumlah_bimbingan_aktual,
        'sisa_kuota': sisa_kuota_aktual,
        'kuota_penuh': is_kuota_penuh(dosen_pb),
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
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')

    query = request.GET.get('q', '')
    mahasiswa_list = get_mahasiswa_bimbingan(dosen_pb)

    if query:
        mahasiswa_list = mahasiswa_list.filter(
            Q(nim__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query)
        )

    mahasiswa_list = mahasiswa_list.order_by('user__first_name')
    page_obj, entries = paginate_queryset(request, mahasiswa_list, default_per_page=10)

    return render(request, 'dosenpb/list_mahasiswa.html', {
        'page_obj': page_obj,
        'mahasiswa_list': page_obj,
        'query': query,
        'entries': entries,
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
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')

    keyword = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    entries = request.GET.get('entries', '5')

    pengajuan_list = PengajuanDospem.objects.select_related(
        'mahasiswa__user', 'resume', 'dosen_pembimbing__dosen__user'
    ).filter(dosen_pembimbing=dosen_pb).order_by('-tanggal_pengajuan')

    if keyword:
        pengajuan_list = pengajuan_list.filter(
            Q(mahasiswa__user__first_name__icontains=keyword) |
            Q(mahasiswa__user__last_name__icontains=keyword) |
            Q(mahasiswa__nim__icontains=keyword)
        )

    if status_filter:
        pengajuan_list = pengajuan_list.filter(status=status_filter)

    page_obj, entries = paginate_queryset(request, pengajuan_list, default_per_page=5)

    context = {
        'page_obj': page_obj,
        'keyword': keyword,
        'status_filter': status_filter,
        'entries': entries,
        'jumlah_bimbingan': hitung_jumlah_bimbingan(dosen_pb),
        'sisa_kuota': hitung_sisa_kuota(dosen_pb),
        'kuota_penuh': is_kuota_penuh(dosen_pb),
    }
    return render(request, 'dosenpb/pengajuan.html', context)


# =========================================================
# DETAIL MAHASISWA
# =========================================================
@login_required
def dosenpb_detail_mahasiswa(request, id):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response

    dosen_pb = get_dosen_pb(request.user)
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')

    mahasiswa = get_object_or_404(get_mahasiswa_bimbingan(dosen_pb), id=id)

    pengajuan = PengajuanDospem.objects.filter(
        mahasiswa=mahasiswa,
        dosen_pembimbing=dosen_pb,
        status='DISETUJUI'
    ).select_related('resume').first()

    resume = pengajuan.resume if pengajuan else None
    proposal = None
    try:
        proposal = resume.proposal if resume else None
    except AttributeError:
        proposal = None

    return render(request, 'dosenpb/detail_mahasiswa.html', {
        'mahasiswa': mahasiswa,
        'pengajuan': pengajuan,
        'resume': resume,
        'proposal': proposal,
    })


# =========================================================
# DETAIL PENGAJUAN (REVIEW)
# =========================================================
@login_required
def dosenpb_detail_pengajuan(request, id):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response

    dosen_pb = get_dosen_pb(request.user)
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')

    pengajuan = get_object_or_404(
        PengajuanDospem.objects.select_related('mahasiswa__user', 'resume'),
        id=id,
        dosen_pembimbing=dosen_pb
    )

    mahasiswa = pengajuan.mahasiswa
    resume = pengajuan.resume
    proposal = None
    try:
        proposal = resume.proposal if resume else None
    except AttributeError:
        proposal = None

    if request.method == 'POST':
        aksi = request.POST.get('aksi')
        catatan = request.POST.get('catatan', '').strip()

        if aksi in ['tolak', 'revisi'] and not catatan:
            messages.error(request, f"Catatan wajib diisi untuk {aksi}!")
            return redirect(request.path)

        # 🔥 VALIDASI KUOTA
        if aksi == 'setujui':
            jumlah_disetujui = hitung_jumlah_bimbingan(dosen_pb)

            if jumlah_disetujui >= dosen_pb.batas_bimbingan:
                messages.error(
                    request,
                    f"Kuota bimbingan penuh! "
                    f"({jumlah_disetujui}/{dosen_pb.batas_bimbingan} mahasiswa). "
                    f"Anda tidak dapat menyetujui pengajuan baru."
                )
                return redirect(request.path)

        # =========================================================
        # AKSI: SETUJUI
        # =========================================================
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
            mahasiswa.save(update_fields=['dosen_pembimbing'])

            sync_status_dosen(dosen_pb)

            jumlah_baru = hitung_jumlah_bimbingan(dosen_pb)
            messages.success(
                request,
                f"Mahasiswa {mahasiswa.user.get_full_name()} berhasil disetujui! "
                f"Slot terpakai: {jumlah_baru}/{dosen_pb.batas_bimbingan}"
            )

        # =========================================================
        # AKSI: TOLAK
        # =========================================================
        elif aksi == 'tolak':
            lepaskan_mahasiswa(mahasiswa, dosen_pb)

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

            sync_status_dosen(dosen_pb)
            jumlah_baru = hitung_jumlah_bimbingan(dosen_pb)
            messages.warning(
                request,
                f"Pengajuan dari {mahasiswa.user.get_full_name()} ditolak! "
                f"Slot terpakai: {jumlah_baru}/{dosen_pb.batas_bimbingan}"
            )

        # =========================================================
        # AKSI: REVISI
        # =========================================================
        elif aksi == 'revisi':
            lepaskan_mahasiswa(mahasiswa, dosen_pb)

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

            sync_status_dosen(dosen_pb)
            jumlah_baru = hitung_jumlah_bimbingan(dosen_pb)
            messages.info(
                request,
                f"Revisi diminta untuk {mahasiswa.user.get_full_name()}! "
                f"Slot terpakai: {jumlah_baru}/{dosen_pb.batas_bimbingan}"
            )

        pengajuan.save()
        return redirect('capstone_system:dosenpb_pengajuan')

    jumlah_disetujui = hitung_jumlah_bimbingan(dosen_pb)
    sisa_kuota = max(0, dosen_pb.batas_bimbingan - jumlah_disetujui)
    is_kuota_penuh_now = jumlah_disetujui >= dosen_pb.batas_bimbingan

    return render(request, 'dosenpb/detail_pengajuan.html', {
        'mahasiswa': mahasiswa,
        'pengajuan': pengajuan,
        'resume': resume,
        'proposal': proposal,
        'dosen_pb': dosen_pb,
        'sisa_kuota': sisa_kuota,
        'kuota_penuh': is_kuota_penuh_now,
        'jumlah_disetujui': jumlah_disetujui,
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
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')

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
        'jumlah_bimbingan': hitung_jumlah_bimbingan(dosen_pb),
        'sisa_kuota': hitung_sisa_kuota(dosen_pb),
    })


# =========================================================
# JADWAL KONSULTASI
# =========================================================
@login_required
def dosenpb_schedule(request):
    has_access, response = check_role(request, ['DOSENPB'])
    if not has_access:
        return response

    dosen_pb = get_dosen_pb(request.user)
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')

    if request.method == 'POST':
        tanggal = request.POST.get('tanggal')
        jam_mulai = request.POST.get('jam_mulai')
        jam_selesai = request.POST.get('jam_selesai')

        if not tanggal or not jam_mulai or not jam_selesai:
            messages.error(request, "Semua field wajib diisi!")
            return redirect('capstone_system:dosenpb_schedule')

        existing = JadwalKonsultasi.objects.filter(
            dosen=dosen_pb, tanggal=tanggal,
            jam_mulai=jam_mulai, jam_selesai=jam_selesai
        ).exists()

        if existing:
            messages.error(request, f"Jadwal pada tanggal {tanggal} jam {jam_mulai}-{jam_selesai} sudah ada!")
        else:
            JadwalKonsultasi.objects.create(
                dosen=dosen_pb, tanggal=tanggal,
                jam_mulai=jam_mulai, jam_selesai=jam_selesai,
                kuota=3, jumlah_dipesan=0
            )
            messages.success(request, f"Jadwal {tanggal} {jam_mulai}-{jam_selesai} berhasil ditambahkan!")

        return redirect('capstone_system:dosenpb_schedule')

    keyword = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    entries = request.GET.get('entries', '5')

    jadwal_list = JadwalKonsultasi.objects.filter(dosen=dosen_pb).order_by('tanggal', 'jam_mulai')

    if keyword:
        jadwal_list = jadwal_list.filter(Q(tanggal__icontains=keyword))

    if status_filter == 'tersedia':
        jadwal_list = jadwal_list.filter(kuota__gt=F('jumlah_dipesan'))
    elif status_filter == 'penuh':
        jadwal_list = jadwal_list.filter(kuota__lte=F('jumlah_dipesan'))

    page_obj, entries = paginate_queryset(request, jadwal_list, default_per_page=5)

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
    if not dosen_pb:
        messages.error(request, "Anda belum terdaftar sebagai Dosen Pembimbing.")
        return redirect('capstone_system:login')

    jadwal = get_object_or_404(JadwalKonsultasi, id=id, dosen=dosen_pb)
    info = f"{jadwal.tanggal} {jadwal.jam_mulai}-{jadwal.jam_selesai}"
    jadwal.delete()

    messages.success(request, f"Jadwal {info} berhasil dihapus")
    return redirect('capstone_system:dosenpb_schedule')