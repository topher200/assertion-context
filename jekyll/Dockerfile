# initial setup
# adapted from https://hub.docker.com/r/grahamc/jekyll/~/dockerfile/
FROM ruby:2.1
MAINTAINER Topher <topher200@gmail.com>
WORKDIR /code
RUN echo 'set -o vi' >> /root/.bashrc
ENV PYTHONUNBUFFERED=1

# install ruby and gems
RUN apt-get update \
  && apt-get install -y \
    node \
    python-pygments \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/
RUN gem install \
  github-pages \
  jekyll \
  jekyll-redirect-from \
  kramdown \
  pygments.rb \
  rdiscount \
  rouge

# bring down our base jekyll repo
COPY ./ /srv/jekyll

# point the _posts dir to our loaded posts volume
WORKDIR /srv/jekyll
RUN rm -r _posts
RUN ln -s /srv/posts _posts

CMD ["jekyll", "serve", "-H", "0.0.0.0"]
