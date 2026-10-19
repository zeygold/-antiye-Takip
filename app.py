from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import sqlite3
import os
from datetime import datetime
import calendar

app = Flask(__name__)

DATA_DIR = '/opt/render/project/data'
if os.path.exists(DATA_DIR):
    DB_NAME = os.path.join(DATA_DIR, 'santiye.db')
else:
    DB_NAME = 'santiye.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personeller (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            gorev TEXT,
            ucret_tipi TEXT DEFAULT 'Gunluk',
            ucret REAL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS puantaj (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personel_id INTEGER,
            tarih TEXT,
            durum REAL,
            not_aciklama TEXT,
            UNIQUE(personel_id, tarih)
        )
    ''')
    try:
        cursor.execute('ALTER TABLE puantaj ADD COLUMN not_aciklama TEXT')
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hareketler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personel_id INTEGER,
            tarih TEXT,
            tip TEXT,
            tutar REAL,
            aciklama TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS giderler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            kategori TEXT,
            tutar REAL,
            aciklama TEXT
        )
    ''')
    conn.commit()
    conn.close()

ANA_SAYFA_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Şantiye & Personel Takip</title>
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#212529">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #e9ecef; font-size: 15px; -webkit-tap-highlight-color: transparent; margin: 0; padding: 0; }
        .container-fluid { padding: 8px !important; width: 100% !important; max-width: 100% !important; margin: 0 !important; }
        .card { margin-bottom: 14px; border-radius: 12px; border: none; box-shadow: 0 3px 10px rgba(0,0,0,0.06); padding: 14px; background: #ffffff; }
        .form-control, .form-select { height: 48px; font-size: 16px; border-radius: 10px; border: 1.5px solid #ced4da; }
        .btn { height: 50px; font-size: 16px; border-radius: 10px; font-weight: bold; }
        .puantaj-box { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; }
        .puantaj-input { width: 48px; height: 40px; text-align: center; padding: 2px; font-size: 15px; font-weight: bold; border-radius: 8px; }
        .has-note { background-color: #fff3cd !important; border-color: #ffe69c !important; }
        .btn-note { font-size: 11px; font-weight: bold; padding: 3px 6px; border-radius: 6px; background-color: #e9ecef; color: #333; text-decoration: none; display: block; width: 48px; text-align: center; }
        
        .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 8px; }
        .table th, .table td { padding: 10px 6px; vertical-align: middle; white-space: nowrap; }
        
        .pazar-gunu { background-color: #ffe6e6 !important; }

        .sticky-col {
            position: sticky;
            left: 0;
            background-color: #ffffff;
            z-index: 2;
        }
        thead .sticky-col {
            background-color: #212529 !important;
            color: #ffffff;
            z-index: 3;
        }

        #toast-msg {
            position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); z-index: 9999;
            display: none; padding: 12px 24px; background-color: #198754; color: white;
            border-radius: 30px; font-weight: bold; font-size: 14px; box-shadow: 0 6px 16px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
<div id="toast-msg">Kaydedildi ve Hesaplandı ✔</div>

<nav class="navbar navbar-dark bg-dark mb-2 py-3 shadow-sm rounded-0">
    <div class="container-fluid px-3 d-flex justify-content-between align-items-center">
        <span class="navbar-brand fw-bold fs-5">🏗️ Şantiye & Personel</span>
        <span class="navbar-text text-white small fw-bold">{{ secili_ay_str }}</span>
    </div>
</nav>

<div class="container-fluid">
    <div class="card">
        <form method="GET" class="row g-2 align-items-center m-0">
            <div class="col-4 p-0"><label class="fw-bold fs-6">📅 Dönem:</label></div>
            <div class="col-8 p-0">
                <input type="month" name="donem" value="{{ secili_donem }}" class="form-control" onchange="this.form.submit()">
            </div>
        </form>
    </div>

    <div class="card">
        <h5 class="fw-bold border-bottom pb-2 mb-3 text-primary">➕ Yeni Personel Ekle</h5>
        <form action="/personel-ekle" method="POST" class="row g-3">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-12"><input type="text" name="ad_soyad" class="form-control" placeholder="Ad Soyad" required></div>
            <div class="col-12"><input type="text" name="gorev" class="form-control" placeholder="Görev (Örn: Elektrikçi / Kalıpçı)"></div>
            <div class="col-6">
                <select name="ucret_tipi" class="form-select">
                    <option value="Gunluk">Günlük Yevmiye</option>
                    <option value="Aylik">Aylık Maaş</option>
                </select>
            </div>
            <div class="col-6"><input type="number" step="0.01" name="ucret" class="form-control" placeholder="Tutar (TL)" required></div>
            <div class="col-12"><button type="submit" class="btn btn-primary w-100 shadow-sm">Personeli Kaydet</button></div>
        </form>
    </div>

    <div class="card">
        <h5 class="fw-bold border-bottom pb-2 mb-3 text-dark">📊 Puantaj & Hakediş Tablosu</h5>
        <div class="table-responsive">
            <table class="table table-bordered table-hover text-center mb-1">
                <thead class="table-dark">
                    <tr>
                        <th class="text-start sticky-col" style="min-width: 140px; box-shadow: 2px 0 5px rgba(0,0,0,0.1);">Ad Soyad</th>
                        <th style="min-width: 60px;">Tip</th>
                        <th style="min-width: 70px;">Ücret</th>
                        {% for gb in takvim_gunleri %}
                            <th style="min-width: 55px;" class="{% if gb.gun_str == 'Paz' %}bg-danger text-white{% endif %}">
                                <div style="font-size: 13px;">{{ gb.gun_no }}</div>
                                <div style="font-size: 10px; opacity: 0.85;">{{ gb.gun_str }}</div>
                            </th>
                        {% endfor %}
                        <th style="min-width: 60px;">Gün</th>
                        <th style="min-width: 85px;">Hakediş</th>
                        <th style="min-width: 85px;">Avans</th>
                        <th style="min-width: 85px;">Kalan</th>
                        <th style="min-width: 75px;">İşlem</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p in personeller %}
                    <tr id="row_p_{{ p.id }}" data-ucret="{{ p.ucret }}" data-ucrettipi="{{ p.ucret_tipi }}" data-ayingunsayisi="{{ ayin_gun_sayisi }}">
                        <td class="text-start fw-bold sticky-col" style="box-shadow: 2px 0 5px rgba(0,0,0,0.1);">
                            {{ p.ad_soyad }}<br><span class="text-muted fw-normal small">{{ p.gorev }}</span>
                        </td>
                        <td><span class="badge bg-{{ 'info text-dark' if p.ucret_tipi == 'Aylik' else 'secondary' }}" style="font-size:11px;">{{ 'Aylık' if p.ucret_tipi == 'Aylik' else 'Günlük' }}</span></td>
                        <td class="fw-bold">{{ "{:,.0f}".format(p.ucret) }}</td>
                        {% for gb in takvim_gunleri %}
                            {% set tarih_str = gb.tarih_str %}
                            {% set p_info = p.puantaj_dict.get(tarih_str, {}) %}
                            <td class="{% if gb.gun_str == 'Paz' %}pazar-gunu{% endif %}">
                                <div class="puantaj-box">
                                    <input type="text" inputmode="decimal"
                                           value="{{ p_info.get('durum', '') }}" 
                                           class="form-control puantaj-input p-input-val {% if p_info.get('not_aciklama') %}has-note{% endif %}"
                                           id="p_input_{{ p.id }}_{{ tarih_str }}"
                                           data-personelid="{{ p.id }}"
                                           oninput="otomatikKaydet({{ p.id }}, '{{ tarih_str }}')">
                                    <button type="button" class="btn-note border-0 py-1" id="btn_not_{{ p.id }}_{{ tarih_str }}"
                                            onclick="modalNotAc({{ p.id }}, '{{ tarih_str }}')">
                                       {{ '📍Not' if p_info.get('not_aciklama') else '+Not' }}
                                    </button>
                                </div>
                            </td>
                        {% endfor %}
                        <td class="fw-bold" id="toplam_gun_{{ p.id }}">{{ p.toplam_gun }}g</td>
                        <td class="text-success fw-bold" id="hakedis_{{ p.id }}">{{ "{:,.0f}".format(p.hakedis) }}₺</td>
                        <td class="text-danger fw-bold">{{ "{:,.0f}".format(p.toplam_avans) }}₺</td>
                        <td class="fw-bold text-primary" id="kalan_{{ p.id }}">{{ "{:,.0f}".format(p.kalan) }}₺</td>
                        <td><a href="/personel-ekstre/{{ p.id }}?donem={{ secili_donem }}" target="_blank" class="btn btn-outline-dark btn-sm py-2 px-3 fw-bold" style="font-size:12px; height: auto;">📄Ekstre</a></td>
                    </tr>
                    {% else %}
                    <tr><td colspan="{{ takvim_gunleri|length + 8 }}" class="text-center text-muted py-4">Henüz kayıtlı personel bulunmuyor.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div class="card">
        <h5 class="fw-bold border-bottom pb-2 mb-3 text-danger">💸 Avans / Ödeme Girişi</h5>
        <form action="/avans-ekle" method="POST" class="row g-3">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-12">
                <select name="personel_id" class="form-select" required>
                    <option value="">Personel Seçin...</option>
                    {% for p in personeller %}<option value="{{ p.id }}">{{ p.ad_soyad }}</option>{% endfor %}
                </select>
            </div>
            <div class="col-6"><input type="date" name="tarih" class="form-control" value="{{ bugun }}" required></div>
            <div class="col-6"><input type="number" step="0.01" name="tutar" class="form-control" placeholder="Tutar (TL)" required></div>
            <div class="col-12"><input type="text" name="aciklama" class="form-control" placeholder="Açıklama (Örn: Banka havalesi)"></div>
            <div class="col-12"><button type="submit" class="btn btn-danger w-100 shadow-sm">Avans / Ödeme Kaydet</button></div>
        </form>
    </div>

    <div class="card">
        <h5 class="fw-bold border-bottom pb-2 mb-3 text-warning text-dark">🏗️ Şantiye Günlük Gider Girişi</h5>
        <form action="/gider-ekle" method="POST" class="row g-3">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-12">
                <select name="kategori" class="form-select" required>
                    <option value="Malzeme / Nalbur">Malzeme / Nalbur</option>
                    <option value="Akaryakıt">Akaryakıt</option>
                    <option value="Yemek / Mutfak">Yemek / Mutfak</option>
                    <option value="Nakliye / Lojistik">Nakliye / Lojistik</option>
                    <option value="Alet / Kiralama">Alet / Kiralama</option>
                    <option value="Diğer Harcamalar">Diğer Harcamalar</option>
                </select>
            </div>
            <div class="col-6"><input type="date" name="tarih" class="form-control" value="{{ bugun }}" required></div>
            <div class="col-6"><input type="number" step="0.01" name="tutar" class="form-control" placeholder="Tutar (TL)" required></div>
            <div class="col-12"><input type="text" name="aciklama" class="form-control" placeholder="Açıklama (Örn: 10 torba çimento)" required></div>
            <div class="col-12"><button type="submit" class="btn btn-warning w-100 shadow-sm fw-bold">Şantiye Gideri Ekle</button></div>
        </form>
    </div>

    <div class="card mb-5">
        <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-3">
            <h5 class="fw-bold m-0 text-dark">🛒 Bu Ayki Giderler</h5>
            <span class="badge bg-danger fs-5 px-3 py-2">{{ "{:,.2f}".format(toplam_gider) }} TL</span>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle mb-0">
                <thead><tr><th>Tarih</th><th>Kategori</th><th>Açıklama</th><th class="text-end">Tutar</th></tr></thead>
                <tbody>
                    {% for g in giderler %}
                    <tr><td>{{ g.tarih }}</td><td><span class="badge bg-secondary">{{ g.kategori }}</span></td><td>{{ g.aciklama }}</td><td class="text-end fw-bold text-danger">{{ "{:,.2f}".format(g.tutar) }} TL</td></tr>
                    {% else %}
                    <tr><td colspan="4" class="text-center text-muted py-3">Bu ay kayıtlı gider bulunmuyor.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<div class="modal fade" id="notModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content p-2">
      <div class="modal-header"><h5 class="modal-title fw-bold">📍 Şantiye / Servis Noktası Notu</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">
        <input type="hidden" id="modal_p_id"><input type="hidden" id="modal_tarih">
        <label class="form-label small text-muted mb-2">Gittiği Yerler (Örn: Mor Salkım Villası, Erben İnşaat):</label>
        <input type="text" id="modal_not_text" class="form-control py-3" placeholder="Şantiye adını yazın...">
      </div>
      <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">İptal</button><button type="button" class="btn btn-primary fw-bold" onclick="modalNotKaydet()">Notu Kaydet</button></div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
var myModal;
document.addEventListener("DOMContentLoaded", function() { myModal = new bootstrap.Modal(document.getElementById('notModal')); });

function personeliGuncelleHesapla(personelId) {
    var row = document.getElementById('row_p_' + personelId);
    if(!row) return;
    
    var ucret = parseFloat(row.getAttribute('data-ucret')) || 0;
    var ucretTipi = row.getAttribute('data-ucrettipi');
    var ayinGunSayisi = parseInt(row.getAttribute('data-ayingunsayisi')) || 30;
    
    var inputs = row.querySelectorAll('.p-input-val');
    var toplamGun = 0;
    inputs.forEach(function(input) {
        var valStr = input.value.trim().replace(',', '.');
        var val = parseFloat(valStr);
        if(!isNaN(val)) {
            toplamGun += val;
        }
    });
    
    var hakedis = 0;
    if(ucretTipi === 'Aylik') {
        hakedis = (toplamGun >= ayinGunSayisi) ? ucret : (ucret / ayinGunSayisi) * toplamGun;
    } else {
        hakedis = ucret * toplamGun;
    }
    
    var avansCellText = document.getElementById('kalan_' + personelId).previousElementSibling.previousElementSibling.innerText;
    var temizAvans = avansCellText.replace('₺', '').split('.').join('').replace(',', '.');
    var avansTutar = parseFloat(temizAvans) || 0;
    var kalan = hakedis - avansTutar;
    
    document.getElementById('toplam_gun_' + personelId).innerText = toplamGun + 'g';
    document.getElementById('hakedis_' + personelId).innerText = hakedis.toLocaleString('tr-TR', {maximumFractionDigits: 0, minimumFractionDigits: 0}) + '₺';
    document.getElementById('kalan_' + personelId).innerText = kalan.toLocaleString('tr-TR', {maximumFractionDigits: 0, minimumFractionDigits: 0}) + '₺';
}

function otomatikKaydet(personelId, tarih, notVal = null) {
    var inputElem = document.getElementById('p_input_' + personelId + '_' + tarih);
    var durumVal = inputElem.value.trim().replace(',', '.');
    
    personeliGuncelleHesapla(personelId);
    
    fetch('/api/puantaj-guncelle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ personel_id: personelId, tarih: tarih, durum: durumVal, not_aciklama: notVal })
    }).then(r => r.json()).then(data => {
        if(data.success) {
            var toast = document.getElementById('toast-msg');
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 1000);
        }
    });
}

function modalNotAc(pId, tarih) {
    document.getElementById('modal_p_id').value = pId;
    document.getElementById('modal_tarih').value = tarih;
    document.getElementById('modal_not_text').value = '';
    myModal.show();
}

function modalNotKaydet() {
    var pId = document.getElementById('modal_p_id').value;
    var tarih = document.getElementById('modal_tarih').value;
    var text = document.getElementById('modal_not_text').value;
    myModal.hide();
    
    var btn = document.getElementById('btn_not_' + pId + '_' + tarih);
    if(text.trim() !== '') {
        btn.innerText = '📍Not';
        document.getElementById('p_input_' + pId + '_' + tarih).classList.add('has-note');
    } else {
        btn.innerText = '+Not';
        document.getElementById('p_input_' + pId + '_' + tarih).classList.remove('has-note');
    }
    
    otomatikKaydet(pId, tarih, text);
}
</script>
</body>
</html>
"""

EKSTRE_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ekstre - {{ personel.ad_soyad }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>body { background-color: #fff; font-size: 14px; color: #000; } .ekstre-box { max-width: 800px; margin: 15px auto; padding: 20px; } @media print { .no-print { display: none !important; } }</style>
</head>
<body>
<div class="container text-center my-3 no-print"><button onclick="window.print()" class="btn btn-primary fw-bold">🖨️ Sayfayı Yazdır / PDF Kaydet</button></div>
<div class="ekstre-box">
    <div class="d-flex justify-content-between border-bottom pb-3 mb-4">
        <div><h3 class="fw-bold m-0 fs-4">🏗️ PERSONEL HESAP EKSTRESİ</h3><small class="text-muted">Dönem: {{ secili_ay_str }}</small></div>
        <div class="text-end"><h5 class="fw-bold mb-0">{{ personel.ad_soyad }}</h5><small>{{ personel.gorev }}</small></div>
    </div>
    <div class="row text-center mb-4 g-2">
        <div class="col-3"><div class="border p-2 rounded"><small class="text-muted">Birim</small><div class="fw-bold fs-6">{{ "{:,.0f}".format(personel.ucret) }} TL</div></div></div>
        <div class="col-3"><div class="border p-2 rounded"><small class="text-muted">Çalışılan</small><div class="fw-bold fs-6">{{ toplam_gun }} Gün</div></div></div>
        <div class="col-3"><div class="border p-2 rounded"><small class="text-muted">Hakediş</small><div class="fw-bold fs-6 text-success">{{ "{:,.0f}".format(hakedis) }} TL</div></div></div>
        <div class="col-3"><div class="border p-2 rounded"><small class="text-muted">Bakiye</small><div class="fw-bold fs-6 text-primary">{{ "{:,.0f}".format(kalan) }} TL</div></div></div>
    </div>
    <h5 class="fw-bold border-bottom pb-2 mb-3">📅 Puantaj ve Görev Yerleri Dökümü</h5>
    <table class="table table-bordered text-center align-middle mb-4">
        <thead class="table-light"><tr><th>Tarih</th><th>Durum</th><th>Şantiye/Not</th><th>Tarih</th><th>Durum</th><th>Şantiye/Not</th></tr></thead>
        <tbody>
            {% for row in puantaj_rows %}
            <tr>
                <td>{{ row[0].tarih }}</td><td>{{ 'Tam (1.0)' if row[0].durum == 1.0 else ('Yarım (0.5)' if row[0].durum == 0.5 else 'Gelmedi') }}</td><td class="text-start fw-bold">{{ row[0].not_aciklama or '-' }}</td>
                {% if row[1] %}
                <td>{{ row[1].tarih }}</td><td>{{ 'Tam (1.0)' if row[1].durum == 1.0 else ('Yarım (0.5)' if row[1].durum == 0.5 else 'Gelmedi') }}</td><td class="text-start fw-bold">{{ row[1].not_aciklama or '-' }}</td>
                {% else %}<td>-</td><td>-</td><td>-</td>{% endif %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <h5 class="fw-bold border-bottom pb-2 mb-3">💸 Avans ve Ödeme Kayıtları</h5>
    <table class="table table-striped mb-4">
        <thead><tr><th>Tarih</th><th>Açıklama</th><th class="text-end">Tutar</th></tr></thead>
        <tbody>
            {% for a in avanslar %}
            <tr><td>{{ a.tarih }}</td><td>{{ a.aciklama or 'Avans' }}</td><td class="text-end fw-bold text-danger">{{ "{:,.2f}".format(a.tutar) }} TL</td></tr>
            {% else %}<tr><td colspan="3" class="text-center text-muted">Kayıtlı ödeme bulunmuyor.</td></tr>{% endfor %}
            <tr class="table-light fw-bold"><td colspan="2" class="text-end">Toplam Ödenen:</td><td class="text-end text-danger fw-bold">{{ "{:,.2f}".format(toplam_avans) }} TL</td></tr>
        </tbody>
    </table>
    <div class="row mt-5 text-center">
        <div class="col-6"><p class="mb-5 fw-bold">Teslim Eden (Şantiye Yetkilisi)</p><p>İmza: .......................................</p></div>
        <div class="col-6"><p class="mb-5 fw-bold">Teslim Alan (Personel)</p><p>İmza: .......................................</p></div>
    </div>
</div>
</body>
</html>
"""

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Şantiye & Personel Takip", "short_name": "Şantiye Takip", "start_url": "/", "display": "standalone",
        "background_color": "#212529", "theme_color": "#212529",
        "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/1048/1048953.png", "sizes": "512x512", "type": "image/png"}]
    })

@app.route('/')
def ana_sayfa():
    secili_donem = request.args.get('donem', datetime.now().strftime('%Y-%m'))
    yil, ay = map(int, secili_donem.split('-'))
    ayin_gun_sayisi = calendar.monthrange(yil, ay)[1]
    
    gun_kisaltmalari = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
    takvim_gunleri = []
    for gun in range(1, ayin_gun_sayisi + 1):
        dt = datetime(yil, ay, gun)
        index = dt.weekday()
        takvim_gunleri.append({
            'gun_no': gun,
            'gun_str': gun_kisaltmalari[index],
            'tarih_str': f"{yil}-{ay:02d}-{gun:02d}"
        })
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM personeller')
    personeller_db = cursor.fetchall()
    
    personeller = []
    for p in personeller_db:
        cursor.execute('SELECT tarih, durum, not_aciklama FROM puantaj WHERE personel_id = ? AND strftime("%Y-%m", tarih) = ?', (p['id'], secili_donem))
        puantaj_rows = cursor.fetchall()
        puantaj_dict = {row['tarih']: {'durum': row['durum'], 'not_aciklama': row['not_aciklama']} for row in puantaj_rows}
        
        p_gun = sum([float(val['durum']) for val in puantaj_dict.values() if val['durum'] is not None])
        if p['ucret_tipi'] == 'Aylik':
            hakedis = p['ucret'] if p_gun >= ayin_gun_sayisi else (p['ucret'] / ayin_gun_sayisi) * p_gun
        else:
            hakedis = p['ucret'] * p_gun
            
        cursor.execute('SELECT SUM(tutar) as toplam_avans FROM hareketler WHERE personel_id = ? AND strftime("%Y-%m", tarih) = ? AND tip = "Avans"', (p['id'], secili_donem))
        p_avans = cursor.fetchone()['toplam_avans'] or 0.0
        
        personeller.append({
            'id': p['id'], 'ad_soyad': p['ad_soyad'], 'gorev': p['gorev'], 'ucret_tipi': p['ucret_tipi'],
            'ucret': p['ucret'], 'puantaj_dict': puantaj_dict, 'toplam_gun': p_gun, 'hakedis': hakedis,
            'toplam_avans': p_avans, 'kalan': hakedis - p_avans
        })
        
    cursor.execute('SELECT * FROM giderler WHERE strftime("%Y-%m", tarih) = ? ORDER BY tarih DESC', (secili_donem,))
    giderler = cursor.fetchall()
    toplam_gider = sum([g['tutar'] for g in giderler])
    conn.close()
    
    return render_template_string(ANA_SAYFA_HTML, personeller=personeller, secili_donem=secili_donem, 
                                  secili_ay_str=datetime(yil, ay, 1).strftime('%B %Y'), bugun=datetime.now().strftime('%Y-%m-%d'),
                                  yil=yil, ay=ay, ayin_gun_sayisi=ayin_gun_sayisi, takvim_gunleri=takvim_gunleri, giderler=giderler, toplam_gider=toplam_gider)

@app.route('/api/puantaj-guncelle', methods=['POST'])
def api_puantaj_guncelle():
    data = request.json
    p_id = data.get('personel_id')
    tarih = data.get('tarih')
    durum_raw = data.get('durum')
    not_aciklama = data.get('not_aciklama')
    
    durum = None
    if durum_raw is not None and str(durum_raw).strip() != '':
        try:
            durum = float(str(durum_raw).replace(',', '.'))
        except ValueError:
            pass

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT durum, not_aciklama FROM puantaj WHERE personel_id = ? AND tarih = ?', (p_id, tarih))
    row = cursor.fetchone()
    
    yeni_durum = durum if durum is not None else (row['durum'] if row else None)
    yeni_not = not_aciklama if not_aciklama is not None else (row['not_aciklama'] if row else None)
    
    if yeni_durum is not None or yeni_not is not None:
        cursor.execute('''
            INSERT INTO puantaj (personel_id, tarih, durum, not_aciklama) VALUES (?, ?, ?, ?)
            ON CONFLICT(personel_id, tarih) DO UPDATE SET durum=COALESCE(excluded.durum, puantaj.durum), not_aciklama=COALESCE(excluded.not_aciklama, puantaj.not_aciklama)
        ''', (p_id, tarih, yeni_durum, yeni_not))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/personel-ekstre/<int:personel_id>')
def personel_ekstre(personel_id):
    secili_donem = request.args.get('donem', datetime.now().strftime('%Y-%m'))
    yil, ay = map(int, secili_donem.split('-'))
    ayin_gun_sayisi = calendar.monthrange(yil, ay)[1]
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM personeller WHERE id = ?', (personel_id,))
    personel = cursor.fetchone()
    
    puantaj_list = []
    toplam_gun = 0.0
    for gun in range(1, ayin_gun_sayisi + 1):
        tarih_str = f"{yil}-{ay:02d}-{gun:02d}"
        cursor.execute('SELECT durum, not_aciklama FROM puantaj WHERE personel_id = ? AND tarih = ?', (personel_id, tarih_str))
        row = cursor.fetchone()
        durum = row['durum'] if row and row['durum'] is not None else 0.0
        toplam_gun += durum
        puantaj_list.append({'tarih': tarih_str, 'durum': durum, 'not_aciklama': row['not_aciklama'] if row else ''})
        
    puantaj_rows = [(puantaj_list[i], puantaj_list[i+1] if i+1 < len(puantaj_list) else None) for i in range(0, len(puantaj_list), 2)]
    
    if personel['ucret_tipi'] == 'Aylik':
        hakedis = personel['ucret'] if toplam_gun >= ayin_gun_sayisi else (personel['ucret'] / ayin_gun_sayisi) * toplam_gun
    else:
        hakedis = personel['ucret'] * toplam_gun
        
    cursor.execute('SELECT * FROM hareketler WHERE personel_id = ? AND strftime("%Y-%m", tarih) = ? ORDER BY tarih ASC', (personel_id, secili_donem))
    avanslar = cursor.fetchall()
    toplam_avans = sum([a['tutar'] for a in avanslar])
    conn.close()
    
    return render_template_string(EKSTRE_HTML, personel=personel, secili_ay_str=datetime(yil, ay, 1).strftime('%B %Y'),
                                  puantaj_rows=puantaj_rows, toplam_gun=toplam_gun, hakedis=hakedis, avanslar=avanslar,
                                  toplam_avans=toplam_avans, kalan=hakedis - toplam_avans)

@app.route('/personel-ekle', methods=['POST'])
def personel_ekle():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO personeller (ad_soyad, gorev, ucret_tipi, ucret) VALUES (?, ?, ?, ?)',
                   (request.form['ad_soyad'], request.form.get('gorev', ''), request.form.get('ucret_tipi', 'Gunluk'), float(request.form.get('ucret', 0))))
    conn.commit()
    conn.close()
    return redirect(url_for('ana_sayfa', donem=request.form.get('donem', datetime.now().strftime('%Y-%m'))))

@app.route('/avans-ekle', methods=['POST'])
def avans_ekle():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO hareketler (personel_id, tarih, tip, tutar, aciklama) VALUES (?, ?, ?, ?, ?)',
                   (request.form['personel_id'], request.form['tarih'], 'Avans', float(
