FROM python:3.10

RUN /bin/cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' >/etc/timezone

RUN apt-get update -y && apt-get install -y cmake build-essential libgl1-mesa-glx libopenblas-dev liblapack-dev || \
    (apt-get update -y && apt-get install -y cmake build-essential libgl1-mesa-dev libopenblas-dev liblapack-dev)

ENV PYTHONUNBUFFERED=TRUE

RUN mkdir -p /app
ADD . /app/
WORKDIR /app

RUN pip install --upgrade pip && pip install -r requirements.txt

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:17001", "app:app"]

EXPOSE 17001