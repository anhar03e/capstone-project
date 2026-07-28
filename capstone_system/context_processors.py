from .models import Mahasiswa, AnggotaTim

def anggota_tim_context(request):

    anggota_tim = None
    punya_tim = False
    is_ketua = False

    if request.user.is_authenticated:

        try:
            mahasiswa = Mahasiswa.objects.get(user=request.user)

            anggota_tim = AnggotaTim.objects.filter(
                mahasiswa=mahasiswa
            ).first()

            if anggota_tim:
                punya_tim = True

                if anggota_tim.role == "ketua":
                    is_ketua = True

        except Mahasiswa.DoesNotExist:
            pass

    return {
        'anggota_tim': anggota_tim,
        'punya_tim': punya_tim,
        'is_ketua': is_ketua,
    }