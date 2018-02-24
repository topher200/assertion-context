# initial setup
FROM ubuntu:17.10
MAINTAINER Topher <topher200@gmail.com>
WORKDIR /code
RUN echo 'set -o vi' >> /root/.bashrc
ENV PYTHONUNBUFFERED=1

# set my timezone to eastern, so we send our company's standard time to papertrail
ENV TZ=America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


# install dependencies
RUN apt-get update && apt-get install -y \
    iputils-ping \
    less \
    python3.6 \
    python3-pip \
    redis-tools \
    vim
RUN pip3 install --upgrade pip
ADD requirements.txt ./
RUN python3.6 -m pip3 install -r requirements.txt

COPY ./ /code

CMD ["python3.6", "server.py"]
