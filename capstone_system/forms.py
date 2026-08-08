from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from .models import (
    User, Role, Mahasiswa, Dosen, DosenCP, DosenPembimbing,
    ProposalCapstone, Resume, PengajuanDospem, JadwalKonsultasi
)
import os


# =========================================================
# FUNGSI VALIDASI FILE PDF
# =========================================================
def validate_pdf_file(value):
    """Validasi file harus PDF dan maksimal 5MB"""
    ext = os.path.splitext(value.name)[1].lower()
    if ext != '.pdf':
        raise ValidationError('Hanya file PDF yang diperbolehkan.')
    
    if value.size > 5 * 1024 * 1024:  # 5MB
        raise ValidationError('Ukuran file maksimal 5MB.')


# =========================================================
# USER FORMS
# =========================================================
class UserForm(UserChangeForm):
    """Form untuk edit user dengan multi-role"""
    
    # Field role TETAP ADA (backward compatibility)
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Role Utama'
    )
    
    # TAMBAHAN: Field untuk multi-role
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 4}),
        required=False,
        label='Roles (Multi-Role)',
        help_text='Pilih satu atau lebih role (Ctrl+Click untuk multi pilih)'
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'roles', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['roles'].initial = self.instance.roles.all()


class CustomUserCreationForm(UserCreationForm):
    """Form untuk membuat user baru dengan multi-role"""
    
    # Field role TETAP ADA (backward compatibility)
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Role Utama'
    )
    
    # TAMBAHAN: Field untuk multi-role
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 4}),
        required=False,
        label='Roles (Multi-Role)',
        help_text='Pilih satu atau lebih role (Ctrl+Click untuk multi pilih)'
    )
    
    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'role',
            'roles',
            'password1',
            'password2'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Simpan roles ManyToMany
            if self.cleaned_data.get('roles'):
                user.roles.set(self.cleaned_data['roles'])
        return user


# =========================================================
# MAHASISWA FORM
# =========================================================
class MahasiswaForm(forms.ModelForm):

    user = forms.ModelChoiceField(
        queryset=User.objects.filter(roles__name='MAHASISWA'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Mahasiswa"
    )

    class Meta:
        model = Mahasiswa
        fields = ['user', 'nim', 'kelas', 'angkatan', 'status', 'kategori']
        widgets = {
            'nim': forms.TextInput(attrs={'class': 'form-control'}),
            'kelas': forms.TextInput(attrs={'class': 'form-control'}),
            'angkatan': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'kategori': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['user'].queryset = User.objects.filter(roles__name='MAHASISWA')
        self.fields['user'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"


# =========================================================
# DOSEN FORM (DIPERBAIKI - DENGAN CHECKBOX MULTI-ROLE)
# =========================================================

# forms.py - Perbaiki DosenForm

class DosenForm(forms.ModelForm):

    PRODI_CHOICES = [
        ('Teknik Informatika', 'Teknik Informatika'),
        ('Teknik Rekayasa Perangkat Lunak', 'Teknik Rekayasa Perangkat Lunak'),
        ('Teknik Komputer', 'Teknik Komputer'),
        ('Teknik Informatika Multimedia', 'Teknik Informatika Multimedia'),
    ]

    nama_lengkap = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    # 🔥 PERUBAHAN: Multi-role untuk dosen dengan Checkbox + KAPRODI
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(name__in=['DOSENCP', 'DOSENPB', 'KAPRODI']),  # 🔥 TAMBAH KAPRODI
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input role-checkbox'}),
        required=True,
        label='Role Dosen',
        help_text='Centang satu atau lebih role yang sesuai'
    )

    prodi = forms.ChoiceField(
        choices=PRODI_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Dosen
        fields = [
            'nip',
            'prodi',
            'bidang_keahlian',
            'status_aktif',
        ]
        widgets = {
            'nip': forms.TextInput(attrs={'class': 'form-control'}),
            'bidang_keahlian': forms.TextInput(attrs={'class': 'form-control'}),
            'status_aktif': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['nama_lengkap'].initial = user.first_name
            self.fields['email'].initial = user.email
            self.fields['roles'].initial = user.roles.filter(name__in=['DOSENCP', 'DOSENPB', 'KAPRODI'])

    def save(self, commit=True):
        """Override save untuk update/create user data dengan multi-role"""
        dosen = super().save(commit=False)
        
        # 🔥 CEK APAKAH DOSEN SUDAH PUNYA USER
        if dosen.pk is None or not hasattr(dosen, 'user') or dosen.user is None:
            nama_lengkap = self.cleaned_data.get('nama_lengkap', '')
            email = self.cleaned_data.get('email', '')
            nip = self.cleaned_data.get('nip', '')
            
            def split_name(full_name):
                if not full_name:
                    return '', ''
                full_name = full_name.strip()
                parts = full_name.split()
                if len(parts) > 1:
                    return parts[0], ' '.join(parts[1:])
                return full_name, ''
            
            first_name, last_name = split_name(nama_lengkap)
            
            user = User.objects.create_user(
                username=nip,
                password=nip,
                first_name=first_name,
                last_name=last_name,
                email=email,
                role='DOSEN',
                is_password_changed=False,
                is_active=True,
            )
            
            dosen.user = user
            
            if commit:
                dosen.save()
        
        user = dosen.user
        user.first_name = self.cleaned_data.get('nama_lengkap', user.first_name)
        user.email = self.cleaned_data.get('email', user.email)
        
        # 🔥 UPDATE MULTI-ROLE (termasuk KAPRODI)
        selected_roles = self.cleaned_data.get('roles', [])
        
        # Hapus role lama yang terkait dengan dosen (DOSENCP, DOSENPB, KAPRODI)
        user.roles.remove(*user.roles.filter(name__in=['DOSENCP', 'DOSENPB', 'KAPRODI']))
        # Tambahkan role baru
        for role in selected_roles:
            user.roles.add(role)
        
        # 🔥 SET ACTIVE_ROLE
        if selected_roles:
            first_role = selected_roles[0]
            user.active_role = first_role.name if hasattr(first_role, 'name') else str(first_role)
        else:
            user.active_role = 'DOSEN'
        
        if commit:
            user.save()
            dosen.save()
            
            # 🔥 AUTO CREATE DOSENCP, DOSENPEMBIMBING, ATAU KAPRODI
            if user.roles.filter(name='DOSENCP').exists():
                DosenCP.objects.get_or_create(dosen=dosen, defaults={'tugas': 'Reviewer Capstone'})
            else:
                DosenCP.objects.filter(dosen=dosen).delete()
            
            if user.roles.filter(name='DOSENPB').exists():
                DosenPembimbing.objects.get_or_create(dosen=dosen)
            else:
                DosenPembimbing.objects.filter(dosen=dosen).delete()
            
            # 🔥 TAMBAH: Jika role KAPRODI, set user sebagai superuser
            if user.roles.filter(name='KAPRODI').exists():
                user.is_superuser = True
                user.is_staff = True
                user.save()
            else:
                # Jika tidak punya role KAPRODI, pastikan bukan superuser
                if not user.roles.filter(name='KAPRODI').exists():
                    user.is_superuser = False
                    user.is_staff = False
                    user.save()
        
        return dosen


# =========================================================
# DOSEN CP FORM
# =========================================================
class DosenCPForm(forms.ModelForm):
    class Meta:
        model = DosenCP
        fields = ['dosen', 'tugas']
        widgets = {
            'dosen': forms.Select(attrs={'class': 'form-select'}),
            'tugas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# =========================================================
# DOSEN PEMBIMBING FORM
# =========================================================
class DosenPembimbingForm(forms.ModelForm):
    class Meta:
        model = DosenPembimbing
        fields = [
            'dosen',
            'batas_bimbingan',
            'status'
        ]
        widgets = {
            'dosen': forms.Select(attrs={'class': 'form-select'}),
            'batas_bimbingan': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


# =========================================================
# PROPOSAL CAPSTONE FORM (VALIDASI 5MB)
# =========================================================
class ProposalForm(forms.ModelForm):
    class Meta:
        model = ProposalCapstone
        fields = [
            'judul',
            'mitra',
            'file',
        ]
        widgets = {
            'judul': forms.TextInput(attrs={'class': 'form-control'}),
            'mitra': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_file(self):
        """Validasi file PDF maksimal 5MB"""
        file = self.cleaned_data.get('file')
        if file:
            validate_pdf_file(file)
        return file


# =========================================================
# RESUME FORM (VALIDASI 5MB)
# =========================================================
class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = [
            'sub_judul',
            'file_resume',
        ]
        widgets = {
            'sub_judul': forms.TextInput(attrs={'class': 'form-control'}),
            'file_resume': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_file_resume(self):
        """Validasi file PDF maksimal 5MB"""
        file = self.cleaned_data.get('file_resume')
        if file:
            validate_pdf_file(file)
        return file


# =========================================================
# PENGAJUAN DOSPEM
# =========================================================
class PengajuanDospemForm(forms.ModelForm):
    class Meta:
        model = PengajuanDospem
        fields = [
            'dosen_pembimbing',
            'surat_permohonan_dospem',
        ]
        widgets = {
            'dosen_pembimbing': forms.Select(attrs={'class': 'form-select'}),
            'surat_permohonan_dospem': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


# =========================================================
# JADWAL FORM
# =========================================================
class JadwalForm(forms.ModelForm):
    class Meta:
        model = JadwalKonsultasi
        fields = ['tanggal', 'jam_mulai', 'jam_selesai', 'kuota']
        widgets = {
            'tanggal': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'jam_mulai': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'jam_selesai': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'kuota': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


# =========================================================
# UPLOAD MAHASISWA FORM
# =========================================================
class UploadMahasiswaForm(forms.Form):
    file = forms.FileField(
        label='Pilih File Excel',
        help_text='Format: .xlsx atau .xls, Maksimal 2MB',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls',
            'id': 'fileInput'
        })
    )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if not file:
            raise forms.ValidationError('Silakan pilih file terlebih dahulu.')
        
        # Validasi ekstensi
        allowed_extensions = ['.xlsx', '.xls']
        ext = os.path.splitext(file.name)[1].lower()
        
        if ext not in allowed_extensions:
            raise forms.ValidationError('File harus berformat .xlsx atau .xls')
        
        # Validasi ukuran (maks 2MB)
        if file.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Ukuran file maksimal 2MB')
        
        return file