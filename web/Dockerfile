# initial setup
FROM ubuntu:16.04
MAINTAINER Topher <topher200@gmail.com>
WORKDIR /code
RUN echo 'set -o vi' >> /root/.bashrc
ENV PYTHONUNBUFFERED=1

# install dependencies
RUN apt-get update && apt-get install -y \
    python-pip
RUN pip install --upgrade pip
ADD requirements.txt ./
RUN pip install -r requirements.txt

# setup app environment
ADD .aws_credentials /root/.aws/credentials
ADD .aws_config /root/.aws/config
ADD app app

CMD ["python", "-m", "app.server"]
