# initial setup
FROM ubuntu:17.04
MAINTAINER Topher <topher200@gmail.com>
WORKDIR /code
RUN echo 'set -o vi' >> /root/.bashrc
ENV PYTHONUNBUFFERED=1

# install dependencies
RUN apt-get update && apt-get install -y \
    cron \
    iputils-ping \
    less \
    python3.6 \
    python3-pip \
    ruby-full \
    vim

# set my timezone to eastern, so we send our company's standard time to papertrail
ENV TZ=America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN gem install papertrail
RUN pip3 install --upgrade pip
ADD requirements.txt ./
RUN python3.6 -m pip install -r requirements.txt

ADD .papertrail.yml /root/

## setup cron
# Add crontab file in the cron directory
ADD crontab /etc/cron.d/run-updater
# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/run-updater

# web app code is added by docker-compose volume

CMD ["cron", "-f"]
