import logging
import json
import uuid
import os
import azure.functions as func
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from datetime import datetime, timedelta


CONTAINER_USERS = "users"
TENANT_ID_VALUE = "main_tenant"

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type"
}

@app.route(route="AddUser", methods=["POST", "OPTIONS"])
def AddUser(req: func.HttpRequest) -> func.HttpResponse:

    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers=CORS_HEADERS
        )

    logging.info("HTTP trigger processed request to add a User.")

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Proszę przekazać dane w formacie JSON.",
            status_code=400,
            headers=CORS_HEADERS
        )

    name = req_body.get("name")
    email = req_body.get("email")

    if not name or not email:
        return func.HttpResponse(
            "Wymagane pola to 'name' i 'email'.",
            status_code=400,
            headers=CORS_HEADERS
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
        "TenantId": TENANT_ID_VALUE
    }

    try:
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
        database = client.get_database_client(os.environ["COSMOS_DB_NAME"])
        users_container = database.get_container_client(CONTAINER_USERS)

        users_container.create_item(body=new_user)

        return func.HttpResponse(
            json.dumps(new_user),
            status_code=201,
            mimetype="application/json",
            headers=CORS_HEADERS
        )

    except Exception as e:
        logging.error(f"Błąd: {e}")
        return func.HttpResponse(
            f"Błąd: {e}",
            status_code=500,
            headers=CORS_HEADERS
        )



@app.route(route="AddAppointment", methods=["POST", "OPTIONS"])
def AddAppointment(req: func.HttpRequest) -> func.HttpResponse:

    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers=CORS_HEADERS
        )

    logging.info("HTTP trigger processed request to add an Appointment.")

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Proszę przekazać dane w formacie JSON.",
            status_code=400,
            headers=CORS_HEADERS
        )

    user_id = req_body.get("user_id")
    client_name = req_body.get("client_name")
    start_time_iso = req_body.get("start_time_iso")

    if not user_id or not start_time_iso or not client_name:
        return func.HttpResponse(
            "Wymagane pola to 'user_id', 'client_name' i 'start_time'.",
            status_code=400,
            headers=CORS_HEADERS
        )

    try:
        start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(minutes=30)
    except ValueError:
        return func.HttpResponse(
            "Nieprawidłowy format daty/czasu 'start_time'. Oczekiwany ISO 8601.",
            status_code=400,
            headers=CORS_HEADERS
        )

    new_appointment = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "client_name": client_name,
        "start_time": start_time_iso,
        "end_time": end_dt.isoformat().replace("+00:00", "Z"),
        "TenantId": TENANT_ID_VALUE
    }

    try:
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
        database = client.get_database_client(os.environ["COSMOS_DB_NAME"])
        appointments_container = database.get_container_client(CONTAINER_USERS)

        appointments_container.create_item(body=new_appointment)

        return func.HttpResponse(
            json.dumps(new_appointment),
            mimetype="application/json",
            status_code=201,
            headers=CORS_HEADERS
        )

    except CosmosHttpResponseError as e:
        logging.error(f"Błąd Cosmos DB (HTTP): Status={e.status_code}, Treść={e.message}")
        return func.HttpResponse(
            f"Błąd Cosmos DB: Sprawdź klucz dostępu (COSMOS_KEY) lub nazwy. Szczegóły: {e.status_code}",
            status_code=500,
            headers=CORS_HEADERS
        )

    except Exception as e:
        logging.error(f"Krytyczny błąd: {e}")
        return func.HttpResponse(
            f"Wystąpił nieznany błąd serwera: {e}",
            status_code=500,
            headers=CORS_HEADERS
        )

@app.route(route="GetUsers", methods=["GET", "OPTIONS"])
def GetUsers(req: func.HttpRequest) -> func.HttpResponse:

    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers=CORS_HEADERS
        )

    logging.info("HTTP trigger processed request to get users list.")

    try:
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
        database = client.get_database_client(os.environ["COSMOS_DB_NAME"])
        users_container = database.get_container_client(CONTAINER_USERS)

        query = "SELECT * FROM c"

        users_data = list(users_container.query_items(
            query=query,
            enable_cross_partition_query=False,
            partition_key=TENANT_ID_VALUE
        ))

        filtered_users = [
            {"id": u.get("id"), "name": u.get("name")}
            for u in users_data
            if "name" in u and u["name"]
        ]

        return func.HttpResponse(
            json.dumps(filtered_users),
            status_code=200,
            mimetype="application/json",
            headers=CORS_HEADERS
        )

    except Exception as e:
        logging.error(f"Błąd podczas pobierania listy użytkowników: {e}")
        return func.HttpResponse(
            f"Błąd serwera: {e}",
            status_code=500,
            headers=CORS_HEADERS
        )


@app.route(route="GetUserAppointments", methods=["GET", "OPTIONS"])
def GetUserAppointments(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers=CORS_HEADERS)

    user_id = req.params.get("user_id")
    if not user_id:
        return func.HttpResponse(
            "Brak parametru 'user_id'.",
            status_code=400,
            headers=CORS_HEADERS
        )

    try:
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])
        database = client.get_database_client(os.environ["COSMOS_DB_NAME"])
        appointments_container = database.get_container_client(CONTAINER_USERS)

        query = "SELECT * FROM c WHERE c.user_id=@user_id"
        parameters = [{"name": "@user_id", "value": user_id}]

        appointments_data = list(appointments_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        return func.HttpResponse(
            json.dumps(appointments_data),
            status_code=200,
            mimetype="application/json",
            headers=CORS_HEADERS
        )
    except Exception as e:
        logging.error(f"Błąd podczas pobierania spotkań użytkownika: {e}")
        return func.HttpResponse(
            f"Błąd serwera: {e}",
            status_code=500,
            headers=CORS_HEADERS
        )
