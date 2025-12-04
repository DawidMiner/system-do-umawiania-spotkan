import logging
import json
import uuid
import os
import azure.functions as func
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from datetime import datetime, timedelta

# --- STAŁE KONFIGURACYJNE ---
CONTAINER_USERS = "users"
CONTAINER_APPOINTMENTS = "appointments"
# STAŁA WARTOŚĆ DLA KLUCZA PARTYCJONOWANIA W TWOJEJ BAZIE
# Zrzut ekranu wskazał '/TenantId' jako klucz partycjonowania, używamy stałej wartości.
TENANT_ID_VALUE = "main_tenant"
# -----------------------------------------------------------------

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# =================================================================
# 1. FUNKCJA: DODAWANIE OSÓB (POST /api/AddUser)
# =================================================================

@app.route(route="AddUser", methods=["POST", "OPTIONS"])
def AddUser(req: func.HttpRequest) -> func.HttpResponse:
    # 1. JAWNA OBSŁUGA CORS OPTIONS
    if req.method == 'OPTIONS':
        return func.HttpResponse(status_code=200)

    logging.info('HTTP trigger processed request to add a User.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Proszę przekazać dane w formacie JSON.", status_code=400)

    name = req_body.get('name')
    email = req_body.get('email')

    if not name or not email:
        return func.HttpResponse(
            "Wymagane pola to 'name' i 'email'.",
            status_code=400
        )

    default_availability = {
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "start_time": "08:00",
        "end_time": "16:00"
    }

    new_user = {
        "id": str(uuid.uuid4()),
        "name": name,
        "email": email,
        "availability": default_availability,
        "TenantId": TENANT_ID_VALUE # <-- DODANY KLUCZ PARTYCJONOWANIA
    }

    try:
        # Konfiguracja i połączenie z Cosmos DB
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
        database = client.get_database_client(os.environ["COSMOS_DB_NAME"])
        users_container = database.get_container_client(CONTAINER_USERS)

        # Zapis do Cosmos DB z JAWNYM KLUCZEM PARTYCJONOWANIA
        users_container.create_item(
            body=new_user,
            partition_key=TENANT_ID_VALUE
        )

        return func.HttpResponse(
            json.dumps(new_user),
            mimetype="application/json",
            status_code=201
        )

    except CosmosHttpResponseError as e:
        # Błędy autoryzacji (401/403) i inne błędy Cosmos DB
        logging.error(f"Błąd Cosmos DB (HTTP): Status={e.status_code}, Treść={e.message}")
        return func.HttpResponse(
            f"Błąd Cosmos DB. Sprawdź klucz dostępu (COSMOS_KEY). Szczegóły: {e.status_code}",
            status_code=500
        )
    except Exception as e:
        # Ogólny błąd
        logging.error(f"Krytyczny błąd: {e}")
        return func.HttpResponse(
            f"Wystąpił nieznany błąd serwera: {e}",
            status_code=500
        )


# =================================================================
# 2. FUNKCJA: DODAWANIE SPOTKAŃ (POST /api/AddAppointment)
# =================================================================

@app.route(route="AddAppointment", methods=["POST", "OPTIONS"])
def AddAppointment(req: func.HttpRequest) -> func.HttpResponse:
    # 1. JAWNA OBSŁUGA CORS OPTIONS
    if req.method == 'OPTIONS':
        return func.HttpResponse(status_code=200)

    logging.info('HTTP trigger processed request to add an Appointment.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Proszę przekazać dane w formacie JSON.", status_code=400)

    user_id = req_body.get('user_id')
    client_name = req_body.get('client_name')
    start_time_iso = req_body.get('start_time')
    duration_minutes = req_body.get('duration_minutes', 30)

    if not user_id or not start_time_iso or not client_name:
        return func.HttpResponse(
            "Wymagane pola to 'user_id', 'client_name' i 'start_time'.",
            status_code=400
        )

    try:
        start_dt = datetime.fromisoformat(start_time_iso.replace('Z', '+00:00'))
        end_dt = start_dt + timedelta(minutes=duration_minutes)
    except ValueError:
        return func.HttpResponse("Nieprawidłowy format daty/czasu 'start_time'. Oczekiwany ISO 8601.", status_code=400)

    new_appointment = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "client_name": client_name,
        "start_time": start_time_iso,
        "end_time": end_dt.isoformat().replace('+00:00', 'Z'),
        "duration_minutes": duration_minutes,
        "TenantId": TENANT_ID_VALUE # <-- DODANY KLUCZ PARTYCJONOWANIA
    }

    try:
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
        database = client.get_database_client(os.environ["COSMOS_DB_NAME"])
        appointments_container = database.get_container_client(CONTAINER_APPOINTMENTS)

        # Zapis do Cosmos DB z JAWNYM KLUCZEM PARTYCJONOWANIA
        appointments_container.create_item(
            body=new_appointment,
            partition_key=TENANT_ID_VALUE
        )

        return func.HttpResponse(
            json.dumps(new_appointment),
            mimetype="application/json",
            status_code=201
        )

    except CosmosHttpResponseError as e:
        # Błędy autoryzacji (401/403) i inne błędy Cosmos DB
        logging.error(f"Błąd Cosmos DB (HTTP): Status={e.status_code}, Treść={e.message}")
        return func.HttpResponse(
            f"Błąd Cosmos DB. Sprawdź klucz dostępu (COSMOS_KEY). Szczegóły: {e.status_code}",
            status_code=500
        )
    except Exception as e:
        # Ogólny błąd
        logging.error(f"Krytyczny błąd: {e}")
        return func.HttpResponse(
            f"Wystąpił nieznany błąd serwera: {e}",
            status_code=500
        )