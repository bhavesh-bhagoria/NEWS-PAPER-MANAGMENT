from flask import Flask, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from datetime import datetime
import calendar

app = Flask(__name__)
app.secret_key = "change_this_to_random_secret_key_12345"


# ---------------- BILL ENGINE ----------------


# ---------------- Home ----------------
@app.route("/")
def home():
    return render_template("home.html")


# ---------------- Admin Login ----------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM agent_credentials WHERE username=%s AND password=%s",
                       (username, password))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()

        if admin:
            session["admin_id"] = admin["agent_id"]
            session["admin_name"] = admin["username"]
            return redirect(url_for("admin_dashboard"))

        flash("Invalid credentials", "error")

    return render_template("admin_login.html")


def generate_monthly_bills():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    today = datetime.today()
    bill_month = today.strftime("%B %Y")
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    # Get all customers with rate
    cursor.execute("""
        SELECT cd.customer_id, ns.rate_per_day
        FROM customer_details cd
        JOIN newspaper_details ns ON cd.customer_id = ns.customer_id
    """)
    customers = cursor.fetchall()

    UNPAID_STATUS = 1  # from payment_status table

    for customer in customers:
        customer_id = customer["customer_id"]
        rate = customer["rate_per_day"]

        days_active = days_in_month
        amount = days_active * rate

        # Check if bill already exists
        cursor.execute("""
            SELECT bill_id FROM bills
            WHERE customer_id=%s AND bill_month=%s
        """, (customer_id, bill_month))

        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO bills
                (customer_id, bill_month, days_active, amount, amount_status)
                VALUES (%s, %s, %s, %s, %s)
            """, (customer_id, bill_month, days_active, amount, UNPAID_STATUS))

    conn.commit()
    cursor.close()
    conn.close()



# ---------------- Admin Dashboard ----------------
@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    generate_monthly_bills()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    current_month = datetime.now().strftime("%B %Y")

    cursor.execute("SELECT COUNT(*) AS total FROM customer_details WHERE agent_id=%s",
                   (session["admin_id"],))
    total_customers = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT SUM(b.amount) AS total
        FROM bills b
        JOIN customer_details c ON b.customer_id=c.customer_id
        WHERE c.agent_id=%s AND b.bill_month=%s
    """, (session["admin_id"], current_month))
    total_bill = cursor.fetchone()["total"] or 0

    cursor.close()
    conn.close()

    return render_template("admin_dashboard.html",
                           name=session["admin_name"],
                           total_customers=total_customers,
                           total_bill=total_bill,
                           current_month=current_month)


# ---------------- Add Customer ----------------
@app.route("/admin_add_customer", methods=["GET", "POST"])
def admin_add_customer():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO customer_details
            (agent_id, name, password, mobile_no, area_locality,
             landmark_building, flat_house_office_no, start_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["admin_id"],
            request.form["name"],
            request.form["password"],
            request.form["mobile"],
            request.form["area"],
            request.form.get("landmark_building", ""),
            request.form.get("flat_house_office_no", ""),
            request.form["start_date"],
        ))

        customer_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO newspaper_details
            (customer_id, newspaper_name, language, delivery_frequency, rate_per_day)
            VALUES (%s,%s,'English','Daily',%s)
        """, (customer_id, request.form["newspaper"], request.form["rate"]))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Customer added successfully", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_add_customer.html")



@app.route("/customer_login", methods=["GET", "POST"])
def customer_login():
    if request.method == "POST":
        mobile_no = request.form.get("mobile_no")
        password = request.form.get("password")

        if not mobile_no or not password:
            flash("Mobile number and password are required", "error")
            return render_template("customer_login.html")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT customer_id, name
            FROM customer_details
            WHERE mobile_no=%s AND password=%s
        """, (mobile_no, password))

        customer = cursor.fetchone()
        cursor.close()
        conn.close()

        if customer:
            session["customer_id"] = customer["customer_id"]
            session["customer_name"] = customer["name"]
            return redirect(url_for("customer_dashboard"))

        flash("Invalid mobile number or password", "error")

    return render_template("customer_login.html")





# ---------------- Customer Dashboard ----------------
@app.route("/customer_dashboard")
def customer_dashboard():
    if "customer_id" not in session:
        return render_template("customer_login.html")

    generate_monthly_bills()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    current_month = datetime.now().strftime("%B %Y")

    cursor.execute("""
        SELECT amount FROM bills
        WHERE customer_id=%s AND bill_month=%s
    """, (session["customer_id"], current_month))

    bill = cursor.fetchone()
    amount = bill["amount"] if bill else 0

    cursor.close()
    conn.close()

    return render_template("customer_dashboard.html",
                           current_bill=amount,
                           name=session["customer_name"])


# ---------------- View All Bills (Customer) ----------------
@app.route("/view_all_bills")
def view_all_bills():
    if "customer_id" not in session:
        return redirect(url_for("customer_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT bill_id, bill_month, amount, amount_status
        FROM bills
        WHERE customer_id=%s
        ORDER BY bill_id DESC
    """, (session["customer_id"],))

    bills = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("view_all_bills.html", bills=bills)


# ---------------- Admin Bills ----------------
@app.route("/admin/bills")
def admin_bills():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    generate_monthly_bills()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            b.bill_id,
            b.bill_month,
            b.amount,
            b.amount_status,
            c.name,
            c.mobile_no
        FROM bills b
        JOIN customer_details c 
            ON b.customer_id = c.customer_id
        WHERE c.agent_id = %s
        ORDER BY b.bill_id DESC
    """, (session["admin_id"],))

    bills = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_bills.html", bills=bills)



# ---------------- Toggle Paid/Unpaid ----------------
@app.route("/admin/toggle_bill/<int:bill_id>")
def toggle_bill(bill_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bills
        SET amount_status = CASE WHEN amount_status=0 THEN 1 ELSE 0 END
        WHERE bill_id=%s
    """, (bill_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("admin_bills"))

@app.route("/admin_pause_requests")
def admin_pause_requests():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT pd.pause_id, pd.subscription_id, pd.pause_start, pd.pause_end, pd.seen,
               pr.reason, c.name AS customer_name
        FROM pause_details pd
        LEFT JOIN pause_reason pr ON pd.pause_id = pr.pause_id
        JOIN newspaper_details ns ON pd.subscription_id = ns.subscription_id
        JOIN customer_details c ON ns.customer_id = c.customer_id
        WHERE c.agent_id = %s
        ORDER BY pd.pause_start DESC
    """, (session["admin_id"],))

    requests = cursor.fetchall()
    new_requests = sum(1 for r in requests if r['seen'] == 0)

    cursor.close()
    conn.close()

    return render_template(
        "admin_pause_requests.html",
        requests=requests,
        new_requests=new_requests
    )
# ---------------- Mark Bill as Paid ----------------
@app.route("/mark_paid/<int:bill_id>")
def mark_paid(bill_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bills
        SET payment_status = 'Paid'
        WHERE bill_id = %s
    """, (bill_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("admin_bills"))

@app.route("/mark_unpaid/<int:bill_id>")
def mark_unpaid(bill_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE bills
        SET payment_status = 'Unpaid'
        WHERE bill_id = %s
    """, (bill_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("admin_bills"))
@app.route("/mark_seen/<int:pause_id>")
def mark_seen(pause_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pause_requests
        SET seen = 1
        WHERE pause_id = %s
    """, (pause_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("admin_pause_requests"))



# ---------------- Logout ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
