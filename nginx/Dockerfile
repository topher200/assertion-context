# initial setup
FROM nginx:1.11.3
MAINTAINER Topher <topher200@gmail.com>
WORKDIR /code
RUN echo 'set -o vi' >> /root/.bashrc
ENV PYTHONUNBUFFERED=1

# clean up existing nginx config
RUN rm /etc/nginx/nginx.conf
RUN rm /etc/nginx/conf.d/default.conf

# add our files
COPY nginx.conf /etc/nginx
COPY tracebacks_app.conf /etc/nginx/conf.d

COPY ../web/static /www/static
