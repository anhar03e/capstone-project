# views/base.py - COMPLETE FIXED VERSION
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import HttpResponse, JsonResponse
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.messages import get_messages
from django.contrib.sessions.models import Session

from django.contrib.auth import (
    login,
    logout,
    update_session_auth_hash
)
from django.contrib.auth.views import LoginView, PasswordResetView
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.utils import timezone
from django.db.models import F, Q
from django.db import transaction

# Import untuk email
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site

# Import logging
import logging

from ..models import (
    Mahasiswa,
    Dosen,
    DosenCP,
    DosenPembimbing,
    Tim,
    AnggotaTim,
    ProposalCapstone,
    Resume,
    PengajuanDospem,
    JadwalKonsultasi,
    BookingJadwal,
    User,
    RiwayatFeedbackProposal,
    RiwayatFeedbackResume,
)

from ..forms import DosenForm, UserForm, JadwalForm, ProposalForm, ResumeForm

# Setup logging
logger = logging.getLogger(__name__)

# =========================================================
# ROLE CHECKER HELPER
# =========================================================
def check_role(request, allowed_roles, redirect_to=None):
    """
    Cek apakah user memiliki role yang diizinkan.
    Returns: (has_access, redirect_response)
    """
    if not request.user.is_authenticated:
        messages.error(request, 'Silakan login terlebih dahulu.')
        return False, redirect('capstone_system:login')
    
    if request.user.role not in allowed_roles:
        messages.error(request, 'Anda tidak memiliki akses ke halaman ini.')
        
        if not redirect_to:
            role_redirects = {
                'MAHASISWA': 'capstone_system:mahasiswa_home',
                'DOSENCP': 'capstone_system:dosencp_home',
                'DOSENPB': 'capstone_system:dosenpb_home',
                'KAPRODI': 'capstone_system:kaprodi_home',
            }
            redirect_to = role_redirects.get(request.user.role, 'capstone_system:login')
        
        return False, redirect(redirect_to)
    
    return True, None

# =========================================================
# HELPER
# =========================================================
def get_tim_user(mahasiswa):
    return AnggotaTim.objects.select_related('tim').filter(
        mahasiswa=mahasiswa,
        status_persetujuan='APPROVED'
    ).first()

def get_proposal_ketua(mahasiswa):
    anggota = AnggotaTim.objects.select_related('tim').filter(
        mahasiswa=mahasiswa,
        status_persetujuan='APPROVED'
    ).first()

    if anggota:
        return ProposalCapstone.objects.filter(
            tim=anggota.tim
        ).first()

    return None

def get_dosen_pb(user):
    try:
        return DosenPembimbing.objects.select_related('dosen__user').get(
            dosen__user=user
        )
    except DosenPembimbing.DoesNotExist:
        return None

# =========================================================
# CUSTOM AUTHENTICATION FORM - FIXED
# =========================================================
class CustomAuthenticationForm(AuthenticationForm):
    """
    Custom Authentication Form dengan pesan error yang spesifik.
    """
    
    # OVERRIDE error_messages
    error_messages = {
        'invalid_login': "NIM/NIP atau password yang Anda masukkan salah. Silakan coba lagi.",
        'inactive': "Akun Anda telah dinonaktifkan.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ubah label username menjadi NIM/NIP
        self.fields['username'].label = "NIM / NIP"
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Masukkan NIM / NIP'
        })
        self.fields['password'].widget.attrs.update({
            'placeholder': 'Masukkan password'
        })

    def clean(self):
        """
        Override clean() untuk menangani error sebelum super() dipanggil
        """
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        # Jika username atau password kosong, biarkan Django handle
        if not username or not password:
            return super().clean()
        
        # CEK STATUS USER SEBELUM AUTHENTICATE
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # User tidak ditemukan, biarkan Django handle
            return super().clean()
        
        # CEK APAKAH USER NONAKTIF
        if not user.is_active:
            # Cek apakah user adalah mahasiswa
            try:
                mahasiswa = Mahasiswa.objects.get(user=user)
                if mahasiswa.status == "NONAKTIF":
                    raise forms.ValidationError(
                        "❌ Akun Anda telah dinonaktifkan oleh Kaprodi.\n"
                        "Silakan hubungi Kaprodi untuk informasi lebih lanjut.",
                        code='inactive',
                    )
                elif mahasiswa.status == "ARSIP":
                    raise forms.ValidationError(
                        "📦 Akun Anda telah diarsipkan.\n"
                        "Silakan hubungi Kaprodi untuk informasi lebih lanjut.",
                        code='inactive',
                    )
                else:
                    raise forms.ValidationError(
                        "⚠️ Akun Anda tidak aktif.\n"
                        "Silakan hubungi administrator.",
                        code='inactive',
                    )
            except Mahasiswa.DoesNotExist:
                # Cek apakah user adalah dosen
                try:
                    dosen = Dosen.objects.get(user=user)
                    if dosen.status_aktif == "NONAKTIF":
                        raise forms.ValidationError(
                            "❌ Akun dosen Anda telah dinonaktifkan.\n"
                            "Silakan hubungi Kaprodi untuk informasi lebih lanjut.",
                            code='inactive',
                        )
                    else:
                        raise forms.ValidationError(
                            "⚠️ Akun Anda tidak aktif.\n"
                            "Silakan hubungi administrator.",
                            code='inactive',
                        )
                except Dosen.DoesNotExist:
                    raise forms.ValidationError(
                        "⚠️ Akun Anda tidak aktif.\n"
                        "Silakan hubungi administrator.",
                        code='inactive',
                    )
        
        # Lanjutkan ke authenticate
        return super().clean()

# =========================================================
# CUSTOM PASSWORD RESET VIEW WITH DEBUG LOG
# =========================================================
class CustomPasswordResetView(PasswordResetView):
    """
    Custom Password Reset View dengan debug logging untuk memastikan email terkirim
    """
    template_name = 'auth/password_reset.html'
    email_template_name = 'auth/password_reset_email.html'
    subject_template_name = 'auth/password_reset_subject.txt'
    success_url = reverse_lazy('capstone_system:password_reset_done')

    def form_valid(self, form):
        """
        Override untuk menambahkan debug log
        """
        email = form.cleaned_data.get('email')
        
        print("=" * 70)
        print("📧 RESET PASSWORD REQUEST")
        print("=" * 70)
        print(f"📧 Waktu: {timezone.now()}")
        print(f"📧 Email tujuan: {email}")
        print("=" * 70)
        
        # Cek apakah email terdaftar
        try:
            user = User.objects.get(email=email)
            print(f"✅ User ditemukan:")
            print(f"   - Username: {user.username}")
            print(f"   - Nama: {user.get_full_name()}")
            print(f"   - Role: {user.role}")
            print(f"   - Active: {user.is_active}")
            print("=" * 70)
        except User.DoesNotExist:
            print(f"❌ Email tidak terdaftar: {email}")
            print("=" * 70)
            messages.error(
                self.request,
                "❌ Email tidak terdaftar dalam sistem. Silakan coba lagi."
            )
            return self.render_to_response(self.get_context_data(form=form))
        
        # Kirim email
        try:
            # Panggil parent method untuk mengirim email
            response = super().form_valid(form)
            
            print("✅ EMAIL RESET PASSWORD BERHASIL DIKIRIM!")
            print(f"📧 Dikirim ke: {email}")
            print("📧 Silakan cek inbox atau folder SPAM")
            print("=" * 70)
            
            # Log ke file
            logger.info(f"Reset password email sent to: {email}")
            
            messages.success(
                self.request, 
                "✅ Link reset password telah dikirim ke email Anda. Silakan cek inbox atau folder SPAM."
            )
            return response
            
        except Exception as e:
            print(f"❌ GAGAL MENGIRIM EMAIL!")
            print(f"❌ Error: {str(e)}")
            print("=" * 70)
            logger.error(f"Reset password email failed: {str(e)}")
            
            messages.error(
                self.request, 
                f"❌ Gagal mengirim email. Error: {str(e)}"
            )
            return self.render_to_response(self.get_context_data(form=form))

    def form_invalid(self, form):
        """
        Override untuk menampilkan error
        """
        print("=" * 70)
        print("❌ RESET PASSWORD FAILED")
        print("=" * 70)
        print(f"❌ Form errors: {form.errors}")
        print("=" * 70)
        
        messages.error(
            self.request,
            "❌ Gagal mengirim link reset password. Pastikan email Anda terdaftar."
        )
        return super().form_invalid(form)

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        """
        Override send_mail untuk debug
        """
        print("=" * 70)
        print("📧 SENDING EMAIL DETAILS")
        print("=" * 70)
        print(f"📧 From: {from_email}")
        print(f"📧 To: {to_email}")
        print(f"📧 Subject Template: {subject_template_name}")
        print(f"📧 Email Template: {email_template_name}")
        print("=" * 70)
        
        # Render email
        subject = render_to_string(subject_template_name, context)
        subject = ''.join(subject.splitlines())
        
        body = render_to_string(email_template_name, context)
        
        print("📧 EMAIL BODY PREVIEW:")
        print("-" * 70)
        # Tampilkan 500 karakter pertama
        if len(body) > 500:
            print(body[:500] + "...")
        else:
            print(body)
        print("-" * 70)
        
        try:
            # Kirim email
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=from_email,
                to=[to_email]
            )
            email.content_subtype = "html"
            email.send()
            
            print("✅ EMAIL BERHASIL DIKIRIM!")
            print("=" * 70)
            return True
        except Exception as e:
            print(f"❌ GAGAL MENGIRIM EMAIL: {str(e)}")
            print("=" * 70)
            raise

# =========================================================
# LOGIN & LOGOUT
# =========================================================
class CustomLoginView(LoginView):

    template_name = 'login.html'
    authentication_form = CustomAuthenticationForm

    def form_valid(self, form):
        user = form.get_user()
        response = super().form_valid(form)
        current_session = self.request.session.session_key

        if user.session_key:
            if user.session_key != current_session:
                Session.objects.filter(session_key=user.session_key).delete()

        user.session_key = current_session
        user.save(update_fields=["session_key"])

        return response

    def form_invalid(self, form):
        """
        Tampilkan pesan error dari form
        """
        if form.errors:
            # Cek error di field
            if 'username' in form.errors:
                messages.error(self.request, "NIM/NIP yang Anda masukkan tidak terdaftar.")
            elif 'password' in form.errors:
                messages.error(self.request, "Password yang Anda masukkan salah.")
            else:
                # Ambil error dari __all__
                error_messages = form.errors.get('__all__', [])
                if error_messages:
                    messages.error(self.request, error_messages[0])
                else:
                    messages.error(self.request, "NIM/NIP atau password yang Anda masukkan salah. Silakan coba lagi.")
        else:
            messages.error(self.request, "NIM/NIP atau password yang Anda masukkan salah. Silakan coba lagi.")
        
        return super().form_invalid(form)

    def get_success_url(self):
        user = self.request.user

        if not user.is_password_changed:
            return reverse_lazy('capstone_system:force_change_password')

        if user.role == 'MAHASISWA':
            return reverse_lazy('capstone_system:mahasiswa_home')
        elif user.role == 'DOSENCP':
            return reverse_lazy('capstone_system:dosencp_home')
        elif user.role == 'DOSENPB':
            return reverse_lazy('capstone_system:dosenpb_home')
        elif user.role == 'KAPRODI':
            return reverse_lazy('capstone_system:kaprodi_home')

        return reverse_lazy('capstone_system:home')

# =========================================================
# FORCE CHANGE PASSWORD
# =========================================================
@login_required
def force_change_password(request):
    user = request.user

    storage = get_messages(request)
    for _ in storage:
        pass

    if user.is_password_changed:
        return redirect('capstone_system:home')

    if request.method == 'POST':
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if not email or not password1 or not password2:
            messages.error(request, "Semua field wajib diisi.")
            return redirect('capstone_system:force_change_password')

        if password1 != password2:
            messages.error(request, "Konfirmasi password tidak sama.")
            return redirect('capstone_system:force_change_password')

        user.email = email
        user.set_password(password1)
        user.is_password_changed = True
        user.save()

        update_session_auth_hash(request, user)

        messages.success(request, "Password berhasil diperbarui.")

        if user.role == 'MAHASISWA':
            return redirect('capstone_system:mahasiswa_home')
        elif user.role == 'DOSENCP':
            return redirect('capstone_system:dosencp_home')
        elif user.role == 'DOSENPB':
            return redirect('capstone_system:dosenpb_home')
        elif user.role == 'KAPRODI':
            return redirect('capstone_system:kaprodi_home')

        return redirect('capstone_system:home')

    return render(request, 'auth/force_change_password.html')

# =========================================================
# LOGOUT
# =========================================================
def logout_view(request):
    if request.user.is_authenticated:
        request.user.session_key = None
        request.user.save(update_fields=["session_key"])
        logout(request)

    messages.info(request, "Anda berhasil logout.")
    return redirect('capstone_system:login')

# =========================================================
# HOME
# =========================================================
@login_required
def home(request):
    user = request.user

    if user.role == 'MAHASISWA':
        return redirect('capstone_system:mahasiswa_home')
    elif user.role == 'DOSENCP':
        return redirect('capstone_system:dosencp_home')
    elif user.role == 'DOSENPB':
        return redirect('capstone_system:dosenpb_home')
    elif user.role == 'KAPRODI':
        return redirect('capstone_system:kaprodi_home')

    return redirect('capstone_system:login')