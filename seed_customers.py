from faker import Faker
import random
from datetime import date, timedelta
from db import get_db_connection

fake = Faker("en_IN")
fake.unique.clear()

AREAS = ["Vijay Nagar", "Palasia", "Tilak Nagar", "Rajendra Nagar", "Bhawarkuan"]
LANDMARKS = ["Near Temple", "Opp Mall", "Main Road", "Near School", "Near Hospital"]
NEWSPAPERS = ["The Hindu", "The Times", "Naidunia", "Dainik Bhaskar"]


def random_start_date():
    today = date.today()
    days_back = random.randint(0, 180)
    return today - timedelta(days=days_back)


def populate_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT agent_id FROM agent_credentials")
    agent_rows = cursor.fetchall()

    agent_ids = [row[0] for row in agent_rows]


    for i in range(1000):
        agent_id = random.choice(agent_ids)

        name = fake.name()
        mobile = fake.unique.msisdn()[:10]
        password = "1234"
        area = random.choice(AREAS)
        landmark = random.choice(LANDMARKS)
        flat_no = f"Flat {random.randint(1, 800)}"
        start_date = random_start_date()

        cursor.execute("""
            INSERT INTO customer_details
            (agent_id, name, password, mobile_no, area_locality,
             landmark_building, flat_house_office_no, start_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            agent_id,
            name,
            password,
            mobile,
            area,
            landmark,
            flat_no,
            start_date
        ))

        customer_id = cursor.lastrowid
        newspaper = random.choice(NEWSPAPERS)
        rate = random.randint(3, 12)

        cursor.execute("""
            INSERT INTO newspaper_details
            (customer_id, newspaper_name, language, delivery_frequency, rate_per_day)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            customer_id,
            newspaper,
            "English",
            "Daily",
            rate
        ))

    conn.commit()
    cursor.close()
    conn.close()

    print("coustomer added")

