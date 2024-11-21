FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y git && apt-get clean

WORKDIR /users

COPY requirements.txt /users/
RUN pip install --no-cache -r requirements.txt

COPY . /users/

CMD ["sh", "-c", "python manage.py migrate && gunicorn --workers=2 --threads=4 --bind 0.0.0.0:$PORT academy.wsgi:application"]