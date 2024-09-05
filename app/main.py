# === Import Statements ===
# Import necessary modules and packages for the application.
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import redis
import hashlib
from openai import OpenAI
from dotenv import load_dotenv
import logging
import yaml
from fastapi.staticfiles import StaticFiles

# === Initialize FastAPI App ===
# Create an instance of the FastAPI application and configure CORS.
app = FastAPI()

# === Import Internal Modules ===
# Import database session, models, schemas, and CRUD operations.
from database import SessionLocal, engine, Base, get_db
import models  # ORM models for database interaction
import schemas  # Pydantic schemas for data validation
import crud  # CRUD operations for database access

load_dotenv() 

# Initializing Environmental Variables
# SQLALCHEMY_DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}/{os.getenv('POSTGRES_DB')}"

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
redis_url               = os.getenv('REDIS_URL')
client                  = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# === Initialize Redis Client for Caching ===
# Set up Redis client to cache chatbot responses.
redis_client = redis.from_url(redis_url)

# === Database Setup ===
# Create database tables based on the models defined.
models.Base.metadata.create_all(bind=engine)

# === Dependency Injection ===
# Dependency to get the database session for use in endpoint functions.

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic schema for incoming messages
class Message(BaseModel):
    id: int
    content: str

# === Helper Functions ===

def generate_response(message: str) -> str:
    """
    Generate a response using OpenAI's GPT model.
    :param message: User's message.
    :return: Generated response as a string.
    """
    # Calls the `create` method from OpenAI's client library to generate a response using the GTP model.
    response = client.chat.completions.create(

    model="gpt-3.5-turbo", # Specifies the model to use for generating the response

    # messages is a ist of dictionaries, where each dictionary represents a message in the conversation.
    # The conversation is constructed as a list of role-based messages.
    messages=[ 
        {"role": "system", "content": "You are a helpful assistant."},  # System message to set the tone of the conversation
        {"role": "user", "content": message}  # User's message is passed as input to the model
    ]
    )
    # Return the content of the generated response. This accesses the content of the first choice in the response
    # generated by the model and also removes any leading or trailing whitespace using `.strip()` method.
    return response.choices[0].message.content.strip()


def generate_content_hash(content: str) -> str:
    """
    Generate a SHA-256 hash of the message content.
    :param content: The content to be hashed.
    :return: The SHA-256 hash as a string.
    """
    # Converts the input content (a string) into a bytes object using UTF-8 encoding,
    # then pass it to the hashlib.sha256() function to compute the SHA-256 hash.
    # The result is a hash object.
    hash_object = hashlib.sha256(content.encode('utf-8'))

    # Converts the hash object to a hexadecimal string representation of the hash.
    # This converts the hash from a raw binary format to a human-readable format.
    hash_hex = hash_object.hexdigest()

    # Returns the hexadecimal string of the hash to the caller.
    return hash_hex

def cache_response(content: str, response: str):
    """
    Cache the response in Redis with a key based on the content hash.
    :param content: The message content.
    :param response: The response to be cached.
    """
    # Generates a unique key for the cache entry by creating a SHA-256 hash of the content.
    # Prefixes the key with "message:" to distinguish it from other types of cached data.
    key = f"message:{generate_content_hash(content)}"

    # Stores the response in Redis using the generated key.
    # The `setex` method is used to set the value in the cache with an expiration time.
    # Here, the expiration time is set to 300 seconds (5 minutes).
    redis_client.setex(key, 300, response)


def check_cache_for_content(content: str):
    """
    Check if a response for the given content exists in the cache.
    
    This function generates a cache key based on the SHA-256 hash of the provided 
    content and checks if a corresponding response exists in Redis. If a cached 
    response is found, it is decoded from bytes to a UTF-8 string. If no cached 
    response is found, the function returns None.

    :param content: The message content for which to check the cache.
    :return: The cached response as a UTF-8 string if found, otherwise None.
    """
    # Generates a unique key for the cache entry by creating a SHA-256 hash of the content.
    # Prefixes the key with "message:" to distinguish it from other types of cached data.
    key = f"message:{generate_content_hash(content)}"

    # Attempts to retrieve the cached response from Redis using the generated key.
    cached_response = redis_client.get(key)

    # Checks if a cached response was found.
    # If a response exists, it will be in bytes format, so we decode it to a UTF-8 string.
    # If no cached response is found (i.e., cached_response is None), return None.
    if cached_response:
        return cached_response.decode('utf-8')

    # Return None if there was no cached response found for the given key.
    return None

# === Pydantic Models ===
# Define the request model for editing a message.
class EditMessageRequest(BaseModel):
    new_content: str

# === API Endpoints ===

@app.post("/messages/", response_model=schemas.Message)
async def send_message(message: schemas.MessageCreate, db: Session = Depends(get_db)):
    """
    Handles POST requests to send a message to the chatbot.
    Check the cache first; if not found, generates a new response.
    
    :param message: The message content submitted by the user.
    :param db: The database session, injected by FastAPI's dependency injection.
    :return: A JSON response containing the message ID, content, and chatbot's response.
    """
    # Checks if the response for the given content is already in the cache.
    # If a cached response is found, it's returned immediately.
    cached_response = check_cache_for_content(message.content)
    
    # If a cached response exists, use it to create a new database entry for the message
    # and return it along with the original content and cached response.
    if cached_response:
        db_message = crud.create_message(db=db, message=message, response=cached_response)
        return {"id": db_message.id, "content": message.content, "response": cached_response}

    # If no cached response is found, generates a new response using the AI model.
    response = generate_response(message.content)

    # Stores the newly generated message and response in the database.
    db_message = crud.create_message(db=db, message=message, response=response)

    # Caches the new response using the content as the key.
    cache_response(message.content, response)

    # Returns a JSON response containing the message ID, the original content,
    # and the newly generated response.
    return {"id": db_message.id, "content": db_message.content, "response": db_message.response}

# GET endpoint to retrieve all messages
@app.get("/messages/")
async def get_messages(skip: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    """
    Handles GET requests to retrieve a list of messages from the database.
    
    This function handles the retrieval of messages stored in the database. It supports 
    pagination by allowing the caller to specify how many records to skip and the maximum 
    number of records to return.

    :param skip: The number of records to skip (for pagination). Default is 1.
    :param limit: The maximum number of records to return. Default is 10.
    :param db: The database session, injected by FastAPI's dependency injection.
    :return: A list of message records retrieved from the database.
    """
    # Uses the CRUD utility to retrieve messages from the database.
    # The `skip` parameter allows the function to skip the specified number of records.
    # The `limit` parameter restricts the number of records returned to the specified limit.
    messages = crud.get_messages(db, skip=skip, limit=limit)

    # Returns the list of messages retrieved from the database.
    return messages

# PUT endpoint to edit a message by ID
@app.put("/messages/{message_id}", response_model=schemas.EditMessage)
async def edit_message(message_id: int, request: EditMessageRequest, db: Session = Depends(get_db)):
    """
    Handles PUT requests to edit an existing message by its ID.
    
    This function allows the client to update the content of an existing message. 
    It generates a new response based on the updated content, updates the message 
    in the database, and returns the updated message.

    :param message_id: The ID of the message to be edited.
    :param request: The request body containing the new content.
    :param db: The database session, injected by FastAPI's dependency injection.
    :return: The updated message with the new content and response.
    """
    # Extracts the new content from the request body.
    new_content = request.new_content
    
    # Generates a new response based on the updated content using the AI model.
    response = generate_response(new_content)

    # Updates the message in the database with the new content and the new response.
    message = crud.update_message(db=db, message_id=message_id, new_content=new_content, new_response=response)
    
    # If the message is not found in the database (i.e., message is None), raise a 404 error.
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Returns the updated message, which includes the new content and response.
    return message


# DELETE endpoint to delete a message by ID and all subsequent messages
@app.delete("/messages/{message_id}")
async def delete_message_and_following(message_id: int, db: Session = Depends(get_db)):
    """
    Handles DELETE requests to delete a specific message and all subsequent messages by their ID.
    
    This function will delete a message with the specified ID as well as all messages 
    that were created after it (i.e., messages with IDs greater than or equal to the specified ID).

    :param message_id: The ID of the message from which to start deleting.
    :param db: The database session, injected by FastAPI's dependency injection.
    :return: A JSON response indicating how many messages were deleted.
    """
    # Queries the database for all messages with an ID greater than or equal to the provided message_id.
    messages_to_delete = db.query(models.Message).filter(models.Message.id >= message_id).all()
    
    # If no messages are found, raises a 404 error indicating that the message was not found.
    if not messages_to_delete:
        raise HTTPException(status_code=404, detail="Message not found")

    # Iterates through the list of messages and deletes each one from the database.
    for message in messages_to_delete:
        db.delete(message)

    # Commit the changes to the database to ensure that the deletions are saved.
    db.commit()
    
    # Returns a JSON response indicating the number of messages deleted and the starting ID.
    return {"detail": f"Deleted {len(messages_to_delete)} messages starting from ID {message_id}"}


# === CORS Configuration ===
# Configure Cross-Origin Resource Sharing (CORS) to allow requests from the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)