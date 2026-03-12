from flask import Flask, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from datetime import datetime, date
import pandas as pd
from datetime import datetime, timedelta
import calendar
import re
app = Flask(__name__)
app.secret_key = "qwerty"


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/admin_register", methods=["GET", "POST"])
def admin_register():

    errors = []

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        mobile_no = request.form.get("mobile_no", "").strip()
        password = request.form.get("password", "").strip()

        if not username:
            errors.append("Username is required")
        elif not re.match(r"^(?!([A-Za-z])\1+$)(?!([A-Za-z]{2})\2+$)[A-Za-z ]{3,50}$", username):
            errors.append("Enter a valid name (no repeated character patterns)")
        if not mobile_no:
            errors.append("Mobile number is required")
        elif not re.match(r"^(?!([6-9])\1{9}$)[6-9]\d{9}$", mobile_no):
            errors.append("Enter a valid Indian mobile number")

        if not password:
            errors.append("Password is required")
        elif not re.match(r"^(?=.*[!@#$%^&*(),.?\":{}|<>]).{4,}$", password):
            errors.append("Password must be at least 4 characters and include one special symbol")

        conn = get_db_connection()
        cursor = conn.cursor()

        if not errors:
            
            cursor.execute(
                "SELECT 1 FROM agent_credentials WHERE mobile_no = %s",
                (mobile_no,)
            )
            if cursor.fetchone():
                errors.append("Mobile number already registered")

            cursor.execute(
                "SELECT 1 FROM agent_credentials WHERE username = %s",
                (username,)
            )
            if cursor.fetchone():
                errors.append("Username already taken")

        if errors:
            conn.close()
            return render_template(
                "agent_register.html",
                errors=errors,
                username=username,
                mobile_no=mobile_no
            )
        cursor.execute("""
            INSERT INTO agent_credentials (username, mobile_no, password)
            VALUES (%s, %s, %s)
        """, (username, mobile_no, password))

        conn.commit()
        conn.close()

        return redirect(url_for("admin_login"))

    return render_template("agent_register.html", errors=[])


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():

    errors = []

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username:
            errors.append("Username is required")

        if not password:
            errors.append("Password is required")

        if not errors:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                "SELECT * FROM agent_credentials WHERE username=%s AND password=%s",
                (username, password)
            )

            admin = cursor.fetchone()
            cursor.close()
            conn.close()

            if not admin:
                errors.append("Invalid username or password")

            else:
                session["admin_id"] = admin["agent_id"]
                session["admin_name"] = admin["username"]
                return redirect(url_for("admin_dashboard"))

        return render_template(
            "admin_login.html",
            errors=errors,
            username=username
        )

    return render_template("admin_login.html", errors=[])


def generate_monthly_bills():
    conn = get_db_connection()
    main_cursor = conn.cursor(dictionary=True)

    today = datetime.today().date()

    main_cursor.execute("""
        SELECT customer_details.customer_id,
               customer_details.start_date,
               newspaper_details.rate_per_day,
               newspaper_details.subscription_id
        FROM customer_details
        JOIN newspaper_details
        ON customer_details.customer_id = newspaper_details.customer_id
    """)
    customers = main_cursor.fetchall()

    UNPAID_STATUS = 2

    for c in customers:
        customer_id = c["customer_id"]
        start = c["start_date"]
        rate = c["rate_per_day"]
        subscription_id = c["subscription_id"]

        month_cursor = start.replace(day=1)

        while month_cursor <= today:
            year = month_cursor.year
            month = month_cursor.month
            month_name = calendar.month_name[month]
            bill_month = month_name + " " + str(year)

            days_in_month = calendar.monthrange(year, month)[1]
            month_start = month_cursor
            last_day_of_month = datetime(year, month, days_in_month).date()

            month_end = min(last_day_of_month, today)
            total_days = (month_end - month_start).days + 1

            pause_cursor = conn.cursor(dictionary=True)
            pause_cursor.execute("""
                SELECT pause_start, pause_end
                FROM pause_details
                WHERE subscription_id=%s
                AND pause_start <= %s
                AND pause_end >= %s
            """, (subscription_id, month_end, month_start))

            pauses = pause_cursor.fetchall()
            pause_cursor.close()

            paused_days = 0
            for p in pauses:
                ps = max(p["pause_start"], month_start)
                pe = min(p["pause_end"], month_end)
                if ps <= pe:
                    paused_days += (pe - ps).days + 1

            active_days = max(0, total_days - paused_days)
            amount = active_days * rate

            bill_cursor = conn.cursor()
            bill_cursor.execute("""
                SELECT bill_id FROM bills
                WHERE customer_id=%s AND bill_month=%s
            """, (customer_id, bill_month))

            exists = bill_cursor.fetchone()

            if not exists:
                bill_cursor.execute("""
                    INSERT INTO bills
                    (customer_id, bill_month, days_active, amount, amount_status)
                    VALUES (%s,%s,%s,%s,%s)
                """, (customer_id, bill_month, active_days, amount, UNPAID_STATUS))

            bill_cursor.close()

            if month == 12:
                month_cursor = datetime(year + 1, 1, 1).date()
            else:
                month_cursor = datetime(year, month + 1, 1).date()

    conn.commit()
    main_cursor.close()
    conn.close()

@app.route("/admin_add_customer", methods=["GET", "POST"])
def admin_add_customer():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":

        errors = []

        mobile = request.form.get("mobile", "").strip()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "").strip()
        area = request.form.get("area", "").strip()
        landmark = request.form.get("landmark_building", "").strip()
        flat_no = request.form.get("flat_house_office_no", "").strip()
        start_date = request.form.get("start_date", "").strip()
        newspaper = request.form.get("newspaper", "").strip()
        monthly_amount = request.form.get("monthly_amount", "").strip()

        rate = None


        if not name:
            errors.append("Name is required")
        elif not re.match(r"^(?!([A-Za-z])\1+$)(?!([A-Za-z]{2})\2+$)[A-Za-z ]{3,50}$", name):
            errors.append("Enter a valid name")

        if not mobile:
            errors.append("Mobile number is required")
        elif not re.match(r"^(?!([6-9])\1{9}$)[6-9]\d{9}$", mobile):
            errors.append("Enter a valid Indian mobile number")

        if not password:
            errors.append("Password is required")
        elif not re.match(r"^(?=.*[!@#$%^&*(),.?\":{}|<>]).{6,}$", password):
            errors.append("Password must be at least 6 characters and include one special symbol")

        if not area:
            errors.append("Area is required")
        elif not re.match(r"^(?!([A-Za-z])\1+$)[A-Za-z ]{3,100}$", area):
            errors.append("Enter a valid area name")

        if not landmark:
            errors.append("Landmark / Building is required")
        elif not re.match(r"^(?!([A-Za-z0-9])\1+$)[A-Za-z0-9 ,.-]{3,100}$", landmark):
            errors.append("Enter a valid landmark")

        if not flat_no:
            errors.append("Flat / House / Office No. is required")
        elif not re.match(r"^(?!([A-Za-z0-9])\1+$)[A-Za-z0-9/-]{1,20}$", flat_no):
            errors.append("Enter a valid flat/house number")

        if not start_date:
            errors.append("Start date is required")
        else:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                errors.append("Invalid start date format (YYYY-MM-DD required)")

        if not newspaper:
            errors.append("Newspaper is required")

        if not monthly_amount:
            errors.append("Monthly subscription amount is required")
        else:
            try:
                monthly_amount = float(monthly_amount)
                if monthly_amount <= 0:
                    errors.append("Monthly amount must be greater than 0")
                else:
                    rate = round(monthly_amount / 30.0, 2)
            except ValueError:
                errors.append("Monthly amount must be a valid number")


        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT customer_id FROM customer_details WHERE mobile_no = %s",
            (mobile,)
        )
        existing = cursor.fetchone()

        if existing:
            errors.append("Mobile number already exists")

        if errors:
            cursor.close()
            connection.close()

            return render_template(
            "admin_add_customer.html",
            errors=errors,
            name=name,
            mobile=mobile,
            area=area,
            landmark_building=landmark,
            flat_house_office_no=flat_no,
            monthly_amount=monthly_amount,
            start_date=start_date,
            newspaper=newspaper
    )


        try:
            cursor.execute("""
                INSERT INTO customer_details
                (agent_id, name, password, mobile_no, area_locality,
                 landmark_building, flat_house_office_no, start_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session["admin_id"],
                name,
                password,
                mobile,
                area,
                landmark,
                flat_no,
                start_date
            ))

            new_customer_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO newspaper_details
                (customer_id, newspaper_name, language,
                 delivery_frequency, rate_per_day)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                new_customer_id,
                newspaper,
                "English",
                "Daily",
                rate
            ))

            connection.commit()

        except Exception as e:
            connection.rollback()
            print("DATABASE ERROR:", e)
            flash("Database error occurred while adding customer", "danger")
            cursor.close()
            connection.close()
            return redirect(url_for("admin_add_customer"))

        cursor.close()
        connection.close()

        flash("Customer added successfully", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_add_customer.html")




@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    generate_monthly_bills()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    today = datetime.today()
    today = today.date()

    current_month_name = calendar.month_name[today.month]
    current_year = today.year
    current_month = current_month_name + " " + str(current_year)
    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    previous_month_name = calendar.month_name[last_day_of_previous_month.month]
    previous_year = last_day_of_previous_month.year
    previous_month = previous_month_name + " " + str(previous_year)

    cursor.execute(
        "SELECT COUNT(*) AS total_customers FROM customer_details WHERE agent_id=%s",
        (session["admin_id"],)
    )
    total_customers_result = cursor.fetchone()
    total_customers = total_customers_result["total_customers"]

    cursor.execute(
        "SELECT SUM(bills.amount) AS total_bill "
        "FROM bills "
        "JOIN customer_details ON bills.customer_id = customer_details.customer_id "
        "WHERE customer_details.agent_id=%s AND bills.bill_month=%s",
        (session["admin_id"], current_month)
    )
    total_bill_result = cursor.fetchone()
    if total_bill_result["total_bill"] is None:
        total_bill = 0
    else:
        total_bill = total_bill_result["total_bill"]

    cursor.execute(
        "SELECT SUM(bills.amount) AS collected_last_month "
        "FROM bills "
        "JOIN customer_details ON bills.customer_id = customer_details.customer_id "
        "WHERE customer_details.agent_id=%s AND bills.bill_month=%s AND bills.amount_status=1",
        (session["admin_id"], previous_month)
    )
    collected_last_month_result = cursor.fetchone()
    if collected_last_month_result["collected_last_month"] is None:
        collected_last_month = 0
    else:
        collected_last_month = collected_last_month_result["collected_last_month"]

    cursor.execute(
        "SELECT DISTINCT newspaper_details.customer_id "
        "FROM newspaper_details "
        "JOIN customer_details ON newspaper_details.customer_id = customer_details.customer_id "
        "WHERE customer_details.agent_id=%s",
        (session["admin_id"],)
    )
    subscriptions_result = cursor.fetchall()

    paused_today_list = []

    for subscription_row in subscriptions_result:
        customer_id = subscription_row["customer_id"]

        cursor.execute(
            "SELECT pause_details.pause_start, pause_details.pause_end "
            "FROM pause_details "
            "JOIN newspaper_details ON pause_details.subscription_id = newspaper_details.subscription_id "
            "WHERE newspaper_details.customer_id=%s",
            (customer_id,)
        )
        pause_dates_result = cursor.fetchall()

        for pause_row in pause_dates_result:
            pause_start = pause_row["pause_start"]
            pause_end = pause_row["pause_end"]

            if pause_start <= today and today <= pause_end:
                paused_today_list.append(customer_id)
                break

    active_today = total_customers - len(paused_today_list)

    cursor.execute(
        "SELECT COUNT(DISTINCT customer_details.customer_id) AS paused_today "
        "FROM pause_details "
        "JOIN newspaper_details ON pause_details.subscription_id = newspaper_details.subscription_id "
        "JOIN customer_details ON newspaper_details.customer_id = customer_details.customer_id "
        "WHERE customer_details.agent_id=%s "
        "AND %s BETWEEN pause_details.pause_start AND pause_details.pause_end",
        (session["admin_id"], today)
    )
    paused_today_result = cursor.fetchone()
    paused_today = paused_today_result["paused_today"]

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        name=session["admin_name"],
        total_customers=total_customers,
        active_today=active_today,
        paused_today=paused_today,
        total_bill=total_bill,
        collected_last_month=collected_last_month,
        current_month_name=current_month_name,
        previous_month_name=previous_month_name
    )

@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM customer_details WHERE customer_id = %s",
        (customer_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('admin_customers'))



@app.route("/admin/bulk_customer_upload")
def bulk_customer_upload():
    return render_template("admin_bulk_customer_upload.html")



@app.route("/admin/upload_bulk_customers", methods=["POST"])
def upload_bulk_customers():

    file = request.files['file']
    df = pd.read_csv(file)

    conn = get_db_connection()
    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute(
            "SELECT customer_id FROM customer_details WHERE mobile_no=%s",
            (row['mobile_no'],)
        )

        exists = cursor.fetchone()

        if not exists:
            cursor.execute("""
            INSERT INTO customer_details
            (agent_id, name, password, mobile_no, area_locality,
            landmark_building, flat_house_office_no, start_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                row['agent_id'],
                row['name'],
                row['password'],
                row['mobile_no'],
                row['area_locality'],
                row['landmark_building'],
                row['flat_house_office_no'],
                row['start_date']
            ))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Bulk customers added successfully")
    return redirect(url_for("admin_add_customer"))
from datetime import datetime
 

@app.route("/customer_login", methods=["GET", "POST"])
def customer_login():

    errors = []

    if request.method == "POST":

        mobile_no = request.form.get("mobile_no", "").strip()
        password = request.form.get("password", "").strip()

        if not mobile_no:
            errors.append("Mobile number is required")
        elif not mobile_no.isdigit():
            errors.append("Mobile number must contain only digits")
        elif len(mobile_no) != 10:
            errors.append("Mobile number must be 10 digits")

        if not password:
            errors.append("Password is required")

        if not errors:
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

            if not customer:
                errors.append("Invalid mobile number or password")
            else:
                session["customer_id"] = customer["customer_id"]
                session["customer_name"] = customer["name"]
                return redirect(url_for("customer_dashboard"))

        return render_template(
            "customer_login.html",
            errors=errors,
            mobile_no=mobile_no
        )

    return render_template("customer_login.html", errors=[])





@app.route("/customer_dashboard")
def customer_dashboard():
    if "customer_id" not in session:
        return redirect(url_for("customer_login"))
    generate_monthly_bills()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    today = datetime.now().date()
    current_month = today.strftime("%B %Y")

    cursor.execute("""
        SELECT amount, days_active
        FROM bills
        WHERE customer_id=%s AND bill_month=%s
    """, (session["customer_id"], current_month))
    current = cursor.fetchone()


    first_day_current = today.replace(day=1)
    prev_month_date = first_day_current - timedelta(days=1)
    previous_month = prev_month_date.strftime("%B %Y")

    cursor.execute("""
        SELECT bill_month, amount, amount_status
        FROM bills
        WHERE customer_id=%s AND bill_month=%s
        LIMIT 1
    """, (session["customer_id"], previous_month))
    last_bill = cursor.fetchone()


    cursor.execute("""
        SELECT SUM(amount) AS paid
        FROM bills
        WHERE customer_id=%s AND amount_status=1
    """, (session["customer_id"],))
    paid = cursor.fetchone()["paid"] or 0


    cursor.execute("""
        SELECT newspaper_name, rate_per_day
        FROM newspaper_details
        WHERE customer_id=%s
    """, (session["customer_id"],))
    subscription = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "customer_dashboard.html",
        name=session["customer_name"],
        subscription=subscription,
        current_month_bill=current["amount"] if current else 0,
        total_paid=paid,
        last_month_bill=last_bill,
        last_month_name=last_bill["bill_month"] if last_bill else previous_month
    )



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

@app.route("/download_bill/<int:bill_id>")
def download_bill_pdf(bill_id):

    if "customer_id" not in session:
        return redirect(url_for("customer_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            b.bill_id,
            b.bill_month,
            b.amount,
            b.days_active,
            c.name AS customer_name,
            a.username AS agent_name,
            n.newspaper_name,
            n.rate_per_day
        FROM bills b
        JOIN customer_details c 
            ON b.customer_id = c.customer_id
        JOIN agent_credentials a 
            ON c.agent_id = a.agent_id
        JOIN newspaper_details n 
            ON c.customer_id = n.customer_id
        WHERE b.bill_id = %s
    """, (bill_id,))

    bill = cursor.fetchone()

    cursor.close()
    conn.close()

    if not bill:
        return "Bill not found"

    pdf = FPDF()
    pdf.add_page()

    # Header
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "NEWSPAPER BILL", 0, 1, "C")

    pdf.ln(5)

    # Bill details
    pdf.set_font("Arial", "", 12)

    pdf.cell(100, 8, f"Bill ID: {bill['bill_id']}", 0, 0)
    pdf.cell(0, 8, f"Month: {bill['bill_month']}", 0, 1)

    pdf.cell(100, 8, f"Customer: {bill['customer_name']}", 0, 0)
    pdf.cell(0, 8, f"Agent: {bill['agent_name']}", 0, 1)

    pdf.ln(10)

    # Table Header
    pdf.set_font("Arial", "B", 12)

    pdf.cell(70, 10, "Newspaper", 1)
    pdf.cell(30, 10, "Rate/Day", 1)
    pdf.cell(30, 10, "Days", 1)
    pdf.cell(40, 10, "Amount", 1)
    pdf.ln()

    # Table Data
    pdf.set_font("Arial", "", 12)

    pdf.cell(70, 10, bill["newspaper_name"], 1)
    pdf.cell(30, 10, f"Rs.{bill['rate_per_day']}", 1, 0, "C")
    pdf.cell(30, 10, str(bill["days_active"]), 1, 0, "C")
    pdf.cell(40, 10, f"Rs.{bill['amount']}", 1, 0, "R")
    pdf.ln()

    pdf.ln(10)

    # Total section
    pdf.set_font("Arial", "B", 12)

    pdf.cell(130, 10, "Total Amount", 1)
    pdf.cell(40, 10, f"Rs.{bill['amount']}", 1, 0, "R")

    # Generate PDF response
    response = make_response(pdf.output(dest="S").encode("latin-1"))
    response.headers.set("Content-Disposition", "attachment", filename=f"bill_{bill_id}.pdf")
    response.headers.set("Content-Type", "application/pdf")

    return response

@app.route("/admin/bills")
def admin_bills():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    generate_monthly_bills()

    page = request.args.get("page", 1, type=int)

    connection = get_db_connection()
    database_cursor = connection.cursor(dictionary=True)

    database_cursor.execute("""
        SELECT 
            bills.bill_id,
            bills.bill_month,
            bills.amount,
            bills.amount_status,
            bills.customer_id,
            customer_details.name,
            customer_details.mobile_no
        FROM bills
        JOIN customer_details
            ON bills.customer_id = customer_details.customer_id
        WHERE customer_details.agent_id = %s
    """, (session["admin_id"],))

    all_bills_result = database_cursor.fetchall()

    database_cursor.close()
    connection.close()

    month_list = []
    for bill in all_bills_result:
        if bill["bill_month"] not in month_list:
            month_list.append(bill["bill_month"])

    month_tuples = []
    for month_name_year in month_list:
        parts = month_name_year.split(" ")
        if len(parts) == 2:
            month_name = parts[0]
            year_number = int(parts[1])
            month_number = 1
            month_names = [
                "", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            for i in range(1, 13):
                if month_names[i] == month_name:
                    month_number = i
                    break
            month_tuples.append((year_number, month_number, month_name_year))
        else:
            month_tuples.append((0, 0, month_name_year)) 


    month_tuples_sorted = []
    while len(month_tuples) > 0:
        max_index = 0
        for i in range(1, len(month_tuples)):
            if month_tuples[i][0] > month_tuples[max_index][0]:
                max_index = i
            elif month_tuples[i][0] == month_tuples[max_index][0] and month_tuples[i][1] > month_tuples[max_index][1]:
                max_index = i
        month_tuples_sorted.append(month_tuples[max_index])
        month_tuples.pop(max_index)


    total_pages = len(month_tuples_sorted)

    if page < 1:
        page = 1
    if page > total_pages and total_pages > 0:
        page = total_pages

    bills_grouped_dirty = {}

    if total_pages > 0:
        selected_month_tuple = month_tuples_sorted[page - 1]
        month_name_year = selected_month_tuple[2]

        bills_grouped_dirty[month_name_year] = []

        for bill in all_bills_result:
            if bill["bill_month"] == month_name_year:
                bills_grouped_dirty[month_name_year].append(bill)

    return render_template(
        "admin_bills.html",
        bills_grouped=bills_grouped_dirty,
        page=page,
        total_pages=total_pages
    )

from fpdf import FPDF
from flask import make_response

@app.route("/admin/bills/download/<int:customer_id>")
def download_customer_pdf(customer_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            bills.bill_id,
            bills.bill_month,
            bills.amount,
            bills.amount_status,
            customer_details.name,
            customer_details.mobile_no
        FROM bills
        JOIN customer_details
            ON bills.customer_id = customer_details.customer_id
        WHERE bills.customer_id = %s
        AND customer_details.agent_id = %s
    """, (customer_id, session["admin_id"]))

    bills = cursor.fetchall()

    cursor.close()
    connection.close()

    if not bills:
        return "No bills found"

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Customer Bills Report", ln=True, align="C")

    pdf.ln(10)

    pdf.set_font("Arial", size=12)

    pdf.cell(0, 8, f"Name: {bills[0]['name']}", ln=True)
    pdf.cell(0, 8, f"Mobile: {bills[0]['mobile_no']}", ln=True)

    pdf.ln(5)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(25, 10, "Bill ID", 1)
    pdf.cell(40, 10, "Month", 1)
    pdf.cell(30, 10, "Amount", 1)
    
    pdf.ln()

    pdf.set_font("Arial", size=10)

    for bill in bills:
        pdf.cell(25, 10, str(bill["bill_id"]), 1)
        pdf.cell(40, 10, bill["bill_month"], 1)
        pdf.cell(30, 10, str(bill["amount"]), 1)
        pdf.ln()

    response = make_response(pdf.output(dest="S").encode("latin-1"))
    response.headers.set("Content-Type", "application/pdf")
    response.headers.set("Content-Disposition","attachment",
        filename=f"{bills[0]['name']}_bills.pdf",
    )

    return response


@app.route("/admin_pause_requests")
def admin_pause_requests():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    database_cursor = connection.cursor(dictionary=True)

    sql_query = """
        SELECT pause_details.pause_id, pause_details.subscription_id,
               pause_details.pause_start, pause_details.pause_end,
               pause_details.seen, pause_reason.reason,
               customer_details.name AS customer_name
        FROM pause_details
        LEFT JOIN pause_reason ON pause_details.pause_id = pause_reason.pause_id
        JOIN newspaper_details ON pause_details.subscription_id = newspaper_details.subscription_id
        JOIN customer_details ON newspaper_details.customer_id = customer_details.customer_id
        WHERE customer_details.agent_id = %s
        ORDER BY pause_details.pause_start DESC
    """
    database_cursor.execute(sql_query, (session["admin_id"],))

    all_pause_requests = database_cursor.fetchall()

    new_requests_count = 0
    for single_request in all_pause_requests:
        if single_request["seen"] == 0:
            new_requests_count = new_requests_count + 1

    database_cursor.close()
    connection.close()

    return render_template(
        "admin_pause_requests.html",
        requests=all_pause_requests,
        new_requests=new_requests_count
    )

    
@app.route("/admin/toggle_bill/<bill_id>")
def toggle_bill(bill_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    bill_id = int(bill_id)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
                  UPDATE bills
                SET amount_status = CASE 
                WHEN amount_status = 2 THEN 1 
                ELSE 2 
                END
                WHERE bill_id=%s
            """, (bill_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("admin_bills"))

@app.route("/mark_seen/<pause_id>")
def mark_seen(pause_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    pause_id = int(pause_id)

    connection = get_db_connection()
    database_cursor = connection.cursor()
    database_cursor.execute("""
        UPDATE pause_details
        SET seen = 1
        WHERE pause_id = %s
    """, (pause_id,))
    connection.commit()

    database_cursor.close()
    connection.close()

    return redirect(url_for("admin_pause_requests"))


@app.route("/logout")
def logout():
    session.pop("admin_id", None)
    session.pop("customer_id", None)
    return redirect(url_for("home"))



@app.route("/customer_pause_request", methods=["GET", "POST"])
def customer_pause_request():
    if "customer_id" not in session:
        return redirect(url_for("customer_login"))

    connection = get_db_connection()
    database_cursor = connection.cursor(dictionary=True)

    today = date.today()

    if request.method == "POST":
        pause_start_str = request.form.get("pause_start")
        pause_end_str = request.form.get("pause_end")
        reason = request.form.get("reason", "")

        pause_start_parts = pause_start_str.split("-")
        pause_start_date = date(
            int(pause_start_parts[0]),
            int(pause_start_parts[1]),
            int(pause_start_parts[2])
        )

        pause_end_parts = pause_end_str.split("-")
        pause_end_date = date(
            int(pause_end_parts[0]),
            int(pause_end_parts[1]),
            int(pause_end_parts[2])
        )

        if pause_start_date < today:
            flash("Pause start date cannot be in the past.", "error")
            database_cursor.close()
            connection.close()
            return redirect(url_for("customer_pause_request"))

        if pause_end_date < pause_start_date:
            flash("Pause end date cannot be before start date.", "error")
            database_cursor.close()
            connection.close()
            return redirect(url_for("customer_pause_request"))

        database_cursor.execute(
            "SELECT subscription_id FROM newspaper_details WHERE customer_id = %s",
            (session["customer_id"],))
        subscription_result = database_cursor.fetchone()

        if not subscription_result:
            flash("No active subscription found.", "error")
            database_cursor.close()
            connection.close()
            return redirect(url_for("customer_dashboard"))

        subscription_id = subscription_result["subscription_id"]

        database_cursor.execute(
            "INSERT INTO pause_details (subscription_id, pause_start, pause_end, seen) VALUES (%s, %s, %s, 0)",
            (subscription_id, pause_start_date, pause_end_date))

        pause_id = database_cursor.lastrowid

        if reason != "":
            database_cursor.execute(
                "INSERT INTO pause_reason (pause_id, reason) VALUES (%s, %s)",
                (pause_id, reason))

        connection.commit()
        database_cursor.close()
        connection.close()

        flash("Pause request submitted successfully", "success")
        return redirect(url_for("customer_dashboard"))
    
    database_cursor.execute(
        "SELECT subscription_id, newspaper_name FROM newspaper_details WHERE customer_id = %s",
        (session["customer_id"],))
    subscription_result = database_cursor.fetchone()

    database_cursor.close()
    connection.close()
    return render_template(
        "customer_pause_request.html",
        subscription=subscription_result,
        date=date)


@app.route("/admin/customers")
def admin_customers():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""SELECT 
            customer_id,
            name,
            mobile_no,
            area_locality,
            landmark_building,
            flat_house_office_no
        FROM customer_details
        WHERE agent_id = %s
        ORDER BY name ASC
    """, (session["admin_id"],))

    customers = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_customers.html", customers=customers)



if __name__ == "__main__":
    app.run(debug=True)









