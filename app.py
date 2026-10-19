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
                            <td>
                                <a href="/personel-ekstre/{{ p.id }}?donem={{ secili_donem }}" target="_blank" class="btn btn-outline-dark btn-sm">📄 Ekstre</a>
                            </td>
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
                        <input type="text" name="aciklama" class="form-control form-control-sm" placeholder="Açıklama (Örn: Banka)">
                    </div>
                    <div class="col-12">
                        <button type="submit" class="btn btn-danger btn-sm w-100">Avans Ödemesi Kaydet</button>
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
                        <td
