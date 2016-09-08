# initial setup
FROM ubuntu:16.04
MAINTAINER Topher <topher200@gmail.com>
WORKDIR /root
RUN echo 'set -o vi' >> .bashrc

# install dependencies
RUN apt-get update && apt-get install -y \
    python-pip
RUN pip install --upgrade pip
ADD requirements.txt ./
RUN pip install -r requirements.txt

# setup app environment
ADD .aws_credentials .aws/credentials
ADD .aws_config .aws/config
ADD app app

CMD ["python", "app/server.py"]
