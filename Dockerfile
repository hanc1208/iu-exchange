FROM python:3.7

LABEL maintainer="hanc1208@gmaill.com"
ENV LANG=C.UTF-8

COPY requirements.txt /tmp/

RUN pip install -r /tmp/requirements.txt

RUN mkdir /app
WORKDIR /app
COPY . /app

ENV IU_EXCHANGE_CONFIG=prod.toml
EXPOSE 8516
CMD ./run.py -p 8516 $IU_EXCHANGE_CONFIG
