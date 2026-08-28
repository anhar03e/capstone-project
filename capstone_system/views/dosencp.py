from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

from ..models import ProposalCapstone, RiwayatFeedbackProposal, DosenCP, Dosen
from .base import check_role


# =========================================================
# FUNGSI BANTU: Ambil atau Buat DosenCP
# =========================================================
def get_or_create_dosencp(user):
    """
    Mendapatkan atau membuat entri DosenCP untuk user
    Mendukung multi-role (user yang punya role DOSENCP)
    """
    try:
        return DosenCP.objects.get(dosen__user=user)
    except DosenCP.DoesNotExist:
        # Jika user tidak terdaftar sebagai DosenCP
        # Tapi cek apakah user punya role DOSENCP
        if user.has_role('DOSENCP'):
            dosen = get_object_or_404(Dosen, user=user)
            dosen_cp = DosenCP.objects.create(
                dosen=dosen,
                tugas="Dosen CP (Multi-Role)"
            )
            return dosen_cp
        return None


# =========================================================
# DOSEN CP HOME
# =========================================================
@login_required
def dosencp_home(request):
    has_access, response = check_role(request, ['DOSENCP'])
    if not has_access:
        return response

    # Ambil parameter
    keyword = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    entries = request.GET.get('entries', '5')

    # Query proposal
    proposal_qs = ProposalCapstone.objects.all().order_by('-waktu_update')

    # Filter keyword
    if keyword:
        proposal_qs = proposal_qs.filter(
            Q(judul__icontains=keyword) |
            Q(tim__nama_tim__icontains=keyword)
        )

    # Filter status
    if status_filter:
        proposal_qs = proposal_qs.filter(status_cp=status_filter)

    # Statistik
    pending_qs = proposal_qs.filter(status_cp='BELUM_REVIEW')
    diterima_qs = proposal_qs.filter(status_cp='DITERIMA')
    revisi_qs = proposal_qs.filter(status_cp='REVISI')
    ditolak_qs = proposal_qs.filter(status_cp='DITOLAK')

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
            count = proposal_qs.count()
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
        page_obj = FakePage(proposal_qs)
    else:
        paginator = Paginator(proposal_qs, per_page)
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
        'total_proposal': proposal_qs.count(),
        'proposal_pending': pending_qs.count(),
        'proposal_diterima': diterima_qs.count(),
        'proposal_revisi': revisi_qs.count() + ditolak_qs.count(),
    }

    return render(request, 'dosencp/home.html', context)


# =========================================================
# LIST PROPOSAL
# =========================================================
@login_required
def dosencp_list_proposal(request):
    has_access, response = check_role(request, ['DOSENCP'])
    if not has_access:
        return response

    keyword = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    entries = request.GET.get('entries', '5')

    proposals = ProposalCapstone.objects.select_related('tim').order_by('-id')

    # Filter keyword
    if keyword:
        proposals = proposals.filter(
            Q(judul__icontains=keyword) |
            Q(tim__nama_tim__icontains=keyword)
        )

    # Filter status
    if status_filter:
        proposals = proposals.filter(status_cp=status_filter)

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
            count = proposals.count()
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
        page_obj = FakePage(proposals)
    else:
        paginator = Paginator(proposals, per_page)
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

    return render(request, 'dosencp/list_proposal.html', context)


# =========================================================
# DETAIL PROPOSAL - DENGAN MULTIPLE FEEDBACK
# =========================================================
@login_required
def dosencp_detail_proposal(request, proposal_id):
    has_access, response = check_role(request, ['DOSENCP'])
    if not has_access:
        return response

    proposal = get_object_or_404(ProposalCapstone, id=proposal_id)
    
    # =========================================================
    # 🔥 AMBIL DOSEN CP YANG LOGIN
    # =========================================================
    dosen_cp = get_or_create_dosencp(request.user)
    
    if dosen_cp is None:
        messages.error(request, "Anda tidak memiliki akses sebagai Dosen CP.")
        return redirect('capstone_system:home')

    # =========================================================
    # 🔥 AMBIL SEMUA CATATAN DARI RIWAYAT FEEDBACK
    # =========================================================
    semua_catatan = RiwayatFeedbackProposal.objects.filter(
        proposal=proposal,
        reviewer='CP'
    ).order_by('-created_at')

    # =========================================================
    # 🔥 CEK APAKAH STATUS SUDAH PERNAH DITENTUKAN?
    # =========================================================
    # Status ditentukan jika proposal.status_cp tidak NULL/NONE
    # dan statusnya salah satu dari DITERIMA, REVISI, DITOLAK
    status_pernah_ditentukan = proposal.status_cp in ['DITERIMA', 'REVISI', 'DITOLAK']

    # =========================================================
    # 🔥 TOTAL REVISI (dari catatan yang ada)
    # =========================================================
    total_revisi = semua_catatan.filter(status='REVISI').count()

    # =========================================================
    # 🔥 ANGGOTA TIM
    # =========================================================
    anggota_tim = proposal.tim.anggota.select_related('mahasiswa__user').order_by('-role', 'mahasiswa__nim')

    # =========================================================
    # 🔥 PROSES FORM REVIEW
    # =========================================================
    if request.method == 'POST':
        action = request.POST.get('action')
        catatan = request.POST.get('keterangan', '').strip()

        if not catatan:
            messages.error(request, "Catatan wajib diisi.")
            return redirect('capstone_system:dosencp_detail_proposal', proposal_id=proposal.id)

        if not action:
            messages.error(request, "Status harus dipilih.")
            return redirect('capstone_system:dosencp_detail_proposal', proposal_id=proposal.id)

        # =========================================================
        # 🔥 VALIDASI: Jika status sudah ditentukan
        # =========================================================
        if status_pernah_ditentukan:
            # Status sudah ditentukan, TIDAK BISA diubah
            # Action harus sama dengan status yang berlaku
            if action != proposal.status_cp:
                messages.error(
                    request,
                    f"❌ Status sudah {proposal.status_cp}. Anda hanya bisa menambah catatan dengan status yang sama."
                )
                return redirect('capstone_system:dosencp_detail_proposal', proposal_id=proposal.id)
            
            # Simpan catatan dengan status yang sama
            RiwayatFeedbackProposal.objects.create(
                proposal=proposal,
                reviewer='CP',
                dosen=dosen_cp.dosen,
                status=action,
                catatan=catatan
            )
            
            # Update catatan_cp dengan catatan terbaru
            proposal.catatan_cp = catatan
            proposal.save()
            
            messages.success(request, f"✅ Catatan tambahan berhasil disimpan dengan status {action}.")
            return redirect('capstone_system:dosencp_detail_proposal', proposal_id=proposal.id)

        # =========================================================
        # 🔥 BELUM ADA STATUS: Bisa menentukan status
        # =========================================================
        # VALIDASI: Action harus salah satu dari 3 status
        if action not in ['DITERIMA', 'REVISI', 'DITOLAK']:
            messages.error(request, "❌ Status tidak valid. Pilih Terima, Revisi, atau Tolak.")
            return redirect('capstone_system:dosencp_detail_proposal', proposal_id=proposal.id)

        # =========================================================
        # 🔥 SIMPAN CATATAN KE RIWAYAT
        # =========================================================
        RiwayatFeedbackProposal.objects.create(
            proposal=proposal,
            reviewer='CP',
            dosen=dosen_cp.dosen,
            status=action,
            catatan=catatan
        )

        # =========================================================
        # 🔥 UPDATE STATUS PROPOSAL (pertama kali ditentukan)
        # =========================================================
        proposal.status_cp = action
        proposal.catatan_cp = catatan
        proposal.tanggal_review_cp = timezone.now()
        proposal.save()
        
        messages.success(request, f"✅ Status berhasil ditentukan: {action}")
        return redirect('capstone_system:dosencp_detail_proposal', proposal_id=proposal.id)

    # =========================================================
    # 🔥 CONTEXT UNTUK TEMPLATE
    # =========================================================
    context = {
        'proposal': proposal,
        'anggota_tim': anggota_tim,
        'semua_catatan': semua_catatan,
        'status_pernah_ditentukan': status_pernah_ditentukan,
        'total_revisi': total_revisi,
        'status_berlaku': proposal.status_cp if proposal.status_cp else 'Belum Review',
    }

    return render(request, 'dosencp/detail_proposal.html', context)

# =========================================================
# PROFILE DOSEN CP
# =========================================================
@login_required
def dosencp_profile(request):
    has_access, response = check_role(request, ['DOSENCP'])
    if not has_access:
        return response

    user = request.user
    dosen = user.dosen

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
        return redirect('capstone_system:dosencp_profile')

    return render(request, 'dosencp/profile.html', {
        'user': user,
        'dosen': dosen
    })