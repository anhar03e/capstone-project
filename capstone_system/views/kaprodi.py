from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import update_session_auth_hash
import pandas as pd
from django.views.decorators.csrf import csrf_exempt  
from django.views.decorators.http import require_http_methods

from ..models import (
    AnggotaTim,
    Mahasiswa,
    Dosen,
    DosenCP,
    DosenPembimbing,
    Tim,
    ProposalCapstone,
    Resume,
    PengajuanDospem,
    User,
)
from ..forms import DosenForm, ProposalForm, UploadMahasiswaForm
from .base import check_role

# =========================================================
# DASHBOARD KAPRODI
# =========================================================
@login_required
def kaprodi_home(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    context = {
        'total_proposal': ProposalCapstone.objects.count(),
        'total_resume': Resume.objects.count(),
        'total_mahasiswa': Mahasiswa.objects.filter(status="AKTIF").count(),
        'total_mahasiswa_aktif': Mahasiswa.objects.filter(status="AKTIF").count(),
        'total_mahasiswa_nonaktif': Mahasiswa.objects.filter(status="NONAKTIF").count(),
        'total_dospem': DosenPembimbing.objects.count(),
        'total_dosen': Dosen.objects.filter(status_aktif="AKTIF").count(),
        'total_dosen_aktif': Dosen.objects.filter(status_aktif="AKTIF").count(),
        'total_dosen_nonaktif': Dosen.objects.filter(status_aktif="NONAKTIF").count(),
        'total_tim': Tim.objects.count(),
    }

    return render(request, 'kaprodi/home.html', context)


# =========================================================
# MAHASISWA (MASTER DATA) - DENGAN KATEGORI
# =========================================================
@login_required
def kaprodi_list_mahasiswa(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    # 🔥 PERBAIKI: Ambil hanya AKTIF dan NONAKTIF, KECUALI ARSIP (kecuali difilter)
    mahasiswa_list = Mahasiswa.objects.select_related(
        'user', 'dosen_pembimbing'
    ).exclude(status="ARSIP")  # 🔥 EXCLUDE ARSIP SECARA DEFAULT

    status = request.GET.get('status')
    if status:
        mahasiswa_list = mahasiswa_list.filter(status=status)
    else:
        # Jika tidak ada filter status, tampilkan AKTIF dan NONAKTIF saja
        mahasiswa_list = mahasiswa_list.filter(status__in=['AKTIF', 'NONAKTIF'])

    angkatan = request.GET.get('angkatan')
    if angkatan:
        mahasiswa_list = mahasiswa_list.filter(angkatan=angkatan)

    keyword = request.GET.get('q', '').strip()
    if keyword:
        mahasiswa_list = mahasiswa_list.filter(
            Q(user__first_name__icontains=keyword) |
            Q(user__last_name__icontains=keyword) |
            Q(nim__icontains=keyword)
        )

    mahasiswa_list = mahasiswa_list.order_by('-angkatan', 'nim')

    # 🔥 TAMBAH: Ambil kategori dari Mahasiswa atau AnggotaTim
    for mhs in mahasiswa_list:
        # PRIORITAS: Jika mahasiswa.kategori ada (diubah Kaprodi), pakai itu
        if mhs.kategori:
            mhs.kategori_tim = mhs.kategori
        else:
            # Jika tidak ada, ambil dari AnggotaTim
            anggota = AnggotaTim.objects.filter(
                mahasiswa=mhs,
                status_persetujuan='APPROVED'
            ).first()
            mhs.kategori_tim = anggota.kategori if anggota else None

    daftar_angkatan = Mahasiswa.objects.values_list('angkatan', flat=True).distinct().order_by('-angkatan')

    total_mahasiswa_aktif = Mahasiswa.objects.filter(status="AKTIF").count()
    total_mahasiswa_nonaktif = Mahasiswa.objects.filter(status="NONAKTIF").count()
    total_mahasiswa_arsip = Mahasiswa.objects.filter(status="ARSIP").count()

    context = {
        'mahasiswa_list': mahasiswa_list,
        'daftar_angkatan': daftar_angkatan,
        'status_filter': status,
        'angkatan_filter': angkatan,
        'keyword': keyword,
        'total_mahasiswa': total_mahasiswa_aktif + total_mahasiswa_nonaktif + total_mahasiswa_arsip,
        'total_mahasiswa_aktif': total_mahasiswa_aktif,
        'total_mahasiswa_nonaktif': total_mahasiswa_nonaktif,
        'total_mahasiswa_arsip': total_mahasiswa_arsip,
    }

    return render(request, 'kaprodi/list_mahasiswa.html', context)


# =========================================================
# NONAKTIFKAN MAHASISWA (DIPERBAIKI)
# =========================================================
@login_required
@transaction.atomic
def nonaktifkan_mahasiswa(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, id=id)
    
    # CEK: Jika sudah nonaktif
    if mahasiswa.status == "NONAKTIF":
        messages.warning(request, f"{mahasiswa.user.get_full_name()} sudah nonaktif.")
        return redirect("capstone_system:kaprodi_mahasiswa")
    
    # CEK: Jika sedang arsip
    if mahasiswa.status == "ARSIP":
        messages.warning(request, f"{mahasiswa.user.get_full_name()} sedang dalam arsip. Kembalikan dulu dari arsip.")
        return redirect("capstone_system:kaprodi_mahasiswa")

    dospem = mahasiswa.dosen_pembimbing

    if mahasiswa.status == "AKTIF" and dospem:
        dospem.update_status()

    mahasiswa.status = "NONAKTIF"
    mahasiswa.save()
    mahasiswa.user.is_active = False
    mahasiswa.user.save()

    messages.success(request, f"{mahasiswa.user.get_full_name()} berhasil dinonaktifkan.")
    return redirect("capstone_system:kaprodi_mahasiswa")


# =========================================================
# AKTIFKAN MAHASISWA (DIPERBAIKI - TAMBAH HANDLE ARSIP)
# =========================================================
@login_required
@transaction.atomic
def aktifkan_mahasiswa(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, id=id)
    
    # CEK: Jika sudah aktif
    if mahasiswa.status == "AKTIF":
        messages.info(request, f"{mahasiswa.user.get_full_name()} sudah aktif.")
        return redirect("capstone_system:kaprodi_mahasiswa")
    
    # =========================================================
    # HANDLE KHUSUS UNTUK STATUS ARSIP
    # =========================================================
    if mahasiswa.status == "ARSIP":
        # Cek kuota dosen pembimbing
        if mahasiswa.dosen_pembimbing:
            dospem = mahasiswa.dosen_pembimbing
            if dospem.penuh:
                messages.error(
                    request, 
                    f"Mahasiswa tidak dapat diaktifkan karena kuota Dosen Pembimbing {dospem.dosen.user.get_full_name()} sudah penuh."
                )
                return redirect("capstone_system:kaprodi_mahasiswa")
            dospem.update_status()
        
        mahasiswa.status = "AKTIF"
        mahasiswa.save()
        mahasiswa.user.is_active = True
        mahasiswa.user.save()
        
        messages.success(request, f"{mahasiswa.user.get_full_name()} berhasil dikembalikan dari arsip.")
        return redirect("capstone_system:kaprodi_mahasiswa")
    
    # =========================================================
    # HANDLE UNTUK STATUS NONAKTIF
    # =========================================================
    dospem = mahasiswa.dosen_pembimbing
    if mahasiswa.status == "NONAKTIF" and dospem:
        if dospem.penuh:
            messages.error(
                request, 
                f"Mahasiswa tidak dapat diaktifkan karena kuota Dosen Pembimbing {dospem.dosen.user.get_full_name()} sudah penuh."
            )
            return redirect("capstone_system:kaprodi_mahasiswa")
        dospem.update_status()

    mahasiswa.status = "AKTIF"
    mahasiswa.save()
    mahasiswa.user.is_active = True
    mahasiswa.user.save()

    messages.success(request, f"{mahasiswa.user.get_full_name()} berhasil diaktifkan kembali.")
    return redirect("capstone_system:kaprodi_mahasiswa")


# =========================================================
# KEMBALIKAN MAHASISWA DARI ARSIP (FUNGSI BARU)
# =========================================================
@login_required
@transaction.atomic
def kembalikan_dari_arsip(request, id):
    """
    Mengembalikan mahasiswa dari status ARSIP ke AKTIF
    """
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, id=id)
    
    if mahasiswa.status != "ARSIP":
        messages.warning(request, f"Mahasiswa {mahasiswa.user.get_full_name()} tidak dalam status arsip.")
        return redirect("capstone_system:kaprodi_mahasiswa")

    # Cek kuota dosen pembimbing
    if mahasiswa.dosen_pembimbing:
        dospem = mahasiswa.dosen_pembimbing
        if dospem.penuh:
            messages.error(
                request, 
                f"Mahasiswa tidak dapat dikembalikan karena kuota Dosen Pembimbing {dospem.dosen.user.get_full_name()} sudah penuh."
            )
            return redirect("capstone_system:arsip_mahasiswa")
        dospem.update_status()

    # Kembalikan ke status AKTIF
    mahasiswa.status = "AKTIF"
    mahasiswa.save()
    
    # Aktifkan user
    mahasiswa.user.is_active = True
    mahasiswa.user.save()

    messages.success(
        request, 
        f"{mahasiswa.user.get_full_name()} berhasil dikembalikan dari arsip."
    )
    return redirect("capstone_system:arsip_mahasiswa")


# =========================================================
# Detail Mahasiswa (KAPRODI) - DENGAN RIWAYAT & KATEGORI
# =========================================================
@login_required
def detail_mahasiswa(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, id=id)
    
    # 🔥 PRIORITAS: Jika mahasiswa.kategori ada, pakai itu
    if mahasiswa.kategori:
        mahasiswa.kategori_tim = mahasiswa.kategori
    else:
        anggota = AnggotaTim.objects.filter(
            mahasiswa=mahasiswa,
            status_persetujuan='APPROVED'
        ).first()
        mahasiswa.kategori_tim = anggota.kategori if anggota else None
    
    # Ambil tim yang diikuti mahasiswa
    tim_ids = AnggotaTim.objects.filter(
        mahasiswa=mahasiswa,
        status_persetujuan='APPROVED'
    ).values_list('tim_id', flat=True)
    
    proposal_list = ProposalCapstone.objects.filter(
        tim_id__in=tim_ids
    ).order_by('-waktu_pengajuan')
    
    resume_list = Resume.objects.filter(
        mahasiswa=mahasiswa
    ).order_by('-waktu_pengajuan')
    
    pengajuan_list = PengajuanDospem.objects.filter(
        mahasiswa=mahasiswa
    ).order_by('-tanggal_pengajuan').select_related(
        'dosen_pembimbing__dosen__user'
    )

    return render(request, "kaprodi/detail_mahasiswa.html", {
        "mahasiswa": mahasiswa,
        "proposal_list": proposal_list,
        "resume_list": resume_list,
        "pengajuan_list": pengajuan_list,
    })


# =========================================================
# TAMBAH MAHASISWA
# =========================================================
@login_required
@transaction.atomic
def tambah_mahasiswa(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    if request.method == "POST":
        form = Mahasiswa(request.POST)
        if form.is_valid():
            nim = form.cleaned_data["nim"]
            if User.objects.filter(username=nim).exists():
                messages.error(request, "NIM sudah terdaftar.")
                return render(request, "kaprodi/tambah_mahasiswa.html", {"form": form})

            if User.objects.filter(email=form.cleaned_data["email"]).exists():
                messages.error(request, "Email sudah digunakan.")
                return render(request, "kaprodi/tambah_mahasiswa.html", {"form": form})

            user = User.objects.create_user(
                username=nim,
                password=nim,
                first_name=form.cleaned_data["nama_lengkap"],
                email=form.cleaned_data["email"],
                role="MAHASISWA",
                is_password_changed=False,
            )

            mahasiswa = form.save(commit=False)
            mahasiswa.user = user
            mahasiswa.status = "AKTIF"
            mahasiswa.save()

            messages.success(request, "Mahasiswa berhasil ditambahkan.")
            return redirect("capstone_system:kaprodi_mahasiswa")
    else:
        form = Mahasiswa()

    return render(request, "kaprodi/tambah_mahasiswa.html", {"form": form})


# =========================================================
# EDIT MAHASISWA (KAPRODI)
# =========================================================
@login_required
def edit_mahasiswa(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    mahasiswa = get_object_or_404(Mahasiswa, id=id)
    user = mahasiswa.user

    dospem_list = DosenPembimbing.objects.filter(
        Q(status="OPEN") | Q(id=mahasiswa.dosen_pembimbing_id)
    ).select_related("dosen__user")

    # 🔥 AMBIL NEXT URL
    next_url = request.GET.get('next') or request.POST.get('next')
    
    # 🔥 Ambil kategori dari tim
    anggota = AnggotaTim.objects.filter(
        mahasiswa=mahasiswa,
        status_persetujuan='APPROVED'
    ).first()
    mahasiswa.kategori_tim = anggota.kategori if anggota else None

    if request.method == "POST":
        user.first_name = request.POST.get("nama")
        user.email = request.POST.get("email")
        nim = request.POST.get("nim")

        if Mahasiswa.objects.exclude(id=mahasiswa.id).filter(nim=nim).exists():
            messages.error(request, "NIM sudah digunakan.")
            return redirect("capstone_system:edit_mahasiswa", id=id)

        user.username = nim
        user.save()

        mahasiswa.nim = nim
        mahasiswa.kelas = request.POST.get("kelas")
        mahasiswa.angkatan = request.POST.get("angkatan")
        
        # 🔥 SIMPAN KATEGORI DARI FORM
        mahasiswa.kategori = request.POST.get("kategori")
        
        mahasiswa.status = request.POST.get("status")
        mahasiswa.tanggal_masuk = request.POST.get("tanggal_masuk") or None

        dospem_id = request.POST.get("dosen_pembimbing")
        dospem_lama = mahasiswa.dosen_pembimbing

        if not dospem_id:
            if dospem_lama:
                dospem_lama.update_status()
            mahasiswa.dosen_pembimbing = None
        else:
            dospem_baru = get_object_or_404(DosenPembimbing, id=dospem_id)
            if dospem_lama is None or dospem_lama.id != dospem_baru.id:
                if dospem_baru.penuh:
                    messages.error(request, f"Kuota Dosen Pembimbing {dospem_baru.dosen.user.get_full_name()} sudah penuh.")
                    return redirect("capstone_system:edit_mahasiswa", id=id)
                if dospem_lama:
                    dospem_lama.update_status()
                mahasiswa.dosen_pembimbing = dospem_baru
                dospem_baru.update_status()
            else:
                mahasiswa.dosen_pembimbing = dospem_lama

        mahasiswa.save()
        if mahasiswa.dosen_pembimbing:
            mahasiswa.dosen_pembimbing.update_status()

        messages.success(request, "Data mahasiswa berhasil diperbarui.")

        # 🔥 Redirect ke next URL jika ada
        if next_url:
            return redirect(next_url)
        return redirect("capstone_system:kaprodi_mahasiswa")

    return render(request, "kaprodi/edit_mahasiswa.html", {
        "mahasiswa": mahasiswa,
        "dospem_list": dospem_list,
        "next_url": next_url,
    })


# =========================================================
# DOSEN PEMBIMBING (MANAGE)
# =========================================================
@login_required
def kaprodi_manage_dospem(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    dospem_list = DosenPembimbing.objects.select_related(
        "dosen", "dosen__user"
    ).filter(dosen__status_aktif="AKTIF").order_by("dosen__user__first_name")

    for dospem in dospem_list:
        dospem.update_status()

    context = {
        "dospem_list": dospem_list,
        "total_dospem": dospem_list.count(),
        "total_open": dospem_list.filter(status="OPEN").count(),
        "total_full": dospem_list.filter(status="FULL").count(),
    }

    return render(request, "kaprodi/manage_dospem.html", context)


# =========================================================
# DOSEN CP (OPSIONAL JIKA KAMU TAMBAH DI URLS)
# =========================================================
@login_required
def kaprodi_list_dosen(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    dosen_list = Dosen.objects.select_related('user').all()
    keyword = request.GET.get('q', '')
    status = request.GET.get('status')

    if keyword:
        dosen_list = dosen_list.filter(
            Q(user__first_name__icontains=keyword) |
            Q(user__last_name__icontains=keyword) |
            Q(nip__icontains=keyword)
        )

    if status:
        dosen_list = dosen_list.filter(status_aktif=status)

    context = {
        'dosen_list': dosen_list,
        'keyword': keyword,
        'status_filter': status,
        'total_dosen': Dosen.objects.filter(status_aktif='AKTIF').count(),
        'total_dosen_aktif': Dosen.objects.filter(status_aktif='AKTIF').count(),
        'total_dosen_nonaktif': Dosen.objects.filter(status_aktif='NONAKTIF').count(),
    }

    return render(request, 'kaprodi/list_dosen.html', context)


# =========================================================
# NON AKTIF DOSEN
# =========================================================
@login_required
def nonaktifkan_dosen(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    dosen = get_object_or_404(Dosen, id=id)
    dosen.status_aktif = "NONAKTIF"
    dosen.save()
    dosen.user.is_active = False
    dosen.user.save()
    DosenPembimbing.objects.filter(dosen=dosen).update(status="CLOSED")

    messages.success(request, "Dosen berhasil dinonaktifkan.")
    return redirect('capstone_system:kaprodi_dosen')


# =========================================================
# AKTIF DOSEN
# =========================================================
@login_required
def aktifkan_dosen(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    dosen = get_object_or_404(Dosen, id=id)
    dosen.status_aktif = "AKTIF"
    dosen.save()
    dosen.user.is_active = True
    dosen.user.save()
    DosenPembimbing.objects.filter(dosen=dosen).update(status="OPEN")

    messages.success(request, "Dosen berhasil diaktifkan.")
    return redirect('capstone_system:kaprodi_dosen')


# =========================================================
# TAMBAH DOSEN
# =========================================================
@login_required
@transaction.atomic
def tambah_dosen(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    if request.method == "POST":
        form = DosenForm(request.POST)
        if form.is_valid():
            nama = form.cleaned_data['nama_lengkap']
            email = form.cleaned_data['email']
            role = form.cleaned_data['role']
            nip = form.cleaned_data['nip']

            if User.objects.filter(username=nip).exists():
                messages.error(request, "NIP sudah terdaftar.")
                return render(request, "kaprodi/tambah_dosen.html", {"form": form})

            if User.objects.filter(email=email).exists():
                messages.error(request, "Email sudah digunakan.")
                return render(request, "kaprodi/tambah_dosen.html", {"form": form})

            user = User.objects.create_user(
                username=nip,
                password=nip,
                first_name=nama,
                email=email,
                role=role,
                is_password_changed=False,
            )

            dosen = form.save(commit=False)
            dosen.user = user
            dosen.save()

            if role == "DOSENPB":
                DosenPembimbing.objects.create(dosen=dosen)
            else:
                DosenCP.objects.create(dosen=dosen, tugas="Reviewer Capstone")

            messages.success(request, "Dosen berhasil ditambahkan.")
            return redirect("capstone_system:kaprodi_dosen")
    else:
        form = DosenForm()

    return render(request, "kaprodi/tambah_dosen.html", {"form": form})


# =========================================================
# EDIT DOSEN
# =========================================================
@login_required
@transaction.atomic
def edit_dosen(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    dosen = get_object_or_404(Dosen, id=id)

    if request.method == "POST":
        form = DosenForm(request.POST, instance=dosen)
        if form.is_valid():
            form.save()
            dosen = form.instance

            DosenPembimbing.objects.filter(dosen=dosen).delete()
            DosenCP.objects.filter(dosen=dosen).delete()

            if dosen.user.role == "DOSENPB":
                DosenPembimbing.objects.create(dosen=dosen)
            else:
                DosenCP.objects.create(dosen=dosen, tugas="Reviewer Capstone")

            messages.success(request, "Data dosen berhasil diperbarui.")
            return redirect("capstone_system:kaprodi_dosen")
    else:
        form = DosenForm(instance=dosen)

    return render(request, "kaprodi/edit_dosen.html", {
        "form": form,
        "dosen": dosen
    })


# =========================================================
# TIM
# =========================================================
@login_required
def kaprodi_list_tim(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    tim_list = Tim.objects.all().order_by('-dibuat_pada')
    return render(request, 'kaprodi/list_tim.html', {'tim_list': tim_list})


@login_required
def kaprodi_detail_tim(request, tim_id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    tim = get_object_or_404(Tim, id=tim_id)
    anggota = tim.anggota.all()
    return render(request, 'kaprodi/detail_tim.html', {
        'tim': tim,
        'anggota': anggota
    })


# =========================================================
# PROPOSAL
# =========================================================
@login_required
def kaprodi_list_proposal(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    proposals = ProposalCapstone.objects.all().order_by('-waktu_pengajuan')
    return render(request, 'kaprodi/list_proposal.html', {'proposals': proposals})


@login_required
def kaprodi_detail_proposal(request, proposal_id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    proposal = get_object_or_404(ProposalCapstone, id=proposal_id)
    return render(request, 'kaprodi/detail_proposal.html', {'proposal': proposal})


@login_required
def kaprodi_update_proposal(request, proposal_id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    proposal = get_object_or_404(ProposalCapstone, id=proposal_id)

    if request.method == 'POST':
        form = ProposalForm(request.POST, request.FILES, instance=proposal)
        if form.is_valid():
            form.save()
            messages.success(request, "Proposal berhasil diperbarui")
            return redirect('capstone_system:kaprodi_proposal')
    else:
        form = ProposalForm(instance=proposal)

    return render(request, 'kaprodi/update_proposal.html', {
        'form': form,
        'proposal': proposal
    })


@login_required
def kaprodi_delete_proposal(request, proposal_id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    proposal = get_object_or_404(ProposalCapstone, id=proposal_id)

    if request.method == 'POST':
        proposal.delete()
        messages.success(request, "Proposal berhasil dihapus")
        return redirect('capstone_system:kaprodi_proposal')

    return render(request, 'kaprodi/delete_proposal.html', {'proposal': proposal})


# =========================================================
# RESUME
# =========================================================
@login_required
def kaprodi_list_resume(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    resumes = Resume.objects.all().order_by('-waktu_pengajuan')
    return render(request, 'kaprodi/list_resume.html', {'resumes': resumes})


@login_required
def kaprodi_detail_resume(request, resume_id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    resume = get_object_or_404(Resume, id=resume_id)
    return render(request, 'kaprodi/detail_resume.html', {'resume': resume})


# =========================================================
# PENGAJUAN DOSPEM
# =========================================================
@login_required
def kaprodi_pengajuan(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    pengajuan_list = PengajuanDospem.objects.all().order_by('-tanggal_pengajuan')
    return render(request, 'kaprodi/pengajuan.html', {'pengajuan_list': pengajuan_list})


# =========================================================
# MONITORING CAPSTONE (GABUNGAN PROPOSAL & RESUME)
# =========================================================
@login_required
def kaprodi_monitoring(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    # Ambil semua mahasiswa aktif
    mahasiswa_list = Mahasiswa.objects.filter(status='AKTIF').select_related(
        'user', 'dosen_pembimbing', 'dosen_pembimbing__dosen', 'dosen_pembimbing__dosen__user'
    )

    # Filter pencarian
    keyword = request.GET.get('q', '').strip()
    if keyword:
        mahasiswa_list = mahasiswa_list.filter(
            Q(user__first_name__icontains=keyword) |
            Q(user__last_name__icontains=keyword) |
            Q(nim__icontains=keyword)
        )

    # Filter status
    status_proposal = request.GET.get('status_proposal', '')
    status_resume = request.GET.get('status_resume', '')

    # Build monitoring data
    monitoring_data = []
    total_proposal = 0
    total_resume = 0
    total_belum_upload = 0

    # Statistik
    stats_proposal = {
        'diterima': 0,
        'ditolak': 0,
        'revisi': 0,
        'pending': 0,
        'belum_review': 0,
    }
    stats_resume = {
        'diterima': 0,
        'ditolak': 0,
        'revisi': 0,
        'pending': 0,
        'belum_review': 0,
    }

    # =========================================================
    # DATA DOSEN PEMBIMBING (SEMUA DOSEN)
    # =========================================================
    # Ambil SEMUA dosen pembimbing yang aktif
    semua_dospem = DosenPembimbing.objects.filter(
        dosen__status_aktif='AKTIF'
    ).select_related('dosen', 'dosen__user')

    # Buat dictionary untuk semua dosen dengan default 0
    dosen_dict = {}
    for dospem in semua_dospem:
        nama_dosen = dospem.dosen.user.get_full_name()
        dosen_dict[nama_dosen] = {
            'jumlah_mahasiswa': 0,
            'dospem_id': dospem.id,
            'status': dospem.status,
            'batas_bimbingan': dospem.batas_bimbingan,
        }

    total_tanpa_dosen = 0

    for mhs in mahasiswa_list:
        # Cari proposal terbaru
        proposal = ProposalCapstone.objects.filter(
            tim__anggota__mahasiswa=mhs,
            tim__anggota__status_persetujuan='APPROVED'
        ).order_by('-waktu_pengajuan').first()

        # Cari resume terbaru
        resume = Resume.objects.filter(
            mahasiswa=mhs
        ).order_by('-waktu_pengajuan').first()

        # Status proposal
        status_proposal_text = None
        if proposal:
            status_proposal_text = proposal.status_final
            total_proposal += 1
            
            if status_proposal_text == 'DITERIMA':
                stats_proposal['diterima'] += 1
            elif status_proposal_text == 'DITOLAK':
                stats_proposal['ditolak'] += 1
            elif status_proposal_text == 'REVISI':
                stats_proposal['revisi'] += 1
            elif status_proposal_text == 'SEDANG_REVIEW':
                stats_proposal['pending'] += 1
            elif status_proposal_text == 'BELUM_REVIEW':
                stats_proposal['belum_review'] += 1
        else:
            status_proposal_text = 'BELUM_UPLOAD'

        # Status resume
        status_resume_text = None
        if resume:
            status_resume_text = resume.status
            total_resume += 1
            
            if status_resume_text == 'DISETUJUI':
                stats_resume['diterima'] += 1
            elif status_resume_text == 'DITOLAK':
                stats_resume['ditolak'] += 1
            elif status_resume_text == 'REVISI':
                stats_resume['revisi'] += 1
            elif status_resume_text == 'BELUM_REVIEW':
                stats_resume['belum_review'] += 1
                stats_resume['pending'] += 1
        else:
            status_resume_text = 'BELUM_UPLOAD'

        # Filter berdasarkan status
        if status_proposal and status_proposal_text != status_proposal:
            continue
        if status_resume and status_resume_text != status_resume:
            continue

        # Cek belum upload
        if not proposal and not resume:
            total_belum_upload += 1

        # Dosen pembimbing - UPDATE JUMLAH MAHASISWA
        dosen_nama = None
        if mhs.dosen_pembimbing:
            dosen_nama = mhs.dosen_pembimbing.dosen.user.get_full_name()
            if dosen_nama in dosen_dict:
                dosen_dict[dosen_nama]['jumlah_mahasiswa'] += 1
            else:
                dosen_dict[dosen_nama] = {
                    'jumlah_mahasiswa': 1,
                    'dospem_id': mhs.dosen_pembimbing.id,
                    'status': mhs.dosen_pembimbing.status,
                    'batas_bimbingan': mhs.dosen_pembimbing.batas_bimbingan,
                }
        else:
            total_tanpa_dosen += 1

        monitoring_data.append({
            'mahasiswa_id': mhs.id,
            'nim': mhs.nim,
            'nama': mhs.user.get_full_name(),
            'kelas': mhs.kelas,
            'angkatan': mhs.angkatan,
            'status_proposal': status_proposal_text,
            'status_resume': status_resume_text,
            'proposal_id': proposal.id if proposal else None,
            'resume_id': resume.id if resume else None,
            'dosen_pembimbing': dosen_nama,
        })

    # =========================================================
    # SORTING
    # =========================================================
    sort_by = request.GET.get('sort', 'nama')
    sort_order = request.GET.get('order', 'asc')

    sort_mapping = {
        'nama': 'nama',
        'nim': 'nim',
        'kelas': 'kelas',
        'angkatan': 'angkatan',
        'status_proposal': 'status_proposal',
        'status_resume': 'status_resume',
    }

    sort_field = sort_mapping.get(sort_by, 'nama')
    reverse = sort_order == 'desc'

    monitoring_data.sort(key=lambda x: x.get(sort_field, '').lower() if x.get(sort_field) else '', reverse=reverse)

    # =========================================================
    # BUAT LIST DOSEN UNTUK TAMPILAN (SEMUA DOSEN)
    # =========================================================
    dosen_list = []
    for nama, data in dosen_dict.items():
        dosen_list.append({
            'nama': nama,
            'jumlah_mahasiswa': data['jumlah_mahasiswa'],
            'dospem_id': data['dospem_id'],
            'status': data['status'],
            'batas_bimbingan': data['batas_bimbingan'],
            'sisa_kuota': data['batas_bimbingan'] - data['jumlah_mahasiswa'],
            'penuh': data['jumlah_mahasiswa'] >= data['batas_bimbingan'],
        })
    
    dosen_list.sort(key=lambda x: x['jumlah_mahasiswa'], reverse=True)

    context = {
        'monitoring_list': monitoring_data,
        'total_mahasiswa': mahasiswa_list.count(),
        'total_proposal': total_proposal,
        'total_resume': total_resume,
        'total_belum_upload': total_belum_upload,
        'stats_proposal': stats_proposal,
        'stats_resume': stats_resume,
        'keyword': keyword,
        'status_proposal': status_proposal,
        'status_resume': status_resume,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'dosen_list': dosen_list,
        'total_tanpa_dosen': total_tanpa_dosen,
    }

    return render(request, 'kaprodi/monitoring.html', context)


# =========================================================
# LAPORAN
# =========================================================
@login_required
def kaprodi_laporan(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    total_mahasiswa = Mahasiswa.objects.count()
    total_dosen = Dosen.objects.count()  # TAMBAHKAN
    total_dospem = DosenPembimbing.objects.count()
    total_dosen_cp = DosenCP.objects.count()  # TAMBAHKAN
    total_tim = Tim.objects.count()
    total_proposal = ProposalCapstone.objects.count()
    total_resume = Resume.objects.count()

    return render(request, 'kaprodi/laporan.html', {
        'total_mahasiswa': total_mahasiswa,
        'total_dosen': total_dosen,  # TAMBAHKAN
        'total_dospem': total_dospem,
        'total_dosen_cp': total_dosen_cp,  # TAMBAHKAN
        'total_tim': total_tim,
        'total_proposal': total_proposal,
        'total_resume': total_resume,
    })


# =========================================================
# PROFILE KAPRODI
# =========================================================
@login_required
def kaprodi_profile(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    user = request.user
    dosen, created = Dosen.objects.get_or_create(user=user)

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
        return redirect('capstone_system:kaprodi_profile')

    return render(request, 'kaprodi/profile.html', {
        'user': user,
        'dosen': dosen,
    })


# =========================================================
# ARSIP MAHASISWA
# =========================================================
@login_required
def arsip_mahasiswa(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    keyword = request.GET.get("q", "")
    mahasiswa_list = Mahasiswa.objects.filter(status="ARSIP").select_related("user")

    if keyword:
        mahasiswa_list = mahasiswa_list.filter(
            Q(user__first_name__icontains=keyword) |
            Q(user__last_name__icontains=keyword) |
            Q(nim__icontains=keyword)
        )

    context = {
        "mahasiswa_list": mahasiswa_list,
        "keyword": keyword,
        "total_arsip": mahasiswa_list.count(),
    }

    return render(request, "kaprodi/arsip_mahasiswa.html", context)


# =========================================================
# LIST DOSEN CAPSTONE (KAPRODI)
# =========================================================
@login_required
def kaprodi_dosen_cp(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    dosen_capstone = DosenCP.objects.select_related("dosen", "dosen__user").all().order_by("dosen__user__first_name")

    context = {
        "dosen_capstone": dosen_capstone,
    }

    return render(request, "kaprodi/list_dosen_cp.html", context)


# =========================================================
# ARSIP TAHUNAN MAHASISWA (DIPERBAIKI)
# =========================================================
@login_required
@transaction.atomic
def arsip_tahunan(request):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    if request.method == 'POST':
        ids = request.POST.getlist('mahasiswa')
        if not ids:
            messages.warning(request, 'Pilih minimal satu mahasiswa.')
            return redirect('capstone_system:kaprodi_mahasiswa')

        mahasiswa_list = Mahasiswa.objects.filter(id__in=ids).select_related('user', 'dosen_pembimbing')
        
        # Kumpulkan dosen pembimbing yang perlu diupdate
        dospem_to_update = set()

        for mahasiswa in mahasiswa_list:
            # Hanya arsipkan yang statusnya AKTIF atau NONAKTIF
            if mahasiswa.status in ["AKTIF", "NONAKTIF"]:
                if mahasiswa.status == "AKTIF" and mahasiswa.dosen_pembimbing:
                    dospem_to_update.add(mahasiswa.dosen_pembimbing)

                mahasiswa.status = 'ARSIP'
                mahasiswa.save()
                mahasiswa.user.is_active = False
                mahasiswa.user.save()

        # Update status dosen pembimbing setelah semua perubahan
        for dospem in dospem_to_update:
            dospem.update_status()

        messages.success(request, f'{len(mahasiswa_list)} mahasiswa berhasil diarsipkan.')

    return redirect('capstone_system:kaprodi_mahasiswa')


# =========================================================
# EDIT BATAS BIMBINGAN DOSEN PEMBIMBING (KAPRODI)
# =========================================================
@login_required
def edit_batas_dospem(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    dospem = get_object_or_404(DosenPembimbing, id=id)

    if request.method == "POST":
        batas = int(request.POST.get("batas_bimbingan"))
        if batas < dospem.jumlah_bimbingan:
            messages.error(request, f"Batas minimal adalah {dospem.jumlah_bimbingan} karena saat ini dosen masih membimbing {dospem.jumlah_bimbingan} mahasiswa.")
            return redirect("capstone_system:edit_batas_dospem", id=id)

        dospem.batas_bimbingan = batas
        dospem.save()
        dospem.update_status()

        messages.success(request, "Batas bimbingan berhasil diperbarui.")
        return redirect("capstone_system:kaprodi_dospem")

    return render(request, "kaprodi/edit_batas_dospem.html", {"dospem": dospem})


# =========================================================
# HAPUS DOSEN (KAPRODI)
# =========================================================
@login_required
@transaction.atomic
def hapus_dosen(request, id):
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    dosen = get_object_or_404(Dosen, id=id)

    if Mahasiswa.objects.filter(dosen_pembimbing__dosen=dosen).exists():
        messages.error(request, "Dosen tidak dapat dihapus karena masih menjadi pembimbing mahasiswa.")
        return redirect("capstone_system:kaprodi_dosen")

    DosenPembimbing.objects.filter(dosen=dosen).delete()
    DosenCP.objects.filter(dosen=dosen).delete()
    dosen.user.delete()

    messages.success(request, "Data dosen berhasil dihapus.")
    return redirect("capstone_system:kaprodi_dosen")


# =========================================================
# UPLOAD MAHASISWA VIA EXCEL
# =========================================================
@login_required
def upload_mahasiswa_view(request):
    """Menampilkan form upload mahasiswa"""
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response
    
    form = UploadMahasiswaForm()
    context = {
        'form': form,
        'title': 'Upload Data Mahasiswa',
        'breadcrumb': [
            {'name': 'Dashboard', 'url': 'capstone_system:kaprodi_home'},
            {'name': 'Upload Mahasiswa', 'url': '#'},
        ]
    }
    return render(request, 'kaprodi/upload_mahasiswa.html', context)


@login_required
@csrf_exempt
def upload_mahasiswa_process(request):
    """Proses upload file Excel"""
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method tidak diizinkan'}, status=405)
    
    form = UploadMahasiswaForm(request.POST, request.FILES)
    
    if not form.is_valid():
        return JsonResponse({
            'success': False,
            'message': 'Validasi gagal',
            'errors': form.errors
        }, status=400)
    
    file = request.FILES['file']
    
    try:
        df = pd.read_excel(file)
        
        required_columns = ['nim', 'nama', 'kelas', 'angkatan']
        df.columns = df.columns.str.lower().str.strip()
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return JsonResponse({
                'success': False,
                'message': f'Kolom yang diperlukan tidak ditemukan: {", ".join(missing_columns)}'
            }, status=400)
        
        imported_data = []
        errors = []
        success_count = 0
        
        with transaction.atomic():
            for index, row in df.iterrows():
                row_num = index + 2
                
                nim = str(row['nim']).strip()
                nama = str(row['nama']).strip()
                kelas = str(row['kelas']).strip()
                angkatan = str(row['angkatan']).strip()
                
                if not nim:
                    errors.append(f"Baris {row_num}: NIM tidak boleh kosong")
                    continue
                
                if not nama:
                    errors.append(f"Baris {row_num}: Nama tidak boleh kosong")
                    continue
                
                if not kelas:
                    errors.append(f"Baris {row_num}: Kelas tidak boleh kosong")
                    continue
                
                if not angkatan:
                    errors.append(f"Baris {row_num}: Angkatan tidak boleh kosong")
                    continue
                
                if User.objects.filter(username=nim).exists():
                    errors.append(f"Baris {row_num}: NIM '{nim}' sudah terdaftar sebagai User")
                    continue
                
                if Mahasiswa.objects.filter(nim=nim).exists():
                    errors.append(f"Baris {row_num}: NIM '{nim}' sudah terdaftar sebagai Mahasiswa")
                    continue
                
                email = f"{nim}@student.ac.id"
                if User.objects.filter(email=email).exists():
                    errors.append(f"Baris {row_num}: Email '{email}' sudah digunakan")
                    continue
                
                try:
                    user = User.objects.create_user(
                        username=nim,
                        password=nim,
                        first_name=nama,
                        email=email,
                        role='MAHASISWA',
                        is_password_changed=False,
                        is_active=True
                    )
                    
                    mahasiswa = Mahasiswa.objects.create(
                        user=user,
                        nim=nim,
                        kelas=kelas,
                        angkatan=angkatan,
                        status='AKTIF',
                    )
                    
                    imported_data.append({
                        'nim': nim,
                        'nama': nama,
                        'kelas': kelas,
                        'angkatan': angkatan,
                        'email': email,
                        'password': nim
                    })
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Baris {row_num}: Gagal menyimpan data - {str(e)}")
                    continue
        
        response_data = {
            'success': True,
            'message': f'Berhasil mengupload {success_count} data mahasiswa',
            'data': {
                'success_count': success_count,
                'data': imported_data,
                'errors': errors,
                'total_rows': len(df)
            }
        }
        
        if errors:
            response_data['warning'] = f'Ada {len(errors)} data yang gagal diimport'
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Terjadi kesalahan: {str(e)}'
        }, status=500)


@login_required
def download_template_mahasiswa(request):
    """Download template Excel untuk upload mahasiswa"""
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response
    
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template Mahasiswa"
    
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='4CAF50', end_color='4CAF50', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    headers = ['NIM', 'Nama', 'Kelas', 'Angkatan']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    sample_data = [
        ['2201010001', 'John Doe', 'A', '2022'],
        ['2201010002', 'Jane Smith', 'B', '2022'],
        ['2201010003', 'Budi Santoso', 'C', '2023'],
        ['', '', '', ''],
        ['', '', '', ''],
    ]
    
    for row_idx, row_data in enumerate(sample_data, 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = border
            cell.alignment = Alignment(horizontal='center' if col_idx in [1, 3, 4] else 'left')
    
    for col in range(1, 5):
        column_letter = get_column_letter(col)
        ws.column_dimensions[column_letter].width = 20
    
    ws['F1'] = '📝 Catatan:'
    ws['F2'] = '1. NIM harus unik'
    ws['F3'] = '2. Semua kolom wajib diisi'
    ws['F4'] = '3. Password default = NIM'
    ws['F5'] = '4. Format: .xlsx atau .xls'
    
    for row in range(1, 6):
        ws[f'F{row}'].font = Font(size=10, color='666666')
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="template_mahasiswa.xlsx"'
    wb.save(response)
    
    return response


# =========================================================
# KEMBALIKAN SEMUA MAHASISWA DARI ARSIP (FUNGSI BARU)
# =========================================================
@login_required
@transaction.atomic
def kembalikan_semua_arsip(request):
    """
    Mengembalikan banyak mahasiswa dari status ARSIP ke AKTIF sekaligus
    """
    has_access, response = check_role(request, ['KAPRODI'])
    if not has_access:
        return response

    if request.method == 'POST':
        ids = request.POST.getlist('mahasiswa_ids')
        if not ids:
            messages.warning(request, 'Pilih minimal satu mahasiswa.')
            return redirect('capstone_system:arsip_mahasiswa')

        mahasiswa_list = Mahasiswa.objects.filter(id__in=ids, status="ARSIP").select_related('user', 'dosen_pembimbing')
        
        if not mahasiswa_list.exists():
            messages.warning(request, 'Tidak ada mahasiswa arsip yang dipilih.')
            return redirect('capstone_system:arsip_mahasiswa')

        success_count = 0
        failed_count = 0
        failed_names = []

        # Kumpulkan dosen pembimbing yang perlu diupdate
        dospem_to_update = set()

        for mahasiswa in mahasiswa_list:
            # Cek kuota dosen pembimbing
            if mahasiswa.dosen_pembimbing:
                dospem = mahasiswa.dosen_pembimbing
                if dospem.penuh:
                    failed_count += 1
                    failed_names.append(mahasiswa.user.get_full_name())
                    continue
                dospem_to_update.add(dospem)

            # Kembalikan ke status AKTIF
            mahasiswa.status = "AKTIF"
            mahasiswa.save()
            
            # Aktifkan user
            mahasiswa.user.is_active = True
            mahasiswa.user.save()
            
            success_count += 1

        # Update status dosen pembimbing setelah semua perubahan
        for dospem in dospem_to_update:
            dospem.update_status()

        # Pesan sukses
        if success_count > 0:
            messages.success(
                request, 
                f'{success_count} mahasiswa berhasil dikembalikan dari arsip.'
            )
        
        # Pesan gagal (jika ada)
        if failed_count > 0:
            messages.error(
                request, 
                f'{failed_count} mahasiswa gagal dikembalikan karena kuota dosen penuh: {", ".join(failed_names)}'
            )

    return redirect('capstone_system:arsip_mahasiswa')