# Dockerfile used to create the bot container.

# Pin to python 3.9 since that's what I test with locally.
FROM python:3.9.13-bullseye

# All files go to app directory
WORKDIR /app

# Copy over python code
ADD python .

# For experiments that I want to run on GCB.
ADD integration_tests ./integration_tests

# Add in the user secrets
COPY users*.json ./

# Add in environment configurations
# TODO: do we need this? Can probably add consume contract / webhook to job.
COPY .env* ./

# Install python requirements
RUN pip3 install -r requirements.txt

# Print out contents to make it easier to debug
RUN find /app -ls