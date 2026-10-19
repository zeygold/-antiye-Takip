from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import sqlite3
import os
from datetime import datetime
import calendar

app = Flask(__name__)
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
        body { background-color: #f4f6f9; font-size: 14px; -webkit-tap-highlight-color: transparent; }
        .card { margin-bottom: 14px; border-radius: 12px; border: none; box-shadow: 0 2px 6px rgba(0,0,0,0.06); padding: 14px; }
        
        /* Büyütülmüş Dokunmatik Kutular */
        .form-control-sm, .form-select-sm { height: 42px; font-size: 14px; border-radius: 8px; }
        .btn-sm { height: 44px; font-size: 15px; border-radius: 8px; }
        
        /* İki Sıralı Puantaj Kutuları */
        .puantaj-box { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; }
        .puantaj-input { width: 44px; height: 36px; text-align: center; padding: 2px; font-size: 14px; font-weight: bold; border-radius: 6px; }
        .has-note { background-color: #fff3cd !important; border-color: #ffe69c !important; }
        .btn-note { font-size: 10px; font-weight: bold; padding: 2px 5px; border-radius: 4px; background-color: #e9ecef; color: #495057; text-decoration: none; display: block; width: 44px; text-align: center; }
        
        .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 8px; }
        .table th, .table td { padding: 8px 4px; vertical-align: middle; }
        
        #toast-msg {
            position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); z-index: 9999;
            display: none; padding: 10px 22px; background-color: #198754; color: white;
            border-radius: 25px; font-weight: bold; font-size: 13px; box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        }
    </style>
</head>
<body>
<div id="toast-msg">Otomatik Kaydedildi ✔</div>

<nav class="navbar navbar-dark bg-dark mb-2 py-2">
    <div class="container-fluid px-2">
        <span class="navbar-brand fw-bold fs-6">🏗️ Şantiye & Personel Takip</span>
        <span class="navbar-text text-white small" style="font-size: 11px;">{{ secili_ay_str }}</span>
    </div>
</nav>

<div class="container-fluid px-2">
    <!-- Dönem Seçimi -->
    <div class="card bg-white">
        <form method="GET" class="row g-2 align-items-center m-0">
            <div class="col-auto p-0 me-2"><label class="fw-bold fs-6">Dönem:</label></div>
            <div class="col p-0">
                <input type="month" name="donem" value="{{ secili_donem }}" class="form-control form-control-sm" onchange="this.form.submit()">
            </div>
        </form>
    </div>

    <!-- Personel Ekleme -->
    <div class="card">
        <h6 class="fw-bold border-bottom pb-2 mb-2 fs-6">➕ Yeni Personel Ekle</h6>
        <form action="/personel-ekle" method="POST" class="row g-2">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-12"><input type="text" name="ad_soyad" class="form-control form-control-sm" placeholder="Ad Soyad" required></div>
            <div class="col-12"><input type="text" name="gorev" class="form-control form-control-sm" placeholder="Görev (Örn: Kalıpçı)"></div>
            <div class="col-6">
                <select name="ucret_tipi" class="form-select form-select-sm">
                    <option value="Gunluk">Günlük Yevmiye</option>
                    <option value="Aylik">Aylık Maaş</option>
                </select>
            </div>
            <div class="col-6"><input type="number" step="0.01" name="ucret" class="form-control form-control-sm" placeholder="Tutar (TL)" required></div>
            <div class="col-12"><button type="submit" class="btn btn-primary btn-sm w-100 fw-bold">Personeli Kaydet</button></div>
        </form>
    </div>

    <!-- Puantaj Tablosu -->
    <div class="card">
        <h6 class="fw-bold border-bottom pb-2 mb-2 fs-6">📅 Puantaj Tablosu</h6>
        <div class="table-responsive">
            <table class="table table-bordered table-hover text-center mb-1">
                <thead class="table-dark small">
                    <tr>
                        <th class="text-start" style="min-width: 120px;">Ad Soyad</th>
                        <th style="min-width: 50px;">Tip</th>
                        <th style="min-width: 60px;">Ücret</th>
                        {% for gun in range(1, ayin_gun_sayisi + 1) %}
                            <th style="min-width: 50px;">{{ gun }}</th>
                        {% endfor %}
                        <th style="min-width: 55px;">Gün</th>
                        <th style="min-width: 75px;">Hakediş</th>
                        <th style="min-width: 75px;">Avans</th>
                        <th style="min-width: 75px;">Kalan</th>
                        <th style="min-width: 65px;">İşlem</th>
                    </tr>
                </thead>
                <tbody class="small">
                    {% for p in personeller %}
                    <tr>
                        <td class="text-start fw-bold">{{ p.ad_soyad }}<br><span class="text-muted fw-normal" style="font-size:11px;">{{ p.gorev }}</span></td>
                        <td><span class="badge bg-{{ 'info text-dark' if p.ucret_tipi == 'Aylik' else 'secondary' }}" style="font-size:10px;">{{ 'Aylık' if p.ucret_tipi == 'Aylik' else 'Günlük' }}</span></td>
                        <td>{{ "{:,.0f}".format(p.ucret) }}</td>
                        {% for gun in range(1, ayin_gun_sayisi + 1) %}
                            {% set tarih_str = "{}-{:02d}-{:02d}".format(yil, ay, gun) %}
                            {% set p_info = p.puantaj_dict.get(tarih_str, {}) %}
                            <td>
                                <div class="puantaj-box">
                                    <input type="number" step="0.5" min="0" max="1" 
                                           value="{{ p_info.get('durum', '') }}" 
                                           class="form-control form-control-sm puantaj-input {% if p_info.get('not_aciklama') %}has-note{% endif %}"
                                           id="p_input_{{ p.id }}_{{ tarih_str }}"
                                           onchange="otomatikKaydet({{ p.id }}, '{{ tarih_str }}')">
                                    <button type="button" class="btn-note border-0"
                                            onclick="modalNotAc({{ p.id }}, '{{ tarih_str }}', '{{ p_info.get('not_aciklama', '') }}')">
                                       {{ '📍Not' if p_info.get('not_aciklama') else '+Not' }}
                                    </button>
                                </div>
                            </td>
                        {% endfor %}
                        <td class="fw-bold">{{ p.toplam_gun }}g</td>
                        <td class="text-success fw-bold">{{ "{:,.0f}".format(p.hakedis) }}₺</td>
                        <td class="text-danger fw-bold">{{ "{:,.0f}".format(p.toplam_avans) }}₺</td>
                        <td class="fw-bold text-primary">{{ "{:,.0f}".format(p.kalan) }}₺</td>
                        <td><a href="/personel-ekstre/{{ p.id }}?donem={{ secili_donem }}" target="_blank" class="btn btn-outline-dark btn-sm py-1 px-2 fw-bold" style="font-size:11px; height: auto;">📄Ekstre</a></td>
                    </tr>
                    {% else %}
                    <tr><td colspan="{{ ayin_gun_sayisi + 8 }}" class="text-center text-muted py-3">Henüz personel yok.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Büyütülmüş Avans Girişi -->
    <div class="card">
        <h6 class="fw-bold border-bottom pb-2 mb-2 fs-6">💸 Avans / Ödeme Girişi</h6>
        <form action="/avans-ekle" method="POST" class="row g-2">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-12">
                <select name="personel_id" class="form-select form-select-sm" required>
                    <option value="">Personel Seçin...</option>
                    {% for p in personeller %}<option value="{{ p.id }}">{{ p.ad_soyad }}</option>{% endfor %}
                </select>
            </div>
            <div class="col-6"><input type="date" name="tarih" class="form-control form-control-sm" value="{{ bugun }}" required></div>
            <div class="col-6"><input type="number" step="0.01" name="tutar" class="form-control form-control-sm" placeholder="Tutar (TL)" required></div>
            <div class="col-12"><input type="text" name="aciklama" class="form-control form-control-sm" placeholder="Açıklama (Örn: Banka havalesi)"></div>
            <div class="col-12"><button type="submit" class="btn btn-danger btn-sm w-100 fw-bold">Avans Kaydet</button></div>
        </form>
    </div>

    <!-- Büyütülmüş Şantiye Günlük Gider Girişi -->
    <div class="card">
        <h6 class="fw-bold border-bottom pb-2 mb-2 fs-6">🏗️ Şantiye Günlük Gider Girişi</h6>
        <form action="/gider-ekle" method="POST" class="row g-2">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-12">
                <select name="kategori" class="form-select form-select-sm" required>
                    <option value="Malzeme / Nalbur">Malzeme / Nalbur</option>
                    <option value="Akaryakıt">Akaryakıt</option>
                    <option value="Yemek / Mutfak">Yemek / Mutfak</option>
                    <option value="Nakliye / Lojistik">Nakliye / Lojistik</option>
                    <option value="Alet / Kiralama">Alet / Kiralama</option>
                    <option value="Diğer Harcamalar">Diğer Harcamalar</option>
                </select>
            </div>
            <div class="col-6"><input type="date" name="tarih" class="form-control form-control-sm" value="{{ bugun }}" required></div>
            <div class="col-6"><input type="number" step="0.01" name="tutar" class="form-control form-control-sm" placeholder="Tutar (TL)" required></div>
            <div class="col-12"><input type="text" name="aciklama" class="form-control form-control-sm" placeholder="Açıklama (Örn: Çimento)" required></div>
            <div class="col-12"><button type="submit" class="btn btn-warning btn-sm w-100 fw-bold">Şantiye Gideri Ekle</button></div>
        </form>
    </div>

    <!-- Şantiye Gider Özeti -->
    <div class="card mb-4">
        <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
            <h6 class="fw-bold m-0 fs-6">🛒 Bu Ayki Giderler</h6>
            <span class="badge bg-danger fs-6">{{ "{:,.2f}".format(toplam_gider) }} TL</span>
        </div>
        <div class="table-responsive">
            <table class="table table-sm table-striped align-middle mb-0 small">
                <thead><tr><th>Tarih</th><th>Kategori</th><th>Açıklama</th><th class="text-end">Tutar</th></tr></thead>
                <tbody>
                    {% for g in giderler %}
                    <tr><td>{{ g.tarih }}</td><td><span class="badge bg-secondary" style="font-size:10px;">{{ g.kategori }}</span></td><td>{{ g.aciklama }}</td><td class="text-end fw-bold text-danger">{{ "{:,.2f}".format(g.tutar) }} TL</td></tr>
                    {% else %}
                    <tr><td colspan="4" class="text-center text-muted py-2">Gider yok.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<div class="modal fade" id="notModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header"><h6 class="modal-title fw-bold">📍 Şantiye / Görev Yeri Notu</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">
        <input type="hidden" id="modal_p_id"><input type="hidden" id="modal_tarih">
        <input type="text" id="modal_not_text" class="form-control" placeholder="Örn: Mor Salkım Villası, Erben İnşaat">
      </div>
      <div class="modal-footer"><button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">İptal</button><button type="button" class="btn btn-primary btn-sm fw-bold" onclick="modalNotKaydet()">Kaydet</button></div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
var myModal;
document.addEventListener("DOMContentLoaded", function() { myModal = new bootstrap.Modal(document.getElementById('notModal')); });
function otomatikKaydet(personelId, tarih, notVal = null) {
    var durumVal = document.getElementById('p_input_' + personelId + '_' + tarih).value;
    fetch('/api/puantaj-guncelle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ personel_id: personelId, tarih: tarih, durum: durumVal, not_aciklama: notVal })
    }).then(r => r.json()).then(data => {
        if(data.success) {
            var toast = document.getElementById('toast-msg');
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; location.reload(); }, 800);
        }
    });
}
function modalNotAc(pId, tarih, not) {
    document.getElementById('modal_p_id').value = pId;
    document.getElementById('modal_tarih').value = tarih;
    document.getElementById('modal_not_text').value = not || '';
    myModal.show();
}
function modalNotKaydet() {
    var pId = document.getElementById('modal_p_id').value;
    var tarih = document.getElementById('modal_tarih').value;
    var text = document.getElementById('modal_not_text').value;
    myModal.hide();
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
    <style>body { background-color: #fff; font-size: 13px; color: #000; } .ekstre-box { max-width: 800px; margin: 10px auto; padding: 15px; } @media print { .no-print { display: none !important; } }</style>
</head>
<body>
<div class="container text-center my-2 no-print"><button onclick="window.print()" class="btn btn-primary btn-sm fw-bold">🖨️ Yazdır / PDF Kaydet</button></div>
<div class="ekstre-box">
    <div class="d-flex justify-content-between border-bottom pb-2 mb-3">
        <div><h4 class="fw-bold m-0 fs-5">🏗️ PERSONEL HESAP EKSTRESİ</h4><small class="text-muted">Dönem: {{ secili_ay_str }}</small></div>
        <div class="text-end"><h6 class="fw-bold mb-0">{{ personel.ad_soyad }}</h6><small>{{ personel.gorev }}</small></div>
    </div>
    <div class="row text-center mb-3 g-2">
        <div class="col-3"><div class="border p-1 rounded"><small style="font-size:10px;">Birim</small><div class="fw-bold small">{{ "{:,.0f}".format(personel.ucret) }} TL</div></div></div>
        <div class="col-3"><div class="border p-1 rounded"><small style="font-size:10px;">Çalışılan</small><div class="fw-bold small">{{ toplam_gun }} Gün</div></div></div>
        <div class="col-3"><div class="border p-1 rounded"><small style="font-size:10px;">Hakediş</small><div class="fw-bold small text-success">{{ "{:,.0f}".format(hakedis) }} TL</div></div></div>
        <div class="col-3"><div class="border p-1 rounded"><small style="font-size:10px;">Bakiye</small><div class="fw-bold small text-primary">{{ "{:,.0f}".format(kalan) }} TL</div></div></div>
    </div>
    <h6 class="fw-bold border-bottom pb-1 mb-2">📅 Puantaj ve Görev Yerleri</h6>
    <table class="table table-sm table-bordered text-center align-middle mb-3 small">
        <thead class="table-light"><tr><th>Tarih</th><th>Durum</th><th>Şantiye/Not</th><th>Tarih</th><th>Durum</th><th>Şantiye/Not</th></tr></thead>
        <tbody>
            {% for row in puantaj_rows %}
            <tr>
                <td>{{ row[0].tarih }}</td><td>{{ 'Tam (1.0)' if row[0].durum == 1.0 else ('Yarım (0.5)' if row[0].durum == 0.5 else 'Gelmedi') }}</td><td class="text-start">{{ row[0].not_aciklama or '-' }}</td>
                {% if row[1] %}
                <td>{{ row[1].tarih }}</td><td>{{ 'Tam (1.0)' if row[1].durum == 1.0 else ('Yarım (0.5)' if row[1].durum == 0.5 else 'Gelmedi') }}</td><td class="text-start">{{ row[1].not_aciklama or '-' }}</td>
                {% else %}<td>-</td><td>-</td><td>-</td>{% endif %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <h6 class="fw-bold border-bottom pb-1 mb-2">💸 Avans / Ödemeler</h6>
    <table class="table table-sm table-striped mb-3 small">
        <thead><tr><th>Tarih</th><th>Açıklama</th><th class="text-end">Tutar</th></tr></thead>
        <tbody>
            {% for a in avanslar %}
            <tr><td>{{ a.tarih }}</td><td>{{ a.aciklama or 'Avans' }}</td><td class="text-end text-danger">{{ "{:,.2f}".format(a.tutar) }} TL</td></tr>
            {% else %}<tr><td colspan="3" class="text-center text-muted">Ödeme yok.</td></tr>{% endfor %}
            <tr class="table-light fw-bold"><td colspan="2" class="text-end">Toplam Ödenen:</td><td class="text-end text-danger">{{ "{:,.2f}".format(toplam_avans) }} TL</td></tr>
        </tbody>
    </table>
    <div class="row mt-4 text-center small">
        <div class="col-6"><p class="mb-4 fw-bold">Teslim Eden (Yetkili)</p><p>İmza: .......................</p></div>
        <div class="col-6"><p class="mb-4 fw-bold">Teslim Alan (Personel)</p><p>İmza: .......................</p></div>
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
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM personeller')
    personeller_db = cursor.fetchall()
    
    personeller = []
    for p in personeller_db:
        cursor.execute('SELECT tarih, durum, not_aciklama FROM puantaj WHERE personel_id = ? AND strftime("%Y-%m", tarih) = ?', (p['id'], secili_donem
