# Use the official Python image from the Docker Hub
FROM python:3-alpine

RUN apk add --no-cache tzdata
# Set the timezone to UTC
ENV TZ=UTC

# Set the working directory
WORKDIR /app

# Copy the requirements
COPY requirements.txt requirements.txt

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ./src/app.py app.py

# Expose the port the app runs on
ENV PORT=3000
EXPOSE 3000

# Run the application
CMD ["python", "app.py"]
