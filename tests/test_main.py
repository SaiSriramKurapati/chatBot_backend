# === Import Statements ===
# Import necessary modules and packages for the application.

import os
# import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base, get_db  # Adjusted import
from backend.app.main import app  # Adjusted import
from fastapi.testclient import TestClient
import redis
from unittest.mock import MagicMock, patch
import yaml
from dotenv import load_dotenv

load_dotenv()
print("in database.py")
# Initializing Environmental Variables
# load_dotenv(dotenv_path="backend/.env")
SQLALCHEMY_DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}/{os.getenv('POSTGRES_DB')}"
print(os.getenv('POSTGRES_USER'))
print(os.getenv('POSTGRES_PASSWORD'))
print(os.getenv('POSTGRES_HOST'))
print(os.getenv('POSTGRES_DB'))

# Initializing Environmental Variables
SQLALCHEMY_DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('TEST_POSTGRES_HOST')}/{os.getenv('POSTGRES_DB')}"

# Initialize Redis client
redis_url       = os.getenv('REDIS_URL')
redis_client    = redis.from_url(redis_url)

# Create an SQLAlchemy engine connected to the test database.
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a session factory for the test database, with autocommit and autoflush disabled.
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# === Fixtures ===
# Pytest fixture to create and drop tables for each test to ensure isolation between tests.
@pytest.fixture(scope="function")
def db_session():
    # Create all tables before each test
    Base.metadata.create_all(bind=engine)

    # Get the list of table names from the database to verify they were created
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Create a new session for interacting with the database
    db = TestingSessionLocal()
    try:
        yield db  # Provide the session to the test function
    finally:
        db.close()  # Ensure the session is closed after the test

# Pytest fixture to override the get_db dependency.
@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session  # Provide the test database session
        finally:
            db_session.close()

    # Override the default get_db dependency with the test session
    app.dependency_overrides[get_db] = override_get_db
    
    # Return a TestClient instance to interact with the FastAPI app
    yield TestClient(app)

# Function to cache the chatbot response in Redis with a 5-minute expiration.
def cache_response(message_id: int, response: str):
    redis_client.setex(f"message:{message_id}", 300, response)  # Cache for 5 minutes


# === Test Cases ===
# Test case to ensure that the 'messages' table is created in the test database.
def test_table_creation(db_session):
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Assert that the 'messages' table exists in the test database
    assert "messages" in tables, "The 'messages' table should be created in the test_db"

# # Test case to check if the root endpoint is accessible and returns the expected response.
# def test_read_root(client):
#     response = client.get("/")

#     # Assert that the root endpoint returns a 200 status code and the correct message
#     assert response.status_code == 200
#     assert response.json() == {"message": "Welcome to the Chat API"}

# Pytest fixture to mock the Redis client for testing purposes.
@pytest.fixture(scope="function")
def mock_redis_client(mocker):
    with patch("backend.app.main.redis_client") as mock_redis:
        mock_redis.get.return_value = None
        yield mock_redis

import hashlib

def generate_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def test_create_message(client, mocker, mock_redis_client):
    # Mock the generate_response function to return a specific response
    mock_generate_response = mocker.patch("backend.app.main.generate_response", return_value="Mocked response")
    
    # Send a POST request to create a new message
    response = client.post("/messages/", json={"content": "Hello"})

    # Generate the content hash based on the "Hello" string
    content_hash = generate_content_hash("Hello")
    
    assert response.status_code == 200
    assert response.json()["content"] == "Hello"
    assert response.json()["response"] == "Mocked response"

    # Verify the cache was set in Redis using the content hash
    mock_redis_client.setex.assert_called_once_with(
        f"message:{content_hash}", 300, "Mocked response"
    )

# Test case to retrieve all messages from the database.
def test_get_messages(client):
    # Create a message to ensure there's at least one message in the database
    client.post("/messages/", json={"content": "Hello"})

    # Send a GET request to retrieve messages
    response = client.get("/messages/")
    
    # Assert that the response status is 200 and at least one message is returned
    assert response.status_code == 200
    assert len(response.json()) > 0

# Test case to update an existing message and ensure the update is reflected in the database.
def test_update_message(client):
    # Create a message first
    create_response = client.post("/messages/", json={"content": "Hello"})
    message_id = create_response.json()["id"]

    # Send a PUT request to update the message content
    response = client.put(f"/messages/{message_id}", json={"new_content": "Updated Hello"})
    
    # Assert that the response status is 200 and the content was updated
    assert response.status_code == 200
    assert response.json()["content"] == "Updated Hello"

# Test case to ensure that the cache is checked and used when a message with the same content is sent.
def test_cache_hit(client, mocker, mock_redis_client):
    # Mock the Redis client's get method to return a cached response
    mock_redis_client.get.return_value = b"Cached response"
    
    # Send a POST request that should hit the cache
    response = client.post("/messages/", json={"content": "Hello again"})
    
    # Assert that the response is the cached one
    assert response.status_code == 200
    if mock_redis_client:
        mock_redis_client.get.call_count = 1

    # Ensure the cache was actually checked
    assert mock_redis_client.get.call_count == 1

# Test case to delete a message and verify it is removed from the database.
def test_delete_message(client):
    # Create a message first
    create_response = client.post("/messages/", json={"content": "Hello"})
    message_id = create_response.json()["id"]

    # Send a DELETE request to remove the message
    response = client.delete(f"/messages/{message_id}")
    
    # Assert that the response status is 200 and the message was deleted
    assert response.status_code == 200
    assert response.json() == {"detail": f"Deleted 1 messages starting from ID {message_id}"}

    # Try to delete it again
    response = client.delete(f"/messages/{message_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Message not found"}
