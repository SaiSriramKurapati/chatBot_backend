# Base Image
FROM python:3.9-slim AS base

# Working directory
WORKDIR /backend

# Copying the requirements file into the container
COPY requirements.txt .

# Install any dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copying the rest of the backend application code
COPY . .

# Expose port 8000 for the FastAPI application
EXPOSE 8000


# Command to run the FastAPI app
# Production stage
FROM base AS prod
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

#Test stage
FROM base AS test 
# Install test dependencies (pytest)
RUN pip install pytest
# Command to run the tests
CMD ["pytest"]