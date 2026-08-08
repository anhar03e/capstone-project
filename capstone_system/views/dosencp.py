# views/dosencp.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import F, Q

from ..models import ProposalCapstone, RiwayatFeedbackProposal
from .base import check_role

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
# DETAIL PROPOSAL
# =========================================================
@login_required
def dosencp_detail_proposal(request, proposal_id):
    has_access, response = check_role(request, ['DOSENCP'])
    if not has_access:
        return response

    proposal = get_object_or_404(ProposalCapstone, id=proposal_id)

    if request.method == "POST" and proposal.status_cp == "DITERIMA":
        messages.warning(request, "Proposal telah disetujui sehingga tidak dapat direview kembali.")
        return redirect('capstone_system:dosencp_detail_proposal', proposal_id=proposal.id)

    anggota_tim = proposal.tim.anggota.select_related('mahasiswa__user').order_by('-role', 'mahasiswa__nim')

    if request.method == 'POST':
        action = request.POST.get('action')
        catatan = request.POST.get('keterangan', '').strip()
        VALID_STATUS = ['DITERIMA', 'DITOLAK', 'REVISI']

        if action in VALID_STATUS:
            proposal.status_cp = action
            proposal.catatan_cp = catatan
            proposal.waktu_peninjauan = timezone.now()
            proposal.save()

            RiwayatFeedbackProposal.objects.create(
                proposal=proposal,
                reviewer='CP',
                dosen=proposal.cp_reviewer.dosen if proposal.cp_reviewer else None,
                status=action,
                catatan=catatan
            )

        return redirect('capstone_system:dosencp_list_proposal')

    return render(request, 'dosencp/detail_proposal.html', {
        'proposal': proposal,
        'anggota_tim': anggota_tim,
    })

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