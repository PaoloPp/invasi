# Set base image (host OS)
FROM --platform=linux/amd64 python:3.12
#FROM python:3.12.7-alpine

# By default, listen on port 5000
EXPOSE 5000/tcp


COPY invasi-app app-invasi

WORKDIR /app-invasi

#RUN mkdir /app/templates
#RUN mkdir /app/templates/css
#RUN mkdir /app/templates/js
#RUN mkdir /app/static
#RUN mkdir elaborazioni
#RUN mkdir var
#RUN mkdir var/app-instance

# Copy the dependencies file to the working directory
#COPY requirements.txt .

# Install any dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the local src directory to the working directory
#COPY var/app-instance/invasi.db ./var/app-instance/invasi.db
#COPY app.py .
#COPY round_floats.py .
#COPY set_year.py .
#COPY templates/dashboard.html ./templates/
#COPY templates/form.html ./templates/

# Specify the command to run on container start
CMD [ "python", "./app.py" ]