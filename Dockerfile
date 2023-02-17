FROM python:latest

WORKDIR /chatchat

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .

ENTRYPOINT ["hypercorn", "-b", "0.0.0.0:80", "app:asgi_app"]