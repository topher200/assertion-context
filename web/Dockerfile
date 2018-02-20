# initial setup
FROM ubuntu:16.04
MAINTAINER Topher <topher200@gmail.com>
WORKDIR /code
RUN echo 'set -o vi' >> /root/.bashrc
ENV PYTHONUNBUFFERED=1

# install dependencies
RUN apt-get update && apt-get install -y \
    iputils-ping \
    less \
    python3-pip \
    redis-tools \
    vim
RUN pip3 install --upgrade pip
ADD requirements.txt ./
RUN pip3 install -r requirements.txt

COPY ./ /code

CMD ["python3", "server.py"]
