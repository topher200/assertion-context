# initial setup
FROM python:3.6
WORKDIR /code
RUN echo 'set -o vi\nalias ll="ls -al"' >> /root/.bashrc
ENV PYTHONUNBUFFERED=1

# our company's standard time is Eastern. set the OS timezone to match so it
# sends it that way to Papertrail
ENV TZ=America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update && apt-get install -y \
  iputils-ping \
  less \
  redis-tools \
  ruby-full \
  vim

# install papertrail daemon
RUN wget https://github.com/papertrail/remote_syslog2/releases/download/v0.20/remote_syslog_linux_i386.tar.gz -O ./remote_syslog.tar.gz
RUN tar xzf ./remote_syslog.tar.gz
RUN ls
RUN cp ./remote_syslog/remote_syslog /usr/local/bin

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src /code
COPY src/badcorp/papertrail_log_files.yml /etc/log_files.yml

# the 15 second sleep is required to ensure that the logs are saved to
# Papertrail before the container exits. this value was determined through
# emperical testing
CMD ["sh", "-c", "remote_syslog && sleep 2 && python run_badcorp.py && sleep 15"]
