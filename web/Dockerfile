# initial setup
FROM python:3.6
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
    redis-tools \
    ruby-full \
    vim
RUN gem install papertrail

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ /code

CMD ["python", "server.py"]
