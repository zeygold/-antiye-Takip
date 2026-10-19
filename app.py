from flask import Flask, render_template_string, request, redirect, url_for
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
        .puantaj-input { width: 45px; text-align: center; padding: 2px; font-size: 12px; }
        .table-responsive { overflow-x: auto; }
    </style>
</head>
<body>
<nav class="navbar navbar-dark bg-dark mb-3">
    <div class="container-fluid">
        <a class="navbar-brand fw-bold" href="/">🏗️ Şantiye & Personel Takip</a>
        <span class="navbar-text text-white small">{{ secili_ay_str }}</span>
    </div>
</nav>

<div class="container-fluid px-4">
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
                <button type="submit" class="btn btn-primary btn-sm w-100">Kaydet</button>
            </div>
        </form>
    </div>

    <!-- Puantaj & Hakediş Tablosu -->
    <div class="card p-3">
        <h6 class="fw-bold border-bottom pb-2">📅 Aylık Puantaj ve Hakediş Tablosu</h6>
        <form action="/puantaj-kaydet" method="POST">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="table-responsive">
                <table class="table table-bordered table-hover align-middle text-center">
                    <thead class="table-dark">
                        <tr>
                            <th style="min-width: 150px;">Ad Soyad</th>
                            <th>Ücret Tipi</th>
                            <th>Birim Ücret</th>
                            {% for gun in range(1, ayin_gun_sayisi + 1) %}
                                <th style="min-width: 45px;">{{ gun }}</th>
                            {% endfor %}
                            <th>Çalışılan</th>
                            <th>Hakediş</th>
                            <th>Avans</th>
                            <th>Kalan</th>
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
                            <td>{{ "{:,.0f}".format(p.ucret) }} TL</td>
                            {% for gun in range(1, ayin_gun_sayisi + 1) %}
                                {% set tarih_str = "{}-{:02d}-{:02d}".format(yil, ay, gun) %}
                                <td>
                                    <input type="number" step="0.5" min="0" max="1" 
                                           name="puantaj_{{ p.id }}_{{ tarih_str }}" 
                                           value="{{ p.puantaj_dict.get(tarih_str, '') }}" 
                                           class="form-control form-control-sm puantaj-input">
                                </td>
                            {% endfor %}
                            <td class="fw-bold">{{ p.toplam_gun }} gün</td>
                            <td class="text-success fw-bold">{{ "{:,.2f}".format(p.hakedis) }} TL</td>
                            <td class="text-danger">{{ "{:,.2f}".format(p.toplam_avans) }} TL</td>
                            <td class="fw-bold text-primary">{{ "{:,.2f}".format(p.kalan) }} TL</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="text-end mt-2">
                <button type="submit" class="btn btn-success btn-sm px-4 fw-bold">💾 Puantaj Değişikliklerini Kaydet</button>
            </div>
        </form>
    </div>

    <!-- Avans / Ödeme Girişi -->
    <div class="card p-3">
        <h6 class="fw-bold border-bottom pb-2">💸 Avans / Ödeme Girişi</h6>
        <form action="/avans-ekle" method="POST" class="row g-2">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-md-3">
                <select name="personel_id" class="form-select form-select-sm" required>
                    <option value="">Personel Seçin...</option>
                    {% for p in personeller %}
                    <option value="{{ p.id }}">{{ p.ad_soyad }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-2">
                <input type="date" name="tarih" class="form-control form-control-sm" value="{{ bugun }}" required>
            </div>
            <div class="col-md-2">
                <input type="number" step="0.01" name="tutar" class="form-control form-control-sm" placeholder="Tutar (TL)" required>
            </div>
            <div class="col-md-3">
                <input type="text" name="aciklama" class="form-control form-control-sm" placeholder="Açıklama (Örn: Banka havalesi)">
            </div>
            <div class="col-md-2">
                <button type="submit" class="btn btn-danger btn-sm w-100">Ödeme Ekle</button>
            </div>
        </form>
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
        # Puantaj detayları
        cursor.execute('''
            SELECT tarih, durum FROM puantaj 
            WHERE personel_id = ? AND strftime('%Y-%m', tarih) = ?
        ''', (p['id'], secili_donem))
        puantaj_rows = cursor.fetchall()
        puantaj_dict = {row['tarih']: (row['durum'] if row['durum'] is not None else '') for row in puantaj_rows}
        
        p_gun = sum([float(val) for val in puantaj_dict.values() if val != ''])
        
        # Hakediş Hesabı
        if p['ucret_tipi'] == 'Aylik':
            if p_gun >= ayin_gun_sayisi:
                hakedis = p['ucret']
            else:
                hakedis = (p['ucret'] / ayin_gun_sayisi) * p_gun
        else:
            hakedis = p['ucret'] * p_gun
            
        # Avans verisi
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
                                  ayin_gun_sayisi=ayin_gun_sayisi)

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

@app.route('/puantaj-kaydet', methods=['POST'])
def puantaj_kaydet():
    donem = request.form.get('donem', datetime.now().strftime('%Y-%m'))
    conn = get_db()
    cursor = conn.cursor()
    
    for key, val in request.form.items():
        if key.startswith('puantaj_'):
            parts = key.split('_')
            personel_id = parts[1]
            tarih = parts[2]
            
            if val != '':
                durum = float(val)
                cursor.execute('''
                    INSERT INTO puantaj (personel_id, tarih, durum)
                    VALUES (?, ?, ?)
                    ON CONFLICT(personel_id, tarih) DO UPDATE SET durum=excluded.durum
                ''', (personel_id, tarih, durum))
            else:
                cursor.execute('DELETE FROM puantaj WHERE personel_id = ? AND tarih = ?', (personel_id, tarih))
                
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

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
