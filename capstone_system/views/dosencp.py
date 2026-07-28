# views/dosencp.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash

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

    proposal_qs = ProposalCapstone.objects.all().order_by('-waktu_update')

    pending_qs = proposal_qs.filter(status_cp='BELUM_REVIEW')
    diterima_qs = proposal_qs.filter(status_cp='DITERIMA')
    revisi_qs = proposal_qs.filter(status_cp='REVISI')
    ditolak_qs = proposal_qs.filter(status_cp='DITOLAK')

    context = {
        'total_proposal': proposal_qs.count(),
        'proposal_pending': pending_qs.count(),
        'proposal_diterima': diterima_qs.count(),
        'proposal_revisi': revisi_qs.count(),
        'proposal_ditolak': ditolak_qs.count(),
        'proposal_terbaru': proposal_qs[:5],
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

    proposals = ProposalCapstone.objects.select_related('tim').order_by('-id')
    status = request.GET.get('status')

    if status:
        proposals = proposals.filter(status_cp=status)

    return render(request, 'dosencp/list_proposal.html', {'proposals': proposals})

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