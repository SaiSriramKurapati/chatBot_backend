from pydantic import BaseModel

# === Base Schema for Messages ===
# This base schema defines common fields that will be shared across multiple schemas.
class MessageBase(BaseModel):
    # The 'content' field represents the content of a message and is of type string.
    content: str

# === Schema for Creating a New Message ===
# This schema is used when a new message is being created.
# It inherits from 'MessageBase', meaning it includes the 'content' field
class MessageCreate(MessageBase):
    pass  # No additional fields are needed for creating a message, so we simply pass.

# === Schema for Representing a Message with ID and Response ===
# This schema is used when a message, including its ID and generated response, is returned.
class Message(MessageBase):
    # The 'id' field represents the unique identifier of the message.
    id: int

    # The 'content' field is inherited from 'MessageBase'.
    content: str

    # The 'response' field represents the AI-generated response associated with the message.
    response: str

    # === ORM Mode Configuration ===
    # 'Config' class is a special class in Pydantic that allows to directly return 
    #  SQLAlchemy models from our endpoints, and Pydantic will handle the conversion.
    class Config:
        orm_mode = True

# === Schema for Editing an Existing Message ===
# This schema is used when a message is being edited.
# It includes the message's ID, content, and the updated response.
class EditMessage(MessageBase): # the below parameters mean the same as the above function.
    id: int
    content: str
    response: str

    class Config:
        orm_mode = True
