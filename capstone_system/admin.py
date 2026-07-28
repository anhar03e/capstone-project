from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Mahasiswa, Dosen, ProposalCapstone, Resume,
    DosenPembimbing, DosenCP, PengajuanDospem,
    Tim, AnggotaTim
)

# =========================================================
# CUSTOM USER ADMIN
# =========================================================
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role Info', {'fields': ('role',)}),
    )
    list_display = ('username', 'first_name', 'last_name', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)

admin.site.register(User, UserAdmin)


# =========================================================
# MAHASISWA ADMIN
# =========================================================
class MahasiswaAdmin(admin.ModelAdmin):
    list_display = ('nim', 'user', 'kelas', 'angkatan')
    search_fields = ('nim', 'user__username', 'kelas', 'angkatan')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(role="MAHASISWA")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

admin.site.register(Mahasiswa, MahasiswaAdmin)


# =========================================================
# DOSEN ADMIN
# =========================================================
class DosenAdmin(admin.ModelAdmin):
    list_display = ('nip', 'user', 'bidang_keahlian', 'status_aktif')
    list_filter = ('status_aktif',)
    search_fields = ('nip', 'user__username', 'bidang_keahlian')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(role__in=["DOSENCP", "DOSENPB"])
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

admin.site.register(Dosen, DosenAdmin)


# =========================================================
# DOSEN CP ADMIN
# =========================================================
class DosenCPAdmin(admin.ModelAdmin):
    list_display = ('dosen', 'tugas')
    search_fields = ('dosen__nip', 'dosen__user__username', 'tugas')

admin.site.register(DosenCP, DosenCPAdmin)


# =========================================================
# DOSEN PEMBIMBING ADMIN
# =========================================================
class DosenPembimbingAdmin(admin.ModelAdmin):
    list_display = (
        'dosen',
        'batas_bimbingan',
        'jumlah_bimbingan',
        'sisa_kuota',
        'status',
    )

    list_filter = (
        'status',
    )

    search_fields = (
        'dosen__nip',
        'dosen__user__username',
    )

admin.site.register(DosenPembimbing, DosenPembimbingAdmin)


# =========================================================
# TIM ADMIN
# =========================================================
class TimAdmin(admin.ModelAdmin):
    list_display = ('nama_tim', 'status', 'dibuat_pada')
    list_filter = ('status',)
    search_fields = ('nama_tim',)

admin.site.register(Tim, TimAdmin)


# =========================================================
# ANGGOTA TIM ADMIN
# =========================================================
class AnggotaTimAdmin(admin.ModelAdmin):
    list_display = ('mahasiswa', 'tim', 'role', 'status_persetujuan')
    list_filter = ('role', 'status_persetujuan')
    search_fields = ('mahasiswa__nim', 'tim__nama_tim')

admin.site.register(AnggotaTim, AnggotaTimAdmin)


# =========================================================
# PROPOSAL CAPSTONE ADMIN (UPDATED)
# =========================================================
@admin.register(ProposalCapstone)
class ProposalCapstoneAdmin(admin.ModelAdmin):

    def ketua(self, obj):
        ketua = obj.tim.anggota.filter(role='ketua').first()

        if ketua:
            return ketua.mahasiswa.user.get_full_name()

        return "-"

    ketua.short_description = "Ketua Tim"

    list_display = (
        'judul',
        'ketua',
        'tim',
        'mitra',
        'status_pb',
        'status_cp',
        'status_final_admin',
        'waktu_pengajuan'
    )

    list_filter = (
        'status_pb',
        'status_cp',
    )

    search_fields = (
        'judul',
        'mitra',
        'tim__nama_tim'
    )

    readonly_fields = (
        'waktu_pengajuan',
        'waktu_update',
    )

    fieldsets = (

        ('Informasi Proposal', {
            'fields': (
                'tim',
                'judul',
                'mitra',
                'file'
            )
        }),

        ('Review Dosen PB', {
            'fields': (
                'status_pb',
                'catatan_pb',
                'tanggal_review_pb'
            )
        }),

        ('Review Dosen CP', {
            'fields': (
                'status_cp',
                'catatan_cp',
                'tanggal_review_cp'
            )
        }),

        ('Informasi Sistem', {
            'fields': (
                'waktu_pengajuan',
                'waktu_update'
            )
        }),

    )

    def status_final_admin(self, obj):
        return obj.status_final

    status_final_admin.short_description = "Status Akhir"


# =========================================================
# RESUME ADMIN
# =========================================================
class ResumeAdmin(admin.ModelAdmin):
    list_display = ('sub_judul', 'mahasiswa', 'proposal', 'status', 'waktu_pengajuan')
    list_filter = ('status',)
    search_fields = ('sub_judul', 'mahasiswa__nim', 'proposal__judul')

admin.site.register(Resume, ResumeAdmin)


# =========================================================
# PENGAJUAN DOSPEM ADMIN
# =========================================================
class PengajuanDospemAdmin(admin.ModelAdmin):
    list_display = ('mahasiswa', 'resume', 'dosen_pembimbing', 'status', 'tanggal_pengajuan')
    list_filter = ('status',)
    search_fields = ('mahasiswa__nim', 'resume__sub_judul', 'dosen_pembimbing__dosen__nip')

admin.site.register(PengajuanDospem, PengajuanDospemAdmin)