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
    ruby-full \
    vim
RUN pip3 install --upgrade pip
ADD ../requirements.txt ./
RUN pip3 install -r requirements.txt

RUN gem install papertrail

# web app code is added by docker-compose volume

CMD ["python3", "realtime_updater/run.py"]

