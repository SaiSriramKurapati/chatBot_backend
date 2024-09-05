import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))
from sqlalchemy import Column, Integer, String
from database import Base

# === Define ORM Model for the 'Message' Table ===
# This class represents the 'messages' table in the database.
# It is an ORM (Object-Relational Mapping) model, meaning instances of this class correspond to rows in the 'messages' table.
# SQLAlchemy uses this class to interact with the database table.
class Message(Base):
    # The __tablename__ attribute sets the name of the table in the database.
    __tablename__ = "messages"

    # === Define Columns ===

    # Primary Key Column: 'id'
    # - Integer type column.
    # - Acts as the primary key for the table, meaning each value in this column is unique and identifies a single row.
    # - The 'primary_key=True' argument makes this column the primary key.
    # - 'index=True' creates an index on this column to optimize queries.
    # - 'autoincrement=True' ensures that each new message gets a unique ID automatically.
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Content Column: 'content'
    # - String type column that stores the content of the user's message.
    # - 'index=True' creates an index on this column to optimize search queries based on content.
    content = Column(String, index=True)

    # Response Column: 'response'
    # - String type column that stores the generated response to the user's message.
    # - 'index=True' creates an index on this column to optimize search queries based on response.
    response = Column(String, index=True)
