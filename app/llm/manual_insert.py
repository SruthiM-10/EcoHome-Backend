import psycopg2
from app.llm.routes import unit_test
import pickle

def manual_insert(appliance_name):
    conn = psycopg2.connect("") # put database url

    with open("/Users/sruthi/PycharmProjects/EcoHome-Backend/app/llm/final_listings.pkl", "rb") as f:
        pickled_bytes = f.read()

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO listings (appliance, data)
        VALUES (%s, %s)
    """, (appliance_name, psycopg2.Binary(pickled_bytes)))

    conn.commit()
    cur.close()
    conn.close()

def manual_update(appliance_name):
    conn = psycopg2.connect("") # fill database url

    with open("/Users/sruthi/PycharmProjects/EcoHome-Backend/app/llm/final_listings.pkl", "rb") as f:
        pickled_bytes = f.read()

    cur = conn.cursor()
    cur.execute("""
            UPDATE listings (appliance, data)
            VALUES (%s, %s)
            WHERE appliance = %s
        """, (appliance_name, psycopg2.Binary(pickled_bytes)))

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    query = "dish washer"
    unit_test(query)
    manual_insert(query)
