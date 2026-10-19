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
            UNIQUE(personel_id, tarih)
        )
    ''')
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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Şantiye & Personel Takip</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-size: 13px; }
        .card { margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .puantaj-input { width: 42px; text-align: center; padding: 2px; font-size: 12px; font-weight: bold; }
        .table-responsive { overflow-x: auto; }
        #toast-msg {
            position: fixed; bottom: 20px; right: 20px; z-index: 9999;
            display: none; padding: 10px 20px; background-color: #198754; color: white;
            border-radius: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
<div id="toast-msg">Otomatik Kaydedildi ✔</div>

<nav class="navbar navbar-dark bg-dark mb-3">
    <div class="container-fluid">
        <a class="navbar-brand fw-bold" href="/">🏗️ Şantiye & Personel Takip</a>
        <span class="navbar-text text-white small">{{ secili_ay_str }}</span>
    </div>
</nav>

<div class="container-fluid px-3">
    <!-- Dönem Seçimi -->
    <div class="card p-2 bg-white">
        <form method="GET" class="row g-2 align-items-center">
            <div class="col-auto"><label class="fw-bold">Dönem Seçimi:</label></div>
            <div class="col-auto">
                <input type="month" name="donem" value="{{ secili_donem }}" class="form-control form-control-sm" onchange="this.form.submit()">
            </div>
        </form>
    </div>

    <!-- Personel Ekleme -->
    <div class="card p-3">
        <h6 class="fw-bold border-bottom pb-2">➕ Yeni Personel / İşçi Ekle</h6>
        <form action="/personel-ekle" method="POST" class="row g-2">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-md-3">
                <input type="text" name="ad_soyad" class="form-control form-control-sm" placeholder="Ad Soyad" required>
            </div>
            <div class="col-md-3">
                <input type="text" name="gorev" class="form-control form-control-sm" placeholder="Görev (Örn: Kalıpçı)">
            </div>
            <div class="col-md-2">
                <select name="ucret_tipi" class="form-select form-select-sm">
                    <option value="Gunluk">Günlük Yevmiye</option>
                    <option value="Aylik">Aylık Maaş</option>
                </select>
            </div>
            <div class="col-md-2">
                <input type="number" step="0.01" name="ucret" class="form-control form-control-sm" placeholder="Tutar (TL)" required>
            </div>
            <div class="col-md-2">
                <button type="submit" class="btn btn-primary btn-sm w-100 fw-bold">Kaydet</button>
            </div>
        </form>
    </div>

    <!-- Puantaj & Hakediş Tablosu -->
    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center border-bottom pb-2">
            <h6 class="fw-bold m-0">📅 Aylık Puantaj ve Hakediş Tablosu</h6>
            <small class="text-muted">Kutucuklara 1, 0.5 veya 0 yazın, <strong>otomatik kaydedilir!</strong></small>
        </div>
        <div class="table-responsive mt-2">
            <table class="table table-bordered table-hover align-middle text-center">
                <thead class="table-dark">
                    <tr>
                        <th style="min-width: 140px;">Ad Soyad</th>
                        <th>Tip</th>
                        <th>Ücret</th>
                        {% for gun in range(1, ayin_gun_sayisi + 1) %}
                            <th style="min-width: 42px;">{{ gun }}</th>
                        {% endfor %}
                        <th>Çalışılan</th>
                        <th>Hakediş</th>
                        <th>Avans/Ödeme</th>
                        <th>Kalan</th>
                        <th>İşlem</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p in personeller %}
                    <tr>
                        <td class="text-start fw-bold">{{ p.ad_soyad }} <br><small class="text-muted">{{ p.gorev }}</small></td>
                        <td>
                            {% if p.ucret_tipi == 'Aylik' %}
                                <span class="badge bg-info text-dark">Aylık</span>
                            {% else %}
                                <span class="badge bg-secondary">Günlük</span>
                            {% endif %}
                        </td>
                        <td>{{ "{:,.0f}".format(p.ucret) }}</td>
                        {% for gun in range(1, ayin_gun_sayisi + 1) %}
                            {% set tarih_str = "{}-{:02d}-{:02d}".format(yil, ay, gun) %}
                            <td>
                                <input type="number" step="0.5" min="0" max="1" 
                                       value="{{ p.puantaj_dict.get(tarih_str, '') }}" 
                                       class="form-control form-control-sm puantaj-input"
                                       onchange="otomatikKaydet({{ p.id }}, '{{ tarih_str }}', this.value)">
                            </td>
                        {% endfor %}
                        <td class="fw-bold">{{ p.toplam_gun }} gün</td>
                        <td class="text-success fw-bold">{{ "{:,.2f}".format(p.hakedis) }} TL</td>
                        <td class="text-danger fw-bold">{{ "{:,.2f}".format(p.toplam_avans) }} TL</td>
                        <td class="fw-bold text-primary">{{ "{:,.2f}".format(p.kalan) }} TL</td>
                        <td>
                            <a href="/personel-ekstre/{{ p.id }}?donem={{ secili_donem }}" target="_blank" class="btn btn-outline-dark btn-sm fw-bold">📄 Ekstre</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="{{ ayin_gun_sayisi + 8 }}" class="text-center text-muted">Henüz kayıtlı personel yok. Yukarıdan ekleyebilirsiniz.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Avans & Şantiye Giderleri Yan Yana -->
    <div class="row">
        <!-- Avans Girişi -->
        <div class="col-md-6">
            <div class="card p-3">
                <h6 class="fw-bold border-bottom pb-2">💸 Avans / Ödeme Girişi</h6>
                <form action="/avans-ekle" method="POST" class="row g-2">
                    <input type="hidden" name="donem" value="{{ secili_donem }}">
                    <div class="col-md-6">
                        <select name="personel_id" class="form-select form-select-sm" required>
                            <option value="">Personel Seçin...</option>
                            {% for p in personeller %}
                            <option value="{{ p.id }}">{{ p.ad_soyad }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-md-6">
                        <input type="date" name="tarih" class="form-control form-control-sm" value="{{ bugun }}" required>
                    </div>
                    <div class="col-md-6">
                        <input type="number" step="0.01" name="tutar" class="form-control form-control-sm" placeholder="Tutar (TL)" required>
                    </div>
                    <div class="col-md-6">
                        <input type="text" name="aciklama" class="form-control form-control-sm" placeholder="Açıklama (Örn: Banka havalesi)">
                    </div>
                    <div class="col-12">
                        <button type="submit" class="btn btn-danger btn-sm w-100 fw-bold">Avans / Ödeme Kaydet</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Şantiye Giderleri -->
        <div class="col-md-6">
            <div class="card p-3">
                <h6 class="fw-bold border-bottom pb-2">🏗️ Şantiye Günlük Gider Girişi</h6>
                <form action="/gider-ekle" method="POST" class="row g-2">
                    <input type="hidden" name="donem" value="{{ secili_donem }}">
                    <div class="col-md-6">
                        <select name="kategori" class="form-select form-select-sm" required>
                            <option value="Malzeme / Nalbur">Malzeme / Nalbur</option>
                            <option value="Akaryakıt">Akaryakıt</option>
                            <option value="Yemek / Mutfak">Yemek / Mutfak</option>
                            <option value="Nakliye / Lojistik">Nakliye / Lojistik</option>
                            <option value="Alet / Kiralama">Alet / Kiralama</option>
                            <option value="Diğer Harcamalar">Diğer Harcamalar</option>
                        </select>
                    </div>
                    <div class="col-md-6">
                        <input type="date" name="tarih" class="form-control form-control-sm" value="{{ bugun }}" required>
                    </div>
                    <div class="col-md-6">
                        <input type="number" step="0.01" name="tutar" class="form-control form-control-sm" placeholder="Gider Tutarı (TL)" required>
                    </div>
                    <div class="col-md-6">
                        <input type="text" name="aciklama" class="form-control form-control-sm" placeholder="Açıklama (Örn: 10 torba çimento)" required>
                    </div>
                    <div class="col-12">
                        <button type="submit" class="btn btn-warning btn-sm w-100 fw-bold">Şantiye Gideri Ekle</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Şantiye Gider Özeti -->
    <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center border-bottom pb-2">
            <h6 class="fw-bold m-0">🛒 Bu Ayki Şantiye Giderleri Listesi</h6>
            <span class="badge bg-danger fs-6">Toplam Gider: {{ "{:,.2f}".format(toplam_gider) }} TL</span>
        </div>
        <div class="table-responsive mt-2">
            <table class="table table-sm table-striped">
                <thead>
                    <tr>
                        <th>Tarih</th>
                        <th>Kategori</th>
                        <th>Açıklama</th>
                        <th class="text-end">Tutar</th>
                    </tr>
                </thead>
                <tbody>
                    {% for g in giderler %}
                    <tr>
                        <td>{{ g.tarih }}</td>
                        <td><span class="badge bg-secondary">{{ g.kategori }}</span></td>
                        <td>{{ g.aciklama }}</td>
                        <td class="text-end fw-bold text-danger">{{ "{:,.2f}".format(g.tutar) }} TL</td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" class="text-center text-muted">Bu ay henüz kayıtlı şantiye gideri yok.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
function otomatikKaydet(personelId, tarih, durum) {
    fetch('/api/puantaj-guncelle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ personel_id: personelId, tarih: tarih, durum: durum })
    })
    .then(response => response.json())
    .then(data => {
        if(data.success) {
            var toast = document.getElementById('toast-msg');
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; location.reload(); }, 800);
        }
    });
}
</script>
</body>
</html>
'''

EKSTRE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Personel Hesap Ekstresi - {{ personel.ad_soyad }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #fff; font-size: 13px; color: #000; }
        .ekstre-box { max-width: 800px; margin: 20px auto; padding: 20px; border: 1px solid #ccc; }
        @media print {
            .no-print { display: none !important; }
            .ekstre-box { border: none; max-width: 100%; padding: 0; }
        }
    </style>
</head>
<body>

<div class="container text-center my-3 no-print">
    <button onclick="window.print()" class="btn btn-primary btn-lg fw-bold">🖨️ Sayfayı Yazdır / PDF Kaydet</button>
</div>

<div class="ekstre-box">
    <div class="d-flex justify-content-between align-items-center border-bottom pb-3 mb-3">
        <div>
            <h3 class="fw-bold m-0">🏗️ ŞANTİYE PERSONEL HESAP EKSTRESİ</h3>
            <small class="text-muted">Dönem: {{ secili_ay_str }}</small>
        </div>
        <div class="text-end">
            <h5 class="fw-bold mb-0">{{ personel.ad_soyad }}</h5>
            <small>{{ personel.gorev }} | {{ 'Aylık Maaşlı' if personel.ucret_tipi == 'Aylik' else 'Günlük Yevmiyeli' }}</small>
        </div>
    </div>

    <!-- Özet Tablo -->
    <div class="row text-center mb-4">
        <div class="col-3">
            <div class="border p-2 rounded">
                <small class="text-muted">Birim Ücret</small>
                <div class="fw-bold fs-6">{{ "{:,.2f}".format(personel.ucret) }} TL</div>
            </div>
        </div>
        <div class="col-3">
            <div class="border p-2 rounded">
                <small class="text-muted">Toplam Çalışılan</small>
                <div class="fw-bold fs-6">{{ toplam_gun }} Gün</div>
            </div>
        </div>
        <div class="col-3">
            <div class="border p-2 rounded">
                <small class="text-muted">Toplam Hakediş</small>
                <div class="fw-bold fs-6 text-success">{{ "{:,.2f}".format(hakedis) }} TL</div>
            </div>
        </div>
        <div class="col-3">
            <div class="border p-2 rounded">
                <small class="text-muted">Net Alacak / Bakiye</small>
                <div class="fw-bold fs-6 text-primary">{{ "{:,.2f}".format(kalan) }} TL</div>
            </div>
        </div>
    </div>

    <!-- Puantaj Detayları -->
    <h6 class="fw-bold border-bottom pb-2">📅 Günlük Puantaj Dökümü</h6>
    <table class="table table-sm table-bordered text-center align-middle mb-4">
        <thead class="table-light">
            <tr>
                <th>Tarih</th>
                <th>Çalışma Durumu</th>
                <th>Tarih</th>
                <th>Çalışma Durumu</th>
            </tr>
        </thead>
        <tbody>
            {% for row in puantaj_rows %}
            <tr>
                <td>{{ row[0].tarih }}</td>
                <td>
                    {% if row[0].durum == 1.0 %}
                        <span class="badge bg-success">Tam Gün (1.0)</span>
                    {% elif row[0].durum == 0.5 %}
                        <span class="badge bg-warning text-dark">Yarım Gün (0.5)</span>
                    {% else %}
                        <span class="text-muted">Gelmedi / İzinli</span>
                    {% endif %}
                </td>
                {% if row[1] %}
                <td>{{ row[1].tarih }}</td>
                <td>
                    {% if row[1].durum == 1.0 %}
                        <span class="badge bg-success">Tam Gün (1.0)</span>
                    {% elif row[1].durum == 0.5 %}
                        <span class="badge bg-warning text-dark">Yarım Gün (0.5)</span>
                    {% else %}
                        <span class="text-muted">Gelmedi / İzinli</span>
                    {% endif %}
                </td>
                {% else %}
                <td>-</td>
                <td>-</td>
                {% endif %}
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <!-- Avans / Ödemeler -->
    <h6 class="fw-bold border-bottom pb-2">💸 Yapılan Avans ve Ödeme Kayıtları</h6>
    <table class="table table-sm table-striped mb-4">
        <thead>
            <tr>
                <th>Tarih</th>
                <th>Açıklama</th>
                <th class="text-end">Ödenen Tutar</th>
            </tr>
        </thead>
        <tbody>
            {% for a in avanslar %}
            <tr>
                <td>{{ a.tarih }}</td>
                <td>{{ a.aciklama or 'Avans / Ara Ödeme' }}</td>
                <td class="text-end fw-bold text-danger">{{ "{:,.2f}".format(a.tutar) }} TL</td>
            </tr>
            {% else %}
            <tr>
                <td colspan="3" class="text-center text-muted">Bu dönem içerisinde yapılmış bir ödeme bulunmamaktadır.</td>
            </tr>
            {% endfor %}
            <tr class="table-light fw-bold">
                <td colspan="2" class="text-end">Toplam Alınan Ödeme:</td>
                <td class="text-end text-danger">{{ "{:,.2f}".format(toplam_avans) }} TL</td>
            </tr>
        </tbody>
    </table>

    <!-- İmza Alanı -->
    <div class="row mt-5 pt-4 text-center">
        <div class="col-6">
            <p class="mb-5 fw-bold">Teslim Eden (Şantiye Yetkilisi)</p>
            <p>İmza: .......................................</p>
        </div>
        <div class="col-6">
            <p class="mb-5 fw-bold">Teslim Alan (Personel)</p>
            <p>İmza: .......................................</p>
        </div>
    </div>
</div>

</body>
</html>
'''

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
        cursor.execute('''
            SELECT tarih, durum FROM puantaj 
            WHERE personel_id = ? AND strftime('%Y-%m', tarih) = ?
        ''', (p['id'], secili_donem))
        puantaj_rows = cursor.fetchall()
        puantaj_dict = {row['tarih']: (row['durum'] if row['durum'] is not None else '') for row in puantaj_rows}
        
        p_gun = sum([float(val) for val in puantaj_dict.values() if val != ''])
        
        if p['ucret_tipi'] == 'Aylik':
            if p_gun >= ayin_gun_sayisi:
                hakedis = p['ucret']
            else:
                hakedis = (p['ucret'] / ayin_gun_sayisi) * p_gun
        else:
            hakedis = p['ucret'] * p_gun
            
        cursor.execute('''
            SELECT SUM(tutar) as toplam_avans FROM hareketler 
            WHERE personel_id = ? AND strftime('%Y-%m', tarih) = ? AND tip = 'Avans'
        ''', (p['id'], secili_donem))
        p_avans = cursor.fetchone()['toplam_avans'] or 0.0
        
        personeller.append({
            'id': p['id'],
            'ad_soyad': p['ad_soyad'],
            'gorev': p['gorev'],
            'ucret_tipi': p['ucret_tipi'],
            'ucret': p['ucret'],
            'puantaj_dict': puantaj_dict,
            'toplam_gun': p_gun,
            'hakedis': hakedis,
            'toplam_avans': p_avans,
            'kalan': hakedis - p_avans
        })
        
    cursor.execute('SELECT * FROM giderler WHERE strftime("%Y-%m", tarih) = ? ORDER BY tarih DESC', (secili_donem,))
    giderler = cursor.fetchall()
    toplam_gider = sum([g['tutar'] for g in giderler])
    
    conn.close()
    
    secili_ay_str = datetime(yil, ay, 1).strftime('%B %Y')
    bugun = datetime.now().strftime('%Y-%m-%d')
    
    return render_template_string(HTML_TEMPLATE, 
                                  personeller=personeller, 
                                  secili_donem=secili_donem, 
                                  secili_ay_str=secili_ay_str,
                                  bugun=bugun,
                                  yil=yil,
                                  ay=ay,
                                  ayin_gun_sayisi=ayin_gun_sayisi,
                                  giderler=giderler,
                                  toplam_gider=toplam_gider)

@app.route('/api/puantaj-guncelle', methods=['POST'])
def api_puantaj_guncelle():
    data = request.json
    personel_id = data.get('personel_id')
    tarih = data.get('tarih')
    durum = data.get('durum')
    
    conn = get_db()
    cursor = conn.cursor()
    
    if durum != '' and durum is not None:
        cursor.execute('''
            INSERT INTO puantaj (personel_id, tarih, durum)
            VALUES (?, ?, ?)
            ON CONFLICT(personel_id, tarih) DO UPDATE SET durum=excluded.durum
        ''', (personel_id, tarih, float(durum)))
    else:
        cursor.execute('DELETE FROM puantaj WHERE personel_id = ? AND tarih = ?', (personel_id, tarih))
        
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
        cursor.execute('SELECT durum FROM puantaj WHERE personel_id = ? AND tarih = ?', (personel_id, tarih_str))
        row = cursor.fetchone()
        durum = row['durum'] if row else 0.0
        toplam_gun += durum
        puantaj_list.append({'tarih': tarih_str, 'durum': durum})
        
    puantaj_rows = []
    for i in range(0, len(puantaj_list), 2):
        row_pair = (puantaj_list[i], puantaj_list[i+1] if i+1 < len(puantaj_list) else None)
        puantaj_rows.append(row_pair)
        
    if personel['ucret_tipi'] == 'Aylik':
        if toplam_gun >= ayin_gun_sayisi:
            hakedis = personel['ucret']
        else:
            hakedis = (personel['ucret'] / ayin_gun_sayisi) * toplam_gun
    else:
        hakedis = personel['ucret'] * toplam_gun
        
    cursor.execute('SELECT * FROM hareketler WHERE personel_id = ? AND strftime("%Y-%m", tarih) = ? ORDER BY tarih ASC', (personel_id, secili_donem))
    avanslar = cursor.fetchall()
    toplam_avans = sum([a['tutar'] for a in avanslar])
    
    conn.close()
    
    secili_ay_str = datetime(yil, ay, 1).strftime('%B %Y')
    
    return render_template_string(EKSTRE_TEMPLATE,
                                  personel=personel,
                                  secili_ay_str=secili_ay_str,
                                  puantaj_rows=puantaj_rows,
                                  toplam_gun=toplam_gun,
                                  hakedis=hakedis,
                                  avanslar=avanslar,
                                  toplam_avans=toplam_avans,
                                  kalan=hakedis - toplam_avans)

@app.route('/personel-ekle', methods=['POST'])
def personel_ekle():
    ad_soyad = request.form['ad_soyad']
    gorev = request.form.get('gorev', '')
    ucret_tipi = request.form.get('ucret_tipi', 'Gunluk')
    ucret = float(request.form.get('ucret', 0))
    donem = request.form.get('donem', datetime.now().strftime('%Y-%m'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO personeller (ad_soyad, gorev, ucret_tipi, ucret) VALUES (?, ?, ?, ?)',
                   (ad_soyad, gorev, ucret_tipi, ucret))
    conn.commit()
    conn.close()
    return redirect(url_for('ana_sayfa', donem=donem))

@app.route('/avans-ekle', methods=['POST'])
def avans_ekle():
    personel_id = request.form['personel_id']
    tarih = request.form['tarih']
    tutar = float(request.form['tutar'])
    aciklama = request.form.get('aciklama', '')
    donem = request.form.get('donem', datetime.now().strftime('%Y-%m'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO hareketler (personel_id, tarih, tip, tutar, aciklama) VALUES (?, ?, ?, ?, ?)',
                   (personel_id, tarih, 'Avans', tutar, aciklama))
    conn.commit()
    conn.close()
    return redirect(url_for('ana_sayfa', donem=donem))

@app.route('/gider-ekle', methods=['POST'])
def gider_ekle():
    kategori = request.form['kategori']
    tarih = request.form['tarih']
    tutar = float(request.form['tutar'])
    aciklama = request.form['aciklama']
    donem = request.form.get('donem', datetime.now().strftime('%Y-%m'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO giderler (tarih, kategori, tutar, aciklama) VALUES (?, ?, ?, ?)',
                   (tarih, kategori, tutar, aciklama))
    conn.commit()
    conn.close()
    return redirect(url_for('ana_sayfa', donem=donem))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
