# app.py
from flask import Flask, render_template_string, request, redirect, url_for, flash
import os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# — SMTP CONFIG in your .env —
SMTP_SERVER      = os.getenv("SMTP_SERVER",   "smtp.gmail.com")
SMTP_PORT        = int(os.getenv("SMTP_PORT", 587))
SMTP_USER        = os.getenv("SMTP_USER")
SMTP_PASS        = os.getenv("SMTP_PASS")
REPORT_RECIPIENT = os.getenv("REPORT_RECIPIENT")

# — Define items, units, and low-stock thresholds —
SECTIONS = {
    "Kitchen": [
        ("Chicken",        "pcs",    4),
        ("Pork",           "kg",     2),
        ("Fish",           "kg",     1),
        ("Goat",           "serv",   2),
        ("Sausages",       "pcs",    4),
        ("Eggs",           "pcs",   10),
        ("Flour",          "packs",  2),
        ("Milk",           "ltr",    1),
        ("Fish Fingers",   "pcs",   10),
        ("Pizza",          "serv",   4),
        ("Rolex",          "serv",   4)
    ],
    "Bar": [
        ("Water",            "pcs", 10),
        ("Soda",             "pcs", 20),
        ("Energy Drinks",    "pcs",  2),
        ("Bond 7",           "pcs",  2),
        ("Black & White",    "pcs",  2),
        ("Uganda Waragi",    "pcs",  2),
        ("Four Cousins",     "pcs",  1),
        ("Captain Morgan",   "pcs",  2),
        ("Bowmone",          "pcs",  1),
        ("Smirnoff Vodka",   "pcs",  1),
        ("Baileys",          "pcs",  1),
        ("Black Label",      "pcs",  1),
        ("Singleton",        "pcs",  1),
        ("Gilbey's",         "pcs",  1),
        ("Tanqueray",        "pcs",  1),
        ("Tequila",          "pcs",  1),
        # group-of-10s
        ("Black Ice",        "pcs", 10),
        ("Red Ice",          "pcs", 10),
        ("Smirnoff Guarana", "pcs", 10),
        ("Guinness Stout",   "pcs", 10),
        ("Guinness Smooth",  "pcs", 10),
        ("Tusker Cider",     "pcs", 10),
        ("Tusker Malt",      "pcs", 10),
        ("Tusker Lite",      "pcs", 10),
        ("Castlelo",         "pcs", 10),
        ("Best",             "pcs", 10),
        ("Club",             "pcs", 10),
        ("Nile",             "pcs", 10)
    ]
}

# — HTML with units & richer colors —
FORM_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>St. Padre Pio Leisure Centre Stock Report</title>
  <style>
    body { background: #eef2f7; font-family: 'Segoe UI', sans-serif; }
    .container {
      max-width: 650px; margin: 50px auto; background: #fff;
      padding: 2rem; border-radius: 10px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    h1 { color: #b71c1c; margin-bottom: 0.5rem; }
    h2 { color: #1f3a93; margin-top: 2rem; border-bottom:2px solid #1f3a93; padding-bottom:0.2rem; }
    label { display:block; margin-top:1rem; font-weight:600; color:#333; }
    .unit { font-size:0.9rem; color:#666; margin-left:0.4rem; }
    input { width:100%; padding:0.6rem; margin-top:0.3rem;
            border:1px solid #ccc; border-radius:5px;
            transition: border-color .2s; }
    input:focus { border-color:#1f3a93; outline:none; }
    button {
      margin-top:2.5rem; padding:0.8rem;
      width:100%; background:#b71c1c; color:#fff;
      border:none; border-radius:5px; font-size:1rem;
      cursor:pointer; transition:background .2s;
    }
    button:hover { background:#8e0000; }
    .flash { padding:1rem; border-radius:6px; margin-bottom:1rem; }
    .success { background:#e8f5e9; color:#2e7d32; }
    .error   { background:#ffebee; color:#c62828; }
    .timestamp { text-align:right; margin-top:1.5rem; color:#555; font-size:0.9rem; }
  </style>
</head>
<body>
  <div class="container">
    <h1>St. Padre Pio Leisure Centre</h1>
    <h2>End-of-Shift Stock Report</h2>

    {% with msgs = get_flashed_messages(with_categories=true) %}
      {% for cat, msg in msgs %}
        <div class="flash {{cat}}">{{ msg }}</div>
      {% endfor %}
    {% endwith %}

    <form method="POST">
      <label>Employee Name</label>
      <input type="text" name="employee" required>

      {% for section, items in sections.items() %}
        <h2>{{ section }} Inventory</h2>
        {% for item, unit, _ in items %}
          <label>{{ item }}
            <span class="unit">({{ unit }})</span>
          </label>
          <input
            type="number"
            name="{{ item|replace(' ','_')|lower }}"
            min="0" required
          >
        {% endfor %}
      {% endfor %}

      <button type="submit">Send Report &amp; Alert</button>
    </form>
    <div class="timestamp">Generated: {{ now }}</div>
  </div>
</body>
</html>
"""

def send_email(subject, body, recipient):
    msg = MIMEMultipart()
    msg["From"]    = SMTP_USER
    msg["To"]      = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

@app.route("/", methods=["GET","POST"])
def submit():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    if request.method == "POST":
        try:
            employee = request.form["employee"]
            lines    = [
                f"Stock Report — {employee}",
                f"Timestamp: {now_str}",
                ""
            ]

            # collect and check thresholds
            low_items = []
            for section, items in SECTIONS.items():
                lines.append(f"--- {section} ---")
                for item, unit, threshold in items:
                    key = item.replace(" ","_").lower()
                    qty = int(request.form.get(key, 0))
                    lines.append(f"{item} ({unit}): {qty}")
                    if qty < threshold:
                        low_items.append(f"{item}: {qty} < {threshold}{unit}")
                lines.append("")

            report_body = "\n".join(lines)

            # 1) Always send full report
            send_email(
                subject=f"Stock Report — {employee} @ {now_str}",
                body=report_body,
                recipient=REPORT_RECIPIENT
            )

            # 2) If any low, send alert
            if low_items:
                alert_body = (
                    f"⚠️ Low Stock Alert — {employee} @ {now_str}\n\n"
                    + "\n".join(low_items)
                )
                send_email(
                    subject=f"[ALERT] Low Stock — {now_str}",
                    body=alert_body,
                    recipient=REPORT_RECIPIENT
                )

            flash("Report sent (and alerts if any)!", "success")
        except Exception as e:
            flash(f"Error: {e}", "error")

        return redirect(url_for("submit"))

    return render_template_string(
        FORM_HTML,
        sections=SECTIONS,
        now=now_str
    )

if __name__ == "__main__":
    app.run(debug=True)
