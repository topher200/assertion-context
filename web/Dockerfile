# initial setup
FROM ubuntu:16.04
MAINTAINER Topher <topher200@gmail.com>
WORKDIR /code
RUN echo 'set -o vi' >> /root/.bashrc
ENV PYTHONUNBUFFERED=1

# install dependencies
RUN apt-get update && apt-get install -y \
    python3-pip
RUN pip3 install --upgrade pip
ADD requirements.txt ./
RUN pip3 install -r requirements.txt

# setup aws creds
COPY .aws_credentials /root/.aws/credentials
COPY .aws_config /root/.aws/config

# web app code is added by docker-compose volume

CMD ["gunicorn", "--workers", "2", "--bind", ":8000", "server:flask_app"]
# CMD ["python3", "server.py"]
