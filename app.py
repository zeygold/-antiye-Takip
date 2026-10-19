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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Şantiye & Personel Takip</title>
    
    <!-- PWA / Mobil Uygulama Meta Etiketleri -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#212529">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Şantiye Takip">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/1048/1048953.png">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f6f9; font-size: 13px; -webkit-tap-highlight-color: transparent; }
        .card { margin-bottom: 12px; border-radius: 10px; border: none; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .puantaj-box { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .puantaj-input { width: 38px; height: 32px; text-align: center; padding: 2px; font-size: 13px; font-weight: bold; border-radius: 5px; }
        .has-note { background-color: #fff3cd !important; border-color: #ffe69c !important; }
        
        /* Mobil Ekran Uyumlu Tablo Kaydırma */
        .table-responsive { 
            overflow-x: auto; 
            -webkit-overflow-scrolling: touch; 
            border-radius: 6px;
        }
        
        .table th, .table td { padding: 5px 3px; vertical-align: middle; }
        
        /* Bildirim Toast */
        #toast-msg {
            position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); z-index: 9999;
            display: none; padding: 8px 18px; background-color: #198754; color: white;
            border-radius: 20px; font-weight: bold; font-size: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }

        @media (max-width: 768px) {
            .container-fluid { padding-left: 8px !important; padding-right: 8px !important; }
            .card { padding: 10px !important; }
            .btn { padding: 6px 10px; font-size: 12px; }
        }
    </style>
</head>
<body>
<div id="toast-msg">Otomatik Kaydedildi ✔</div>

<nav class="navbar navbar-dark bg-dark mb-2 py-2">
    <div class="container-fluid px-2">
        <a class="navbar-brand fw-bold fs-6" href="/">🏗️ Şantiye & Personel Takip</a>
        <span class="navbar-text text-white small" style="font-size: 11px;">{{ secili_ay_str }}</span>
    </div>
</nav>

<div class="container-fluid">
    <!-- Dönem Seçimi -->
    <div class="card p-2 bg-white">
        <form method="GET" class="row g-2 align-items-center m-0">
            <div class="col-auto p-0 me-2"><label class="fw-bold small">Dönem:</label></div>
            <div class="col p-0">
                <input type="month" name="donem" value="{{ secili_donem }}" class="form-control form-control-sm" onchange="this.form.submit()">
            </div>
        </form>
    </div>

    <!-- Personel Ekleme -->
    <div class="card p-3">
        <h6 class="fw-bold border-bottom pb-2 mb-2">➕ Yeni Personel / İşçi Ekle</h6>
        <form action="/personel-ekle" method="POST" class="row g-2">
            <input type="hidden" name="donem" value="{{ secili_donem }}">
            <div class="col-12 col-md-3">
                <input type="text" name="ad_soyad" class="form-control form-control-sm" placeholder="Ad Soyad" required>
            </div>
            <div class="col-12 col-md-3">
                <input type="text" name="gorev" class="form-control form-control-sm" placeholder="Görev (Örn: Kalıpçı)">
            </div>
            <div class="col-6 col-md-2">
                <select name="ucret_tipi" class="form-select form-select-sm">
                    <option value="Gunluk">Günlük Yevmiye</option>
                    <option value="Aylik">Aylık Maaş</option>
                </select>
            </div>
            <div class="col-6 col-md-2">
                <input type="number" step="0.01" name="ucret" class="form-control form-control-sm" placeholder="Tutar (TL)" required>
            </div>
            <div class="col-12 col-md-2">
                <button type="submit" class="btn btn-primary btn-sm w-100 fw-bold">Kaydet</button>
            </div>
        </form>
    </div>

    <!-- Puantaj & Hakediş Tablosu -->
    <div class="card p-2">
        <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
            <h6 class="fw-bold m-0 fs-6">📅 Aylık Puantaj Tablosu</h6>
            <small class="text-muted d-none d-md-inline" style="font-size: 11px;">Kutucuğa yazın, otomatik kaydolur.</small>
        </div>
        <div class="table-responsive">
            <table class="table table-bordered table-hover align-middle text-center mb-1">
                <thead class="table-dark small">
                    <tr>
                        <th style="min-width: 120px;" class="text-start">Ad Soyad</th>
                        <th style="min-width: 55px;">Tip</th>
                        <th style="min-width: 60px;">Ücret</th>
                        {% for gun in range(1, ayin_gun_sayisi + 1) %}
                            <th style="min-width: 40px;">{{ gun }}</th>
                        {% endfor %}
                        <th style="min-width: 65px;">Gün</th>
                        <th style="min-width: 80px;">Hakediş</th>
                        <th style="min-width: 80px;">Avans</th>
                        <th style="min-width: 80px;">Kalan</th>
                        <th style="min-width: 65px;">Rapor</th>
                    </tr>
                </thead>
                <tbody class="small">
                    {% for p in personeller %}
                    <tr>
                        <td class="text-start fw-bold" style="line-height: 1.2;">
                            {{ p.ad_soyad }} <br><small class="text-muted fw-normal" style="font-size:10px;">{{ p.gorev }}</small>
                        </td>
                        <td>
                            {% if p.ucret_tipi == 'Aylik' %}
                                <span class="badge bg-info text-dark p-1" style="font-size:9px;">Aylık</span>
                            {% else %}
                                <span class="badge bg-secondary p-1" style="font-size:9px;">Günlük</span>
                            {% endif %}
                        </td>
                        <td>{{ "{:,.0f}".format(p.ucret) }}</td>
                        {% for gun in range(1, ayin_gun_sayisi + 1) %}
                            {% set tarih_str = "{}-{:02d}-{:02d}".format(yil, ay, gun) %}
                            {% set p_info = p.puantaj_dict.get(tarih_str, {}) %}
                            {% set val = p_info.get('durum', '') %}
                            {% set not_val = p_info.get('not_aciklama', '') %}
                            <td>
                                <div class="puantaj-box">
                                    <input type="number" step="0.5" min="0" max="1" 
                                           value="{{ val if val is not none else '' }}" 
                                           class="form-control form-control-sm puantaj-input {% if not_val %}has-note{% endif %}"
                                           id="p_input_{{ p.id }}_{{ tarih_str }}"
                                           onchange="otomatikKaydet({{ p.id }}, '{{ tarih_str }}')">
                                    <button type="button" class="btn btn-link p-0 border-0 text-decoration-none mt-1" style="font-size: 9px; line-height:1;"
                                            onclick="modalNotAc({{ p.id }}, '{{ tarih_str }}', '{{ not_val }}')">
                                       {% if not_val %}📍Not{% else %}+Not{% endif %}
                                    </button>
                                </div>
                            </td>
                        {% endfor %}
                        <td class="fw-bold">{{ p.toplam_gun }}g</td>
                        <td class="text-success fw-bold">{{ "{:,.0f}".format(p.hakedis) }}₺</td>
                        <td class="text-danger fw-bold">{{ "{:,.0f}".format(p.toplam_avans) }}₺</td>
                        <td class="fw-bold text-primary">{{ "{:,.0f}".format(p.kalan) }}₺</td>
                        <td>
                            <a href="/personel-ekstre/{{ p.id }}?donem={{ secili_donem }}" target="_blank" class="btn btn-outline-dark btn-sm py-0 px-1 fw-bold" style="font-size:10px;">📄Ekstre</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="{{ ayin_gun_sayisi + 8 }}" class="text-center text-muted py-3">Henüz personel yok. Yukarıdan ekleyebilirsiniz.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Mobilde Alt Alta Sıralanan Avans & Gider Girişi -->
    <div class="row">
        <!-- Avans Girişi -->
        <div class="col-12 col-md-6">
            <div class="card p-3">
                <h6 class="fw-bold border-bottom pb-2 mb-2">💸 Avans / Ödeme Girişi</h6>
                <form action="/avans-ekle" method="POST" class="row g-2">
                    <input type="hidden" name="donem" value="{{ secili_donem }}">
                    <div class="col-12 col-md-6">
                        <select name="personel_id" class="form-select form-select-sm" required>
                            <option value="">Personel Seçin...</option>
                            {% for p in personeller %}
                            <option value="{{ p.id }}">{{ p.ad_soyad }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="col-12 col-md-6">
                        <input type="date" name="tarih" class="form-control form-control-sm" value="{{ bugun }}" required>
                    </div>
                    <div class="col-12 col-md-6">
                        <input type="number" step="0.01" name="tutar" class="form-control form-control-sm" placeholder="Tutar (TL)" required>
                    </div>
                    <div class="col-12 col-md-6">
                        <input type="text" name="aciklama" class="form-control form-control-sm" placeholder="Açıklama (Örn: Banka havalesi)">
                    </div>
                    <div class="col-12">
                        <button type="submit" class="btn btn-danger btn-sm w-100 fw-bold">Avans / Ödeme Kaydet</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Şantiye Günlük Gider Girişi (Mobilde Altına Gelir) -->
        <div class="col-12 col-md-6">
            <div class="card p-3">
                <h6 class="fw-bold border-bottom pb-2 mb-2">🏗️ Şantiye Günlük Gider Girişi</h6>
                <form action="/gider-ekle" method="POST" class="row g-2">
                    <input type="hidden" name="donem" value="{{ secili_donem }}">
                    <div class="col-12 col-md-6">
                        <select name="kategori" class="form-select form-select-sm" required>
                            <option value="Malzeme / Nalbur">Malzeme / Nalbur</option>
                            <option value="Akaryakıt">Akaryakıt</option>
                            <option value="Yemek / Mutfak">Yemek / Mutfak</option>
                            <option value="Nakliye / Lojistik">Nakliye / Lojistik</option>
                            <option value="Alet / Kiralama">Alet / Kiralama</option>
                            <option value="Diğer Harcamalar">Diğer Harcamalar</option>
                        </select>
                    </div>
                    <div class="col-12 col-md-6">
                        <input type="date" name="tarih" class="form-control form-control-sm" value="{{ bugun }}" required>
                    </div>
                    <div class="col-12 col-md-6">
                        <input type="number" step="0.01" name="tutar" class="form-control form-control-sm" placeholder="Gider Tutarı (TL)" required>
                    </div>
                    <div class="col-12 col-md-6">
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
    <div class="card p-3 mb-4">
        <div class="d-flex justify-content-between align-items-center border-bottom pb-2 mb-2">
            <h6 class="fw-bold m-0 fs-6">🛒 Bu Ayki Şantiye Giderleri Listesi</h6>
            <span class="badge bg-danger fs-6">{{ "{:,.2f}".format(toplam_gider) }} TL</span>
        </div>
        <div class="table-responsive">
            <table class="table table-sm table-striped align-middle mb-0 small">
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
                        <td><span class="badge bg-secondary" style="font-size:10px;">{{ g.kategori }}</span></td>
                        <td>{{ g.aciklama }}</td>
                        <td class="text-end fw-bold text-danger">{{ "{:,.2f}".format(g.tutar) }} TL</td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" class="text-center text-muted py-2">Bu ay kayıtlı şantiye gideri yok.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- Şantiye Notu Modal Penceresi -->
<div class="modal fade" id="notModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h6 class="modal-title fw-bold">📍 Şantiye / Görev Yeri Notu</h6>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Kapat"></button>
      </div>
      <div class="modal-body">
        <input type="hidden" id="modal_p_id">
        <input type="hidden" id="modal_tarih">
        <div class="mb-3">
            <label class="form-label small text-muted">Gittiği Şantiye / Servis Noktaları:</label>
            <input type="text" id="modal_not_text" class="form-control" placeholder="Örn: Mor Salkım Villası, Erben İnşaat">
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">İptal</button>
        <button type="button" class="btn btn-primary btn-sm fw-bold" onclick="modalNotKaydet()">Kaydet</button>
      </div>
    </div>
