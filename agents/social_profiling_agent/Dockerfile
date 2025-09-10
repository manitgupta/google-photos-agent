# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# --- Dependency Installation ---
# Copy only the requirements file first to leverage Docker cache.
COPY ./agents/social_profiling_agent/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- Application Code ---
# Copy the entire agent application code into a subdirectory inside the container.
COPY ./agents/social_profiling_agent /app/agents/social_profiling_agent

# --- Environment ---
# Set the PYTHONPATH so Python can find the agent module.
ENV PYTHONPATH=/app

# --- Execution ---
# Cloud Run uses the PORT env var, but EXPOSE is good practice.
EXPOSE 8080

# Run the A2A server when the container launches.
CMD ["python", "-m", "agents.social_profiling_agent.a2a_server"]
