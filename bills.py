from datetime import date, timedelta
from db import get_db_connection


def generate_monthly_bills():

    today = date.today()

    if today.day != 1:
        print("Not first day")
        return




    months = [
        "January", "February", "March", "April",
        "May", "June", "July", "August",
        "September", "October", "November", "December"
    ]

    current_month_number = today.month
    current_year = today.year

    for i in range(len(months)):
        if i + 1 == current_month_number:

            if i == 0:
                prev_month_name = months[11]
                month = 12
                year = current_year - 1
            else:
                prev_month_name = months[i - 1]
                month = i
                year = current_year

            break




    first_day_this_month = date(today.year, today.month, 1)
    last_day_prev_month = first_day_this_month - timedelta(days=1)

    bill_month_name = prev_month_name + " " + str(year)

    print("Generating bill for:", bill_month_name)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)




    cursor.execute("SELECT * FROM customer_details")
    customers = cursor.fetchall()

    for customer in customers:

        customer_id = customer["customer_id"]
        start_date = customer["start_date"]



        if start_date > last_day_prev_month:
            continue



        cursor.execute("""
            SELECT * FROM newspaper_details
            WHERE customer_id = %s
        """, (customer_id,))
        newspaper = cursor.fetchone()

        if not newspaper:
            continue

        rate_per_day = float(newspaper["rate_per_day"])
        subscription_id = newspaper["subscription_id"]



        first_day = date(year, month, 1)
        last_day = last_day_prev_month
        total_days = (last_day - first_day).days + 1




        if start_date > first_day:
            total_days = (last_day - start_date).days + 1



        cursor.execute("""
            SELECT * FROM pause_details
            WHERE subscription_id = %s
            AND (
                (pause_start BETWEEN %s AND %s)
                OR
                (pause_end BETWEEN %s AND %s)
            )
        """, (subscription_id, first_day, last_day, first_day, last_day))

        pauses = cursor.fetchall()

        pause_days = 0

        for p in pauses:
            ps = p["pause_start"]
            pe = p["pause_end"]




            if ps < first_day:
                ps = first_day
            if pe > last_day:
                pe = last_day

            pause_days += (pe - ps).days + 1

        # -------- Final calculation --------
        chargeable_days = total_days - pause_days

        if chargeable_days < 0:
            chargeable_days = 0

        amount = chargeable_days * rate_per_day

        print("Customer:", customer_id)
        print("Days:", total_days)
        print("Pause:", pause_days)
        print("Chargeable:", chargeable_days)
        print("Amount:", amount)

        # -------- Insert bill --------
        cursor.execute("""
            INSERT INTO bills (customer_id, bill_month, amount, days_active)
            VALUES (%s, %s, %s, %s)
        """, (customer_id, bill_month_name, amount, chargeable_days))

        conn.commit()

    cursor.close()
    conn.close()

    print("Bills generated successfully.")
