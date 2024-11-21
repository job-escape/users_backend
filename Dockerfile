FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y git && apt-get clean

WORKDIR /users_main

COPY requirements.txt /users_main/
RUN pip install --no-cache -r requirements.txt

COPY . /users_main/

CMD ["sh", "-c", "python manage.py migrate && gunicorn --workers=2 --threads=4 --bind 0.0.0.0:$PORT users_main.wsgi:application"]