from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import (
    User, Mahasiswa, Dosen, DosenCP, DosenPembimbing,
    ProposalCapstone, Resume, PengajuanDospem, JadwalKonsultasi
)

# =========================================================
# USER FORMS
# =========================================================
class UserForm(UserChangeForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'role',
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


class MahasiswaForm(forms.ModelForm):

    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role='MAHASISWA'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Mahasiswa"
    )

    class Meta:
        model = Mahasiswa
        fields = ['user', 'nim', 'kelas', 'angkatan']
        widgets = {
            'nim': forms.TextInput(attrs={'class': 'form-control'}),
            'kelas': forms.TextInput(attrs={'class': 'form-control'}),
            'angkatan': forms.TextInput(attrs={'class': 'form-control'}),
        }

    # =========================
    # TAMBAHAN PENTING
    # =========================
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['user'].queryset = User.objects.filter(role='MAHASISWA')

        self.fields['user'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})"

# =========================================================
# DOSEN FORM
# =========================================================
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

    role = forms.ChoiceField(
        choices=[
            ('DOSENCP', 'Dosen CP'),
            ('DOSENPB', 'Dosen Pembimbing'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['nama_lengkap'].initial = user.first_name
            self.fields['email'].initial = user.email
            self.fields['role'].initial = user.role

    def save(self, commit=True):
        dosen = super().save(commit=False)

        user = dosen.user
        user.first_name = self.cleaned_data['nama_lengkap']
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']

        if commit:
            user.save()
            dosen.save()

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
# PROPOSAL CAPSTONE FORM (FIXED)
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


# =========================================================
# RESUME FORM
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
        fields = ['tanggal', 'jam_mulai', 'jam_selesai']
        widgets = {
            'tanggal': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'jam_mulai': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'jam_selesai': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'kuota': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

# =========================================================
# UPLOAD MAHASISWA FORM (TAMBAHKAN INI)
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
        import os
        file = self.cleaned_data.get('file')
        
        # Validasi ekstensi
        allowed_extensions = ['.xlsx', '.xls']
        ext = os.path.splitext(file.name)[1].lower()
        
        if ext not in allowed_extensions:
            raise forms.ValidationError('File harus berformat .xlsx atau .xls')
        
        # Validasi ukuran (maks 2MB)
        if file.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Ukuran file maksimal 2MB')
        
        return file