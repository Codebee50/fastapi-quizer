# pull official base image
FROM python:3.11-slim

# Install system dependencies for ocrmypdf
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    ghostscript \
    qpdf \
    libjpeg-dev \
    zlib1g-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# set work directory
WORKDIR /usr/src/app

RUN mkdir -p /usr/src/app/logs

ENV PYTHONPATH=/usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# copy project
COPY . .
CMD [ "honcho", "start" ]
