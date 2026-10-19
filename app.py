from datetime import datetime
from flask import Flask, flash, redirect, render_template_string, request, url_for
import os
import sqlite3

app = Flask(__name__)
app.secret_key = "gizli_anahtar"

# Veritabanı Kurulumu


def init_db():
  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  # Personel Tablosu
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS personeller (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_soyad TEXT NOT NULL,
            yevmiye REAL NOT NULL
        )
    """)
  # Puantaj Tablosu (Kim, hangi tarih, hangi şantiyede, durum ne?)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS puantaj (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personel_id INTEGER,
            tarih TEXT,
            durum TEXT, -- Tam, Yarım, Gelmedi
            lokasyon TEXT
        )
    """)
  # Avans Tablosu
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS avanslar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personel_id INTEGER,
            tarih TEXT,
            tutar REAL
        )
    """)
  # Günlük Giderler Tablosu
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS giderler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            kategori TEXT, -- Gaz, Yemek, Malzeme vb.
            tutar REAL,
            aciklama TEXT
        )
    """)
  conn.commit()
  conn.close()


# Basit Arayüz Tasarımı (Tek dosya içinde şık bir görünüm)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Şantiye & Personel Takip</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1, h2 { color: #2c3e50; }
        nav { margin-bottom: 20px; background: #34495e; padding: 10px; border-radius: 5px; }
        nav a { color: white; text-decoration: none; margin-right: 15px; font-weight: bold; }
        nav a:hover { text-decoration: underline; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        form { margin-top: 15px; background: #fafafa; padding: 15px; border-radius: 5px; border: 1px solid #eee; }
        input, select { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; }
        button { background: #27ae60; color: white; border: none; padding: 10px 15px; cursor: pointer; border-radius: 4px; font-weight: bold; }
        button:hover { background: #219653; }
        .flash { background: #d4edda; color: #155724; padding: 10px; margin-bottom: 15px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏗️ Şantiye & Personel Takip Sistemi</h1>
        <nav>
            <a href="/">Ana Sayfa / Puantaj</a>
            <a href="/personeller">Personel Yönetimi</a>
            <a href="/avanslar">Avans İşlemleri</a>
            <a href="/giderler">Günlük Giderler</a>
            <a href="/maaslar">Ay Sonu Hesap</a>
        </nav>

        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="flash">{{ messages[0] }}</div>
          {% endif %}
        {% endwith %}

        {% if sayfa == 'anasayfa' %}
            <h2>Günlük Puantaj ve Saha Ataması</h2>
            <form method="POST" action="/puantaj-ekle">
                <label>Tarih:</label>
                <input type="date" name="tarih" value="{{ bugun }}" required>
                <label>Personel:</label>
                <select name="personel_id">
                    {% for p in personeller %}
                        <option value="{{ p[0] }}">{{ p[1] }} (Yevmiye: {{ p[2] }} TL)</option>
                    {% endfor %}
                </select>
                <label>Çalışma Durumu:</label>
                <select name="durum">
                    <option value="Tam Gün">Tam Gün (1)</option>
                    <option value="Yarım Gün">Yarım Gün (0.5)</option>
                    <option value="Gelmedi">Gelmedi (0)</option>
                </select>
                <label>Çalıştığı Yer / Şantiye:</label>
                <input type="text" name="lokasyon" placeholder="Örn: Villa Projesi / Merkez Daire" required>
                <button type="submit">Puantaj Kaydet</button>
            </form>

            <h3>Son Kayıtlı Puantajlar</h3>
            <table>
                <tr><th>Tarih</th><th>Personel</th><th>Durum</th><th>Lokasyon</th></tr>
                {% for row in puantajlar %}
                <tr><td>{{ row[1] }}</td><td>{{ row[2] }}</td><td>{{ row[3] }}</td><td>{{ row[4] }}</td></tr>
                {% endfor %}
            </table>

        {% elif sayfa == 'personeller' %}
            <h2>Personel Listesi</h2>
            <form method="POST" action="/personel-ekle">
                <label>Ad Soyad:</label>
                <input type="text" name="ad_soyad" required>
                <label>Günlük Yevmiye (TL):</label>
                <input type="number" step="0.01" name="yevmiye" required>
                <button type="submit">Personel Ekle</button>
            </form>
            <table>
                <tr><th>ID</th><th>Ad Soyad</th><th>Günlük Yevmiye</th></tr>
                {% for p in personeller %}
                <tr><td>{{ p[0] }}</td><td>{{ p[1] }}</td><td>{{ p[2] }} TL</td></tr>
                {% endfor %}
            </table>

        {% elif sayfa == 'avanslar' %}
            <h2>Avans İşlemleri</h2>
            <form method="POST" action="/avans-ekle">
                <label>Personel:</label>
                <select name="personel_id">
                    {% for p in personeller %}
                        <option value="{{ p[0] }}">{{ p[1] }}</option>
                    {% endfor %}
                </select>
                <label>Tarih:</label>
                <input type="date" name="tarih" value="{{ bugun }}" required>
                <label>Tutar (TL):</label>
                <input type="number" step="0.01" name="tutar" required>
                <button type="submit">Avans Ver</button>
            </form>
            <h3>Verilen Avanslar</h3>
            <table>
                <tr><th>Tarih</th><th>Personel</th><th>Tutar</th></tr>
                {% for a in avanslar %}
                <tr><td>{{ a[1] }}</td><td>{{ a[2] }}</td><td>{{ a[3] }} TL</td></tr>
                {% endfor %}
            </table>

        {% elif sayfa == 'giderler' %}
            <h2>Günlük Saha Giderleri (Gaz, Yemek, Malzeme)</h2>
            <form method="POST" action="/gider-ekle">
                <label>Tarih:</label>
                <input type="date" name="tarih" value="{{ bugun }}" required>
                <label>Kategori:</label>
                <select name="kategori">
                    <option value="Gaz / Yakıt">Gaz / Yakıt</option>
                    <option value="Yemek">Yemek</option>
                    <option value="Malzeme">Malzeme</option>
                    <option value="Diğer">Diğer</option>
                </select>
                <label>Tutar (TL):</label>
                <input type="number" step="0.01" name="tutar" required>
                <label>Açıklama:</label>
                <input type="text" name="aciklama" placeholder="Örn: İnşaat demiri alındı">
                <button type="submit">Gider Kaydet</button>
            </form>
            <h3>Gider Listesi</h3>
            <table>
                <tr><th>Tarih</th><th>Kategori</th><th>Tutar</th><th>Açıklama</th></tr>
                {% for g in giderler %}
                <tr><td>{{ g[1] }}</td><td>{{ g[2] }}</td><td>{{ g[3] }} TL</td><td>{{ g[4] }}</td></tr>
                {% endfor %}
            </table>

        {% elif sayfa == 'maaslar' %}
            <h2>Ay Sonu Özet ve Hakediş Hesabı</h2>
            <table>
                <tr>
                    <th>Personel Adı</th>
                    <th>Toplam Çalışma (Gün)</th>
                    <th>Toplam Hakediş</th>
                    <th>Toplam Alınan Avans</th>
                    <th>Ödenecek Net Tutar</th>
                </tr>
                {% for m in maas_ozet %}
                <tr>
                    <td>{{ m[0] }}</td>
                    <td>{{ m[1] }} gün</td>
                    <td>{{ m[2] }} TL</td>
                    <td>{{ m[3] }} TL</td>
                    <td><b>{{ m[4] }} TL</b></td>
                </tr>
                {% endfor %}
            </table>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route("/")
def anasayfa():
  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute("SELECT id, ad_soyad, yevmiye FROM personeller")
  personeller = cursor.fetchall()

  cursor.execute("""
        SELECT p.id, pu.tarih, p.ad_soyad, pu.durum, pu.lokasyon 
        FROM puantaj pu 
        JOIN personeller p ON pu.personel_id = p.id 
        ORDER BY pu.tarih DESC LIMIT 10
    """)
  puantajlar = cursor.fetchall()
  conn.close()

  return render_template_string(
      HTML_TEMPLATE,
      sayfa="anasayfa",
      personeller=personeller,
      puantajlar=puantajlar,
      bugun=datetime.now().strftime("%Y-%m-%d"),
  )


@app.route("/puantaj-ekle", methods=["POST"])
def puantaj_ekle():
  personel_id = request.form["personel_id"]
  tarih = request.form["tarih"]
  durum = request.form["durum"]
  lokasyon = request.form["lokasyon"]

  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO puantaj (personel_id, tarih, durum, lokasyon) VALUES"
      " (?, ?, ?, ?)",
      (personel_id, tarih, durum, lokasyon),
  )
  conn.commit()
  conn.close()
  flash("Puantaj başarıyla kaydedildi!")
  return redirect(url_for("anasayfa"))


@app.route("/personeller", methods=["GET", "POST"])
def personeller_sayfa():
  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute("SELECT id, ad_soyad, yevmiye FROM personeller")
  personeller = cursor.fetchall()
  conn.close()
  return render_template_string(
      HTML_TEMPLATE, sayfa="personeller", personeller=personeller
  )


@app.route("/personel-ekle", methods=["POST"])
def personel_ekle():
  ad_soyad = request.form["ad_soyad"]
  yevmiye = request.form["yevmiye"]
  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO personeller (ad_soyad, yevmiye) VALUES (?, ?)",
      (ad_soyad, yevmiye),
  )
  conn.commit()
  conn.close()
  flash("Personel eklendi!")
  return redirect(url_for("personeller_sayfa"))


@app.route("/avanslar", methods=["GET"])
def avanslar_sayfa():
  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute("SELECT id, ad_soyad, yevmiye FROM personeller")
  personeller = cursor.fetchall()

  cursor.execute("""
        SELECT a.id, a.tarih, p.ad_soyad, a.tutar 
        FROM avanslar a 
        JOIN personeller p ON a.personel_id = p.id 
        ORDER BY a.tarih DESC
    """)
  avanslar = cursor.fetchall()
  conn.close()
  return render_template_string(
      HTML_TEMPLATE,
      sayfa="avanslar",
      personeller=personeller,
      avanslar=avanslar,
      bugun=datetime.now().strftime("%Y-%m-%d"),
  )


@app.route("/avans-ekle", methods=["POST"])
def avans_ekle():
  personel_id = request.form["personel_id"]
  tarih = request.form["tarih"]
  tutar = request.form["tutar"]

  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO avanslar (personel_id, tarih, tutar) VALUES (?, ?, ?)",
      (personel_id, tarih, tutar),
  )
  conn.commit()
  conn.close()
  flash("Avans kaydedildi!")
  return redirect(url_for("avanslar_sayfa"))


@app.route("/giderler", methods=["GET"])
def giderler_sayfa():
  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, tarih, kategori, tutar, aciklama FROM giderler ORDER BY tarih"
      " DESC"
  )
  giderler = cursor.fetchall()
  conn.close()
  return render_template_string(
      HTML_TEMPLATE,
      sayfa="giderler",
      giderler=giderler,
      bugun=datetime.now().strftime("%Y-%m-%d"),
  )


@app.route("/gider-ekle", methods=["POST"])
def gider_ekle():
  tarih = request.form["tarih"]
  kategori = request.form["kategori"]
  tutar = request.form["tutar"]
  aciklama = request.form["aciklama"]

  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO giderler (tarih, kategori, tutar, aciklama) VALUES (?, ?,"
      " ?, ?)",
      (tarih, kategori, tutar, aciklama),
  )
  conn.commit()
  conn.close()
  flash("Gider kaydedildi!")
  return redirect(url_for("giderler_sayfa"))


@app.route("/maaslar")
def maaslar_sayfa():
  conn = sqlite3.connect("santiye.db")
  cursor = conn.cursor()
  cursor.execute("SELECT id, ad_soyad, yevmiye FROM personeller")
  personeller = cursor.fetchall()

  maas_ozet = []
  for p in personeller:
    p_id, ad, yevmiye = p
    cursor.execute(
        "SELECT durum FROM puantaj WHERE personel_id = ?", (p_id,)
    )
    puantajlar = cursor.fetchall()
    toplam_gun = 0
    for pr in puantajlar:
      if pr[0] == "Tam Gün":
        toplam_gun += 1.0
      elif pr[0] == "Yarım Gün":
        toplam_gun += 0.5

    hakedis = toplam_gun * yevmiye

    cursor.execute(
        "SELECT SUM(tutar) FROM avanslar WHERE personel_id = ?", (p_id,)
    )
    toplam_avans = cursor.fetchone()[0] or 0.0

    net_odencek = hakedis - toplam_avans
    maas_ozet.append(
        (ad, toplam_gun, hakedis, toplam_avans, net_odencek)
    )

  conn.close()
  return render_template_string(
      HTML_TEMPLATE, sayfa="maaslar", maas_ozet=maas_ozet
  )


if __name__ == "__main__":
  init_db()
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)