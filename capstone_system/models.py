from django.db import models
from django.contrib.auth.models import AbstractUser


# =========================================================
# USER
# =========================================================
class User(AbstractUser):

    ROLE_CHOICES = (
        ('MAHASISWA', 'Mahasiswa'),
        ('DOSENCP', 'Dosen CP'),
        ('DOSENPB', 'Dosen Pembimbing'),
        ('KAPRODI', 'Kaprodi'),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        null=True,
        blank=True
    )

    is_password_changed = models.BooleanField(
        default=False
    )

    # Menyimpan session aktif user
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


# =========================================================
# MAHASISWA
# =========================================================
class Mahasiswa(models.Model):
    KATEGORI_CHOICES = (
        ('EPD', 'EPD'),
        ('SM', 'SM'),
    )

    STATUS_CHOICES = (
        ('AKTIF', 'Aktif'),
        ('NONAKTIF', 'Tidak Aktif'),
        ('ARSIP', 'Arsip'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nim = models.CharField(max_length=20, unique=True)
    kelas = models.CharField(max_length=5)
    angkatan = models.CharField(max_length=10)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AKTIF'
    )
    tanggal_masuk = models.DateField(null=True, blank=True)

    kategori = models.CharField(max_length=3, choices=KATEGORI_CHOICES, null=True, blank=True)

    dosen_pembimbing = models.ForeignKey(
        'DosenPembimbing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mahasiswa_bimbingan'
    )

    foto_profil = models.ImageField(upload_to='foto_profil/', null=True, blank=True)

    def __str__(self):
        return f"{self.nim} - {self.user.get_full_name()}"


# =========================================================
# DOSEN (MASTER)
# =========================================================
class Dosen(models.Model):
    STATUS_CHOICES = (
        ('AKTIF', 'Aktif'),
        ('NONAKTIF', 'Non Aktif'),
        ('PINDAH', 'Pindah Prodi'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nip = models.CharField(max_length=20, unique=True)
    bidang_keahlian = models.CharField(max_length=255)
    status_aktif = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AKTIF')
    prodi = models.CharField(max_length=100, default='Teknik Informatika')
    
    foto_profil = models.ImageField(upload_to='foto_dosen/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.nip})"


# =========================================================
# DOSEN PEMBIMBING (PB)
# =========================================================
class DosenPembimbing(models.Model):
    dosen = models.ForeignKey(
        Dosen,
        on_delete=models.CASCADE,
        related_name="pembimbing"
    )

    # Kuota maksimal mahasiswa bimbingan
    batas_bimbingan = models.PositiveIntegerField(default=5)

    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("FULL", "Full"),
        ("CLOSED", "Closed"),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="OPEN"
    )

    @property
    def jumlah_bimbingan(self):
        """
        Menghitung jumlah mahasiswa AKTIF yang dibimbing.
        """
        return Mahasiswa.objects.filter(
            dosen_pembimbing=self,
            status="AKTIF"
        ).count()

    @property
    def sisa_kuota(self):
        """
        Menghitung sisa kuota bimbingan.
        """
        return max(
            0,
            self.batas_bimbingan - self.jumlah_bimbingan
        )

    @property
    def penuh(self):
        """
        True jika kuota sudah penuh.
        """
        return self.jumlah_bimbingan >= self.batas_bimbingan

    def update_status(self):
        """
        Memperbarui status berdasarkan jumlah mahasiswa aktif.
        """
        if self.status == "CLOSED":
            return

        status_baru = (
            "FULL"
            if self.jumlah_bimbingan >= self.batas_bimbingan
            else "OPEN"
        )

        if self.status != status_baru:
            self.status = status_baru
            self.save(update_fields=["status"])

    def __str__(self):
        return f"{self.dosen.user.get_full_name()} ({self.dosen.nip})"


# =========================================================
# DOSEN CP
# =========================================================
class DosenCP(models.Model):
    dosen = models.ForeignKey(Dosen, on_delete=models.CASCADE, related_name='cp')
    tugas = models.TextField()

    def __str__(self):
        return f"{self.dosen.user.get_full_name()} (CP)"


# =========================================================
# TIM
# =========================================================
class Tim(models.Model):
    nama_tim = models.CharField(max_length=255)

    KATEGORI_CHOICES = (
        ('EPD', 'EPD'),
        ('SM', 'SM'),
    )

    kategori = models.CharField(max_length=3, choices=KATEGORI_CHOICES, null=True, blank=True)

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Disetujui'),
        ('REJECTED', 'Ditolak'),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nama_tim
    
    @property
    def can_edit(self):
        proposal = self.proposal.order_by('-waktu_pengajuan').first()

        # Belum pernah upload proposal
        if proposal is None:
            return True

        # Hanya boleh edit jika proposal terakhir ditolak
        return proposal.status_cp == 'DITOLAK'


# =========================================================
# ANGGOTA TIM
# =========================================================
class AnggotaTim(models.Model):
    ROLE_CHOICES = (
        ('ketua', 'Ketua'),
        ('anggota', 'Anggota'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Setuju'),
        ('REJECTED', 'Tolak'),
    )

    tim = models.ForeignKey(Tim, on_delete=models.CASCADE, related_name='anggota')
    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    kategori = models.CharField(max_length=3, choices=(('EPD','EPD'), ('SM','SM')), null=True, blank=True)

    status_persetujuan = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')


# =========================================================
# PROPOSAL CAPSTONE (CORE SYSTEM)
# =========================================================
class ProposalCapstone(models.Model):

    STATUS_CHOICES = (
        ('BELUM_REVIEW', 'Belum Review'),
        ('SEDANG_REVIEW', 'Sedang Review'),
        ('DITERIMA', 'Diterima'),
        ('DITOLAK', 'Ditolak'),
        ('REVISI', 'Perlu Revisi'),
    )

    tim = models.ForeignKey(Tim, on_delete=models.CASCADE, related_name='proposal', null=True, blank=True)

    cp_reviewer = models.ForeignKey(
        DosenCP,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposal_review'
    )

    judul = models.CharField(max_length=255)
    mitra = models.CharField(max_length=255)
    file = models.FileField(upload_to='proposal/')

    waktu_pengajuan = models.DateTimeField(auto_now_add=True)
    waktu_update = models.DateTimeField(auto_now=True)
    waktu_peninjauan = models.DateTimeField(null=True, blank=True)

    # =====================================================
    # REVIEW PB & CP (SOURCE OF TRUTH)
    # =====================================================

    status_pb = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BELUM_REVIEW')
    catatan_pb = models.TextField(blank=True, null=True)
    tanggal_review_pb = models.DateTimeField(null=True, blank=True)

    status_cp = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BELUM_REVIEW')
    catatan_cp = models.TextField(blank=True, null=True)
    tanggal_review_cp = models.DateTimeField(null=True, blank=True)

    # =====================================================
    # STATUS FINAL (COMPUTED - HANYA BERDASARKAN CP)
    # =====================================================
    @property
    def status_final(self):
        """
        🔥 PERUBAHAN: Status final hanya berdasarkan status_cp
        Karena proposal hanya direview oleh Dosen CP
        status_pb tetap disimpan untuk keperluan tracking/riwayat
        """
        return self.status_cp

    # =====================================================
    # STATUS FINAL LENGKAP (UNTUK KAPRODI / TRACKING)
    # =====================================================
    @property
    def status_lengkap(self):
        """
        Menampilkan status lengkap dari kedua reviewer
        Untuk keperluan Kaprodi / Tracking Status
        """
        if self.status_pb == 'DITOLAK' or self.status_cp == 'DITOLAK':
            return 'DITOLAK'

        if self.status_pb == 'REVISI' or self.status_cp == 'REVISI':
            return 'REVISI'

        if self.status_pb == 'DITERIMA' and self.status_cp == 'DITERIMA':
            return 'DITERIMA'

        if self.status_pb != 'BELUM_REVIEW' or self.status_cp != 'BELUM_REVIEW':
            return 'SEDANG_REVIEW'

        return 'BELUM_REVIEW'

    # =====================================================
    # PROGRESS (KAPRODI MONITORING)
    # =====================================================
    @property
    def progress_persen(self):
        progress = 0

        if self.status_pb != 'BELUM_REVIEW':
            progress += 40

        if self.status_cp != 'BELUM_REVIEW':
            progress += 40

        if self.status_pb == 'DITERIMA' and self.status_cp == 'DITERIMA':
            progress += 20

        return progress

    # =====================================================
    # CEK APAKAH PROPOSAL SUDAH VALID (DITERIMA)
    # =====================================================
    @property
    def is_diterima(self):
        """True jika proposal sudah diterima oleh CP"""
        return self.status_cp == 'DITERIMA'

    @property
    def is_ditolak(self):
        """True jika proposal ditolak oleh CP"""
        return self.status_cp == 'DITOLAK'

    @property
    def is_revisi(self):
        """True jika proposal perlu revisi oleh CP"""
        return self.status_cp == 'REVISI'

    @property
    def can_edit(self):
        """
        True jika proposal masih bisa diedit
        (hanya bisa diedit jika status_cp bukan DITERIMA)
        """
        return self.status_cp != 'DITERIMA'


# =========================================================
# RIWAYAT FEEDBACK PROPOSAL (LOG HISTORY)
# =========================================================
class RiwayatFeedbackProposal(models.Model):

    REVIEWER_CHOICES = (
        ('PB', 'Dosen Pembimbing'),
        ('CP', 'Dosen Capstone Project'),
    )

    proposal = models.ForeignKey(
        ProposalCapstone,
        on_delete=models.CASCADE,
        related_name='riwayat_feedback'
    )

    reviewer = models.CharField(
        max_length=2,
        choices=REVIEWER_CHOICES
    )

    dosen = models.ForeignKey(
        Dosen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=ProposalCapstone.STATUS_CHOICES
    )

    catatan = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# =========================================================
# RESUME
# =========================================================
class Resume(models.Model):

    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE)
    proposal = models.ForeignKey(ProposalCapstone, on_delete=models.CASCADE)

    judul_proposal = models.CharField(max_length=255)
    mitra = models.CharField(max_length=255)
    sub_judul = models.CharField(max_length=255)

    file_resume = models.FileField(upload_to='resume/')
    waktu_pengajuan = models.DateTimeField(auto_now_add=True)

    waktu_peninjauan = models.DateTimeField(null=True, blank=True)

    STATUS_CHOICES = (
        ('BELUM_REVIEW', 'Belum Review'),
        ('DISETUJUI', 'Disetujui'),
        ('DITOLAK', 'Ditolak'),
        ('REVISI', 'Revisi'),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BELUM_REVIEW')
    catatan_revisi = models.TextField(blank=True)

    def __str__(self):
        return f"{self.mahasiswa.nim}"

    @property
    def is_disetujui(self):
        """True jika resume sudah disetujui"""
        return self.status == 'DISETUJUI'

    @property
    def is_ditolak(self):
        """True jika resume ditolak"""
        return self.status == 'DITOLAK'

    @property
    def is_revisi(self):
        """True jika resume perlu revisi"""
        return self.status == 'REVISI'


# =========================================================
# RIWAYAT FEEDBACK RESUME (LOG HISTORY)
# =========================================================
class RiwayatFeedbackResume(models.Model):

    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name='riwayat_feedback'
    )

    dosen = models.ForeignKey(
        Dosen,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Resume.STATUS_CHOICES
    )

    catatan = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# =========================================================
# PENGAJUAN DOSPEM
# =========================================================
class PengajuanDospem(models.Model):

    mahasiswa = models.ForeignKey(Mahasiswa, on_delete=models.CASCADE, related_name='pengajuan_dospem')
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='pengajuan_dospem')
    dosen_pembimbing = models.ForeignKey(DosenPembimbing, on_delete=models.CASCADE, related_name='pengajuan')

    tanggal_pengajuan = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('DISETUJUI', 'Disetujui'),
        ('DITOLAK', 'Ditolak'),
        ('REVISI', 'Revisi'),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    sudah_direview = models.BooleanField(default=False)
    waktu_direview = models.DateTimeField(null=True, blank=True)
    catatan_dosen = models.TextField(blank=True)

    surat_permohonan_dospem = models.FileField(upload_to='surat_permohonan/')

    def __str__(self):
        return f"{self.mahasiswa.nim} → {self.dosen_pembimbing}"


# =========================================================
# JADWAL KONSULTASI (UPGRADE BOOKING SYSTEM)
# =========================================================
class JadwalKonsultasi(models.Model):

    dosen = models.ForeignKey(
        DosenPembimbing,
        on_delete=models.CASCADE,
        related_name='jadwal'
    )

    tanggal = models.DateField()
    jam_mulai = models.TimeField()
    jam_selesai = models.TimeField()

    # 🔥 SISTEM KUOTA
    kuota = models.IntegerField(default=3)
    jumlah_dipesan = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.tanggal} ({self.jam_mulai}-{self.jam_selesai})"

    # =========================
    # PROPERTY HELPERS
    # =========================
    @property
    def sisa_kuota(self):
        return self.kuota - self.jumlah_dipesan

    @property
    def penuh(self):
        return self.jumlah_dipesan >= self.kuota


# =========================================================
# BOOKING JADWAL KONSULTASI (UPGRADE BOOKING SYSTEM)
# =========================================================
class BookingJadwal(models.Model):

    STATUS_CHOICES = (
        ('BOOKED', 'Booked'),
        ('CANCELLED', 'Cancelled'),
        ('DONE', 'Done'),
    )

    mahasiswa = models.ForeignKey(
        Mahasiswa,
        on_delete=models.CASCADE,
        related_name='booking_jadwal'
    )

    jadwal = models.ForeignKey(
        JadwalKonsultasi,
        on_delete=models.CASCADE,
        related_name='booking'
    )

    tanggal_booking = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='BOOKED'
    )

    def __str__(self):
        return f"{self.mahasiswa.nim} - {self.jadwal}"

    # 🔥 ANTI DOUBLE BOOKING
    class Meta:
        unique_together = ('mahasiswa', 'jadwal')