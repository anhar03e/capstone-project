from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
import os  # <-- PERUBAHAN: Tambahkan import os

from ..models import (
    Mahasiswa,
    DosenPembimbing,
    Tim,
    AnggotaTim,
    ProposalCapstone,
    Resume,
    PengajuanDospem,
    JadwalKonsultasi,
    BookingJadwal,
    RiwayatFeedbackProposal,
    RiwayatFeedbackResume,
)
from ..forms import ProposalForm, ResumeForm
from .base import check_role, get_tim_user, get_proposal_ketua


# =========================================================
# FUNGSI VALIDASI FILE PDF
# =========================================================
def validate_pdf_file_size(file):
    """
    Validasi file harus PDF dan maksimal 10MB
    """
    if file:
        ext = os.path.splitext(file.name)[1].lower()
        if ext != '.pdf':
            raise ValueError('Hanya file PDF yang diperbolehkan.')
        if file.size > 10 * 1024 * 1024:  # 10MB
            raise ValueError('Ukuran file maksimal 10MB.')


# =========================================================
# MAHASISWA HOME
# =========================================================
@login_required
def mahasiswa_home(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response
    
    mahasiswa = get_object_or_404(Mahasiswa, user=request.user)

    anggota = get_tim_user(mahasiswa)
    tim = anggota.tim if anggota else None

    tim_list = Tim.objects.filter(anggota__mahasiswa=mahasiswa).distinct()

    # =========================================================
    # Ambil anggota tim dengan status lengkap
    # =========================================================
    anggota_tim = []
    if tim:
        anggota_tim = AnggotaTim.objects.select_related(
            'mahasiswa__user'
        ).filter(tim=tim)

    proposal = None
    if anggota and anggota.role == 'ketua':
        proposal = ProposalCapstone.objects.filter(tim=tim).first()
    if proposal and not proposal.file:
        proposal = None

    resume = Resume.objects.filter(mahasiswa=mahasiswa).first()
    if resume and not getattr(resume, "file_resume", None):
        resume = None

    pengajuan = PengajuanDospem.objects.filter(
        mahasiswa=mahasiswa
    ).select_related('dosen_pembimbing__dosen__user').first()

    dosen_pembimbing = None
    if pengajuan and pengajuan.dosen_pembimbing:
        dosen_pembimbing = pengajuan.dosen_pembimbing.dosen.user.get_full_name()

    mahasiswa_list = Mahasiswa.objects.exclude(user=request.user)

    # =========================================================
    # Update status tim jika semua anggota sudah APPROVED
    # =========================================================
    if tim and tim.status == 'PENDING':
        ada_pending = tim.anggota.filter(status_persetujuan='PENDING').exists()
        if not ada_pending:
            tim.status = 'APPROVED'
            tim.save()

    return render(request, 'mahasiswa/home.html', {
        'anggota': anggota,
        'tim': tim,
        'tim_list': tim_list,
        'anggota_tim': anggota_tim,
        'proposal': proposal,
        'resume': resume,
        'pengajuan': pengajuan,
        'dosen_pembimbing': dosen_pembimbing,
        'mahasiswa_list': mahasiswa_list,
        'me': mahasiswa,
    })


# =========================================================
# TRACKING STATUS (FUNGSI BARU)
# =========================================================
@login_required
def tracking_status(request):
    """
    Halaman tracking status untuk mahasiswa
    Menampilkan status proposal, resume, dan pengajuan dospem
    """
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, user=request.user)

    # =========================================================
    # Ambil Proposal
    # =========================================================
    proposal = None
    anggota = get_tim_user(mahasiswa)
    if anggota and anggota.role == 'ketua':
        tim = anggota.tim
        proposal = ProposalCapstone.objects.filter(tim=tim).first()

    # =========================================================
    # Ambil Resume
    # =========================================================
    resume = Resume.objects.filter(mahasiswa=mahasiswa).order_by('-waktu_pengajuan').first()

    # =========================================================
    # Ambil Pengajuan Dospem
    # =========================================================
    pengajuan = PengajuanDospem.objects.filter(mahasiswa=mahasiswa).first()

    # =========================================================
    # STATUS PROPOSAL - menggunakan status_cp
    # =========================================================
    status_proposal = {
        'status': proposal.status_cp if proposal else None,
        'display': proposal.get_status_cp_display() if proposal else 'BELUM UPLOAD',
        'is_uploaded': proposal is not None,
        'is_diterima': proposal.status_cp == 'DITERIMA' if proposal else False,
        'is_ditolak': proposal.status_cp == 'DITOLAK' if proposal else False,
        'is_revisi': proposal.status_cp == 'REVISI' if proposal else False,
        'is_belum': proposal.status_cp == 'BELUM_REVIEW' if proposal else True,
        'is_sedang': proposal.status_cp == 'SEDANG_REVIEW' if proposal else False,
        'catatan': proposal.catatan_cp if proposal else None,
        'tanggal_review': proposal.tanggal_review_cp if proposal else None,
    }

    # =========================================================
    # STATUS RESUME
    # =========================================================
    status_resume = {
        'status': resume.status if resume else None,
        'display': resume.get_status_display() if resume else 'BELUM UPLOAD',
        'is_uploaded': resume is not None,
        'is_disetujui': resume.status == 'DISETUJUI' if resume else False,
        'is_ditolak': resume.status == 'DITOLAK' if resume else False,
        'is_revisi': resume.status == 'REVISI' if resume else False,
        'is_belum': resume.status == 'BELUM_REVIEW' if resume else True,
        'catatan': resume.catatan_revisi if resume else None,
    }

    # =========================================================
    # STATUS PENGAJUAN DOSPEM
    # =========================================================
    status_pengajuan = {
        'is_uploaded': pengajuan is not None,
        'status': pengajuan.status if pengajuan else None,
        'display': pengajuan.get_status_display() if pengajuan else 'BELUM MENGAJUKAN',
        'is_pending': pengajuan.status == 'PENDING' if pengajuan else False,
        'is_disetujui': pengajuan.status == 'DISETUJUI' if pengajuan else False,
        'is_ditolak': pengajuan.status == 'DITOLAK' if pengajuan else False,
        'is_revisi': pengajuan.status == 'REVISI' if pengajuan else False,
        'catatan': pengajuan.catatan_dosen if pengajuan else None,
        'dosen': pengajuan.dosen_pembimbing.dosen.user.get_full_name() if pengajuan and pengajuan.dosen_pembimbing else None,
    }

    # =========================================================
    # RIWAYAT FEEDBACK
    # =========================================================
    riwayat_cp = []
    riwayat_pb = []
    riwayat_resume = []

    if proposal:
        riwayat_cp = RiwayatFeedbackProposal.objects.filter(
            proposal=proposal, reviewer='CP'
        ).order_by('-created_at')[:5]
        riwayat_pb = RiwayatFeedbackProposal.objects.filter(
            proposal=proposal, reviewer='PB'
        ).order_by('-created_at')[:5]

    if resume:
        riwayat_resume = RiwayatFeedbackResume.objects.filter(
            resume=resume
        ).order_by('-created_at')[:5]

    context = {
        'mahasiswa': mahasiswa,
        'proposal': proposal,
        'resume': resume,
        'pengajuan': pengajuan,
        'status_proposal': status_proposal,
        'status_resume': status_resume,
        'status_pengajuan': status_pengajuan,
        'riwayat_cp': riwayat_cp,
        'riwayat_pb': riwayat_pb,
        'riwayat_resume': riwayat_resume,
    }

    return render(request, 'mahasiswa/tracking_status.html', context)


# =========================================================
# UPLOAD PROPOSAL (DIPERBAIKI - TAMBAH VALIDASI FILE)
# =========================================================
@login_required
def upload_proposal(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, user=request.user)
    anggota = get_tim_user(mahasiswa)

    if not anggota:
        messages.error(request, "Kamu belum memiliki tim.")
        return redirect('capstone_system:mahasiswa_home')

    if anggota.role != "ketua":
        messages.error(request, "Hanya ketua tim yang dapat mengelola proposal.")
        return redirect('capstone_system:mahasiswa_home')

    tim = anggota.tim

    anggota_belum_setuju = tim.anggota.filter(status_persetujuan='PENDING').exists()
    if anggota_belum_setuju:
        messages.error(request, "Masih ada anggota tim yang belum menyetujui undangan.")
        return redirect('capstone_system:mahasiswa_home')

    proposal = ProposalCapstone.objects.filter(tim=tim).first()
    edit_mode = request.GET.get("edit")
    
    proposal_locked = (
        proposal is not None and
        proposal.status_cp in ["DITERIMA", "SEDANG_REVIEW"]
    )

    if request.method == "POST":
        if proposal_locked:
            messages.warning(request, "Proposal sedang direview atau telah disetujui sehingga tidak dapat diubah.")
            return redirect("capstone_system:upload_proposal")

        # =========================================================
        # 🔥 VALIDASI FILE SEBELUM FORM VALIDASI
        # =========================================================
        if request.FILES.get('file'):
            try:
                validate_pdf_file_size(request.FILES.get('file'))
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('capstone_system:upload_proposal')

        form = ProposalForm(request.POST, request.FILES, instance=proposal)
        
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tim = tim

            if proposal and not request.FILES.get("file"):
                obj.file = proposal.file

            if request.FILES.get("file"):
                obj.status_cp = "BELUM_REVIEW"
                obj.catatan_cp = ""
                obj.waktu_peninjauan = None
                obj.status_pb = "BELUM_REVIEW"
                obj.catatan_pb = ""

            obj.save()
            messages.success(request, "Proposal berhasil disimpan.")
            return redirect("capstone_system:upload_proposal")
        else:
            messages.error(request, "Form tidak valid. Silakan periksa kembali.")
    else:
        form = ProposalForm(instance=proposal)

    anggota_detail = [
        {
            "nim": a.mahasiswa.nim,
            "nama": a.mahasiswa.user.get_full_name(),
            "role": a.role,
            "status": a.status_persetujuan,
        }
        for a in tim.anggota.select_related("mahasiswa__user")
    ]

    return render(request, "mahasiswa/upload_proposal.html", {
        "proposal": proposal,
        "form": form,
        "anggota_detail": anggota_detail,
        "edit_mode": edit_mode,
        "tim": tim,
        "proposal_locked": proposal_locked,
    })


# =========================================================
# UPLOAD RESUME (DIPERBAIKI - TAMBAH VALIDASI FILE)
# =========================================================
@login_required
def upload_resume(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, user=request.user)
    proposal = get_proposal_ketua(mahasiswa)

    if not proposal or not proposal.file:
        messages.error(request, "Silakan upload proposal terlebih dahulu.")
        return redirect('capstone_system:mahasiswa_home')
    
    if not proposal.status_cp or proposal.status_cp != 'DITERIMA':
        messages.error(request, "Resume belum bisa diakses sebelum Review CP selesai (DITERIMA).")
        return redirect('capstone_system:mahasiswa_home')

    resume = Resume.objects.filter(mahasiswa=mahasiswa).first()
    edit_mode = request.GET.get('edit')
    dosen_list = DosenPembimbing.objects.filter(status='OPEN').select_related('dosen__user')

    if request.method == 'POST':
        # =========================================================
        # 🔥 VALIDASI FILE SEBELUM FORM VALIDASI
        # =========================================================
        if request.FILES.get('file_resume'):
            try:
                validate_pdf_file_size(request.FILES.get('file_resume'))
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('capstone_system:upload_resume')

        form = ResumeForm(request.POST, request.FILES, instance=resume)
        dosen_id = request.POST.get('dosen_pembimbing')

        if form.is_valid():
            res = form.save(commit=False)
            res.status = "BELUM_REVIEW"
            res.catatan_revisi = ""
            res.mahasiswa = mahasiswa
            res.proposal = proposal
            res.judul_proposal = proposal.judul
            res.mitra = proposal.mitra

            if resume:
                res.status = "BELUM_REVIEW"
                res.waktu_peninjauan = None
                res.catatan_revisi = ""

            if resume and not request.FILES.get('file_resume'):
                res.file_resume = resume.file_resume

            res.save()

            proposal.status_pb = "BELUM_REVIEW"
            proposal.catatan_pb = ""
            proposal.save()

            if dosen_id:
                PengajuanDospem.objects.update_or_create(
                    mahasiswa=mahasiswa,
                    defaults={
                        'resume': res,
                        'dosen_pembimbing_id': dosen_id,
                        'surat_permohonan_dospem': res.file_resume,
                        'status': 'PENDING',
                        'sudah_direview': False,
                        'waktu_direview': None,
                        'catatan_dosen': '',
                    }
                )

            messages.success(request, "Resume berhasil disimpan.")
            return redirect('capstone_system:upload_resume')
        else:
            messages.error(request, "Form tidak valid. Silakan periksa kembali.")
    else:
        form = ResumeForm(instance=resume)

    return render(request, 'mahasiswa/upload_resume.html', {
        'form': form,
        'resume': resume,
        'proposal': proposal,
        'dosen_list': dosen_list,
        'edit_mode': edit_mode,
    })


# =========================================================
# SEARCH MAHASISWA
# =========================================================
@login_required
def search_mahasiswa(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse([], safe=False)

    mahasiswa_login = get_object_or_404(Mahasiswa, user=request.user)

    used_ids = set(AnggotaTim.objects.values_list('mahasiswa_id', flat=True))
    tim_user = AnggotaTim.objects.filter(mahasiswa=mahasiswa_login, role='ketua').first()

    if tim_user:
        anggota_tim_sendiri = AnggotaTim.objects.filter(tim=tim_user.tim).values_list('mahasiswa_id', flat=True)
        for m_id in anggota_tim_sendiri:
            used_ids.discard(m_id)

    qs = Mahasiswa.objects.select_related('user').filter(
        Q(nim__icontains=query) |
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query)
    ).exclude(id__in=used_ids)[:10]

    data = []
    for m in qs:
        nama = m.user.get_full_name() or m.user.username
        data.append({
            "id": m.id,
            "nim": m.nim,
            "nama": nama,
            "kategori": m.kategori or "EPD"
        })

    return JsonResponse(data, safe=False)


# =========================================================
# LIST DOSEN PEMBIMBING
# =========================================================
@login_required
def list_dospem(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response
    
    dosen_list = DosenPembimbing.objects.select_related('dosen__user').filter(status='OPEN')
    return render(request, 'mahasiswa/list_dospem.html', {'dosen_list': dosen_list})


# =========================================================
# CEK STATUS (LEGACY - DIPERTAHANKAN UNTUK KOMPATIBILITAS)
# =========================================================
@login_required
def cek_status(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, user=request.user)
    proposal = get_proposal_ketua(mahasiswa)
    resume = Resume.objects.filter(mahasiswa=mahasiswa).first()
    pengajuan = PengajuanDospem.objects.filter(mahasiswa=mahasiswa).first()

    riwayat_cp = []
    riwayat_pb = []
    riwayat_resume = []

    if proposal:
        riwayat_cp = RiwayatFeedbackProposal.objects.filter(
            proposal=proposal, reviewer='CP'
        ).order_by('-created_at')
        riwayat_pb = RiwayatFeedbackProposal.objects.filter(
            proposal=proposal, reviewer='PB'
        ).order_by('-created_at')

    if resume:
        riwayat_resume = RiwayatFeedbackResume.objects.filter(
            resume=resume
        ).order_by('-created_at')

    return render(request, 'mahasiswa/cek_status.html', {
        'proposal': proposal,
        'resume': resume,
        'pengajuan': pengajuan,
        'riwayat_cp': riwayat_cp,
        'riwayat_pb': riwayat_pb,
        'riwayat_resume': riwayat_resume,
    })


# =========================================================
# PROFILE MAHASISWA
# =========================================================
@login_required
def mahasiswa_profile(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response
    
    user = request.user
    mahasiswa = user.mahasiswa

    if request.method == 'POST':
        user.email = request.POST.get('email', '').strip()
        password = request.POST.get('password')
        if password:
            user.set_password(password)
            update_session_auth_hash(request, user)
        user.save()

        if request.FILES.get('foto_profil'):
            mahasiswa.foto_profil = request.FILES['foto_profil']
            mahasiswa.save()

        messages.success(request, "Profil berhasil diperbarui.")
        return redirect('capstone_system:mahasiswa_profile')

    return render(request, 'mahasiswa/profile.html', {
        'user': user,
        'mahasiswa': mahasiswa,
    })


# =========================================================
# BUAT / EDIT TIM (DIPERBAIKI - TAMBAH VALIDASI NIM)
# =========================================================
@login_required
def buat_tim(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, user=request.user)

    anggota_tim = AnggotaTim.objects.filter(
        mahasiswa=mahasiswa,
        status_persetujuan__in=['PENDING', 'APPROVED']
    ).first()

    if anggota_tim and anggota_tim.role != 'ketua':
        messages.error(request, "Anda sudah tergabung dalam tim dan tidak dapat membuat tim baru.")
        return redirect('capstone_system:mahasiswa_home')

    anggota_user = AnggotaTim.objects.filter(
        mahasiswa=mahasiswa, role='ketua', status_persetujuan='APPROVED'
    ).first()
    edit_mode = anggota_user is not None

    tim = None
    ketua_data = None
    anggota_list = []

    if edit_mode:
        tim = anggota_user.tim
        if not tim.can_edit:
            messages.error(request, "Tim tidak dapat diubah karena proposal sedang direview atau telah disetujui.")
            return redirect('capstone_system:mahasiswa_home')

        anggota_queryset = tim.anggota.select_related('mahasiswa').all()
        ketua_obj = anggota_queryset.filter(role='ketua').first()
        if ketua_obj:
            ketua_data = {
                "id": ketua_obj.mahasiswa.id,
                "nama": str(ketua_obj.mahasiswa),
                "kategori": ketua_obj.kategori,
            }
        anggota_list = [
            {
                "id": a.mahasiswa.id,
                "name": str(a.mahasiswa),
                "kategori": a.kategori,
                "role": a.role,
            }
            for a in anggota_queryset.filter(role='anggota')
        ]

    if request.method == 'POST':
        if edit_mode:
            tim = anggota_user.tim
            if not tim.can_edit:
                messages.error(request, "Tim tidak dapat diubah karena proposal sedang direview atau telah disetujui.")
                return redirect('capstone_system:mahasiswa_home')

        # =========================================================
        # 🔥 AMBIL DATA DARI FORM
        # =========================================================
        nama_tim = request.POST.get('nama_tim')
        kategori = request.POST.get('kategori')
        anggota_ids = request.POST.getlist('anggota_id[]')
        anggota_kategori = request.POST.getlist('anggota_kategori[]')

        # =========================================================
        # 🔥 VALIDASI: Kategori wajib dipilih
        # =========================================================
        if not nama_tim:
            messages.error(request, "Nama tim wajib diisi")
            return redirect('capstone_system:mahasiswa_home')

        if not kategori:
            messages.error(request, "Pilih kategori Capstone terlebih dahulu!")
            return redirect('capstone_system:mahasiswa_home')

        if len(anggota_ids) > 4:
            messages.error(request, "Maksimal anggota yang dapat diundang adalah 4 orang.")
            return redirect('capstone_system:mahasiswa_home')

        # =========================================================
        # VALIDASI: Cek duplikasi NIM di antara anggota yang dipilih
        # =========================================================
        nim_list = []
        for m_id in anggota_ids:
            try:
                mhs = Mahasiswa.objects.get(id=int(m_id))
                if mhs.nim in nim_list:
                    messages.error(request, f"⚠️ Mahasiswa dengan NIM {mhs.nim} sudah ada di daftar anggota!")
                    return redirect('capstone_system:buat_tim')
                nim_list.append(mhs.nim)
            except Mahasiswa.DoesNotExist:
                messages.error(request, f"Mahasiswa dengan ID {m_id} tidak ditemukan.")
                return redirect('capstone_system:buat_tim')

        # =========================================================
        # 🔥 SIMPAN / UPDATE TIM DENGAN KATEGORI
        # =========================================================
        if edit_mode:
            tim = anggota_user.tim
            tim.nama_tim = nama_tim
            tim.kategori = kategori
            tim.status = 'PENDING'
            tim.save()
            
            ketua = tim.anggota.filter(role='ketua').first()
            if ketua:
                ketua.kategori = kategori
                ketua.save()
                
        else:
            semua_id = set(anggota_ids)
            sudah_pakai = AnggotaTim.objects.filter(
                mahasiswa_id__in=semua_id,
                status_persetujuan__in=['PENDING', 'APPROVED']
            ).exists()
            if sudah_pakai:
                messages.error(request, "Ada anggota yang sudah memiliki tim")
                return redirect('capstone_system:mahasiswa_home')

            tim = Tim.objects.create(
                nama_tim=nama_tim,
                kategori=kategori,
                status='PENDING'
            )
            
            AnggotaTim.objects.create(
                tim=tim,
                mahasiswa=mahasiswa,
                role='ketua',
                kategori=kategori,
                status_persetujuan='APPROVED'
            )

        # =========================================================
        # 🔥 UPDATE ANGGOTA TIM - PAKAI KATEGORI DARI DROPDOWN
        # =========================================================
        anggota_lama = {a.mahasiswa_id: a for a in tim.anggota.filter(role='anggota')}
        anggota_baru = set()

        for m_id, kat in zip(anggota_ids, anggota_kategori):
            m_id = int(m_id)
            
            if m_id == mahasiswa.id:
                continue
            
            anggota_baru.add(m_id)
            
            if kat not in ['EPD', 'SM']:
                kat = 'EPD'
            
            if m_id in anggota_lama:
                anggota = anggota_lama[m_id]
                anggota.kategori = kat
                anggota.save()
            else:
                AnggotaTim.objects.create(
                    tim=tim,
                    mahasiswa_id=m_id,
                    role='anggota',
                    kategori=kat,
                    status_persetujuan='PENDING'
                )

        for m_id, anggota in anggota_lama.items():
            if m_id not in anggota_baru:
                anggota.delete()

        ada_pending = tim.anggota.filter(status_persetujuan='PENDING').exists()
        tim.status = 'PENDING' if ada_pending else 'APPROVED'
        tim.save()

        messages.success(request, "Tim berhasil diperbarui" if edit_mode else "Tim berhasil dibuat")
        return redirect('capstone_system:mahasiswa_home')

    return render(request, 'mahasiswa/buat_tim.html', {
        'edit_mode': edit_mode,
        'tim': tim,
        'ketua_data': ketua_data,
        'anggota_list': anggota_list,
    })


# =========================================================
# LIST UNDANGAN TIM (DIPERBAIKI)
# =========================================================
@login_required
def undangan_tim(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, user=request.user)
    undangan = AnggotaTim.objects.filter(
        mahasiswa=mahasiswa, status_persetujuan='PENDING'
    ).select_related('tim')

    if request.method == "POST":
        anggota_id = request.POST.get("anggota_id")
        aksi = request.POST.get("aksi")
        anggota = get_object_or_404(AnggotaTim, id=anggota_id, mahasiswa=mahasiswa)
        tim = anggota.tim

        if aksi == "terima":
            anggota.status_persetujuan = "APPROVED"
            anggota.save()
            messages.success(request, f"Anda berhasil bergabung dengan tim {tim.nama_tim}")
        elif aksi == "tolak":
            anggota.status_persetujuan = "REJECTED"
            anggota.save()
            anggota.delete()
            messages.warning(request, f"Anda menolak undangan dari tim {tim.nama_tim}")

        ada_pending = tim.anggota.filter(status_persetujuan='PENDING').exists()
        tim.status = 'PENDING' if ada_pending else 'APPROVED'
        tim.save()

        return redirect('capstone_system:undangan_tim')

    return render(request, 'mahasiswa/undangan_tim.html', {'undangan': undangan})


# =========================================================
# JADWAL BIMBINGAN
# =========================================================
@login_required
def mahasiswa_jadwal_bimbingan(request):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = Mahasiswa.objects.get(user=request.user)
    dosen_pb = mahasiswa.dosen_pembimbing

    jadwal = JadwalKonsultasi.objects.filter(dosen=dosen_pb).order_by('tanggal', 'jam_mulai')
    booking_saya = BookingJadwal.objects.filter(mahasiswa=mahasiswa).select_related('jadwal').order_by('-tanggal_booking')

    return render(request, 'mahasiswa/jadwal_bimbingan.html', {
        'jadwal': jadwal,
        'booking_saya': booking_saya,
        'dosen_pb': dosen_pb
    })


# =========================================================
# BOOKING JADWAL BIMBINGAN
# =========================================================
@login_required
def booking_jadwal(request, jadwal_id):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = Mahasiswa.objects.get(user=request.user)
    jadwal = get_object_or_404(JadwalKonsultasi, id=jadwal_id)

    booking, created = BookingJadwal.objects.get_or_create(
        mahasiswa=mahasiswa,
        jadwal=jadwal,
        defaults={'status': 'BOOKED'}
    )

    if not created:
        if booking.status == 'CANCELLED':
            booking.status = 'BOOKED'
            booking.save()
        else:
            messages.warning(request, "Kamu sudah ambil jadwal ini")
            return redirect('capstone_system:mahasiswa_jadwal')

    if created or booking.status == 'BOOKED':
        jadwal.jumlah_dipesan += 1
        jadwal.save()

    messages.success(request, "Jadwal berhasil diambil kembali")
    return redirect('capstone_system:mahasiswa_jadwal')


# =========================================================
# CANCEL BOOKING JADWAL BIMBINGAN
# =========================================================
@login_required
def cancel_booking(request, booking_id):
    has_access, response = check_role(request, ['MAHASISWA'])
    if not has_access:
        return response

    mahasiswa = Mahasiswa.objects.get(user=request.user)
    booking = get_object_or_404(BookingJadwal, id=booking_id, mahasiswa=mahasiswa)

    if booking.status != 'BOOKED':
        messages.error(request, "Tidak bisa dibatalkan")
        return redirect('capstone_system:mahasiswa_jadwal')

    booking.status = 'CANCELLED'
    booking.save()

    jadwal = booking.jadwal
    jadwal.jumlah_dipesan = max(0, jadwal.jumlah_dipesan - 1)
    jadwal.save()

    messages.success(request, "Booking dibatalkan")
    return redirect('capstone_system:mahasiswa_jadwal')