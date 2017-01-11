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
# RUN curl https://raw.githubusercontent.com/rubygems/rubygems/master/lib/rubygems/ssl_certs/index.rubygems.org/GlobalSignRootCA.pem > $(ruby -ropenssl -e 'puts OpenSSL::X509::DEFAULT_CERT_FILE')
# RUN curl --insecure -O https://rubygems.org/downloads/rubygems-update-2.6.7.gem
# RUN gem install --local ./rubygems-update-2.6.7.gem
# RUN update_rubygems --no-ri --no-rdoc
# RUN gem uninstall rubygems-update -x
RUN gem install \
  github-pages \
  jekyll \
  jekyll-redirect-from \
  kramdown \
  rdiscount \
  rouge

# # bring down our base jekyll repo
# # COPY ./ /srv/jekyll

# # # point the _posts dir to our loaded posts volume
# # WORKDIR /srv/jekyll
# # RUN rm -r _posts
# # RUN ln -s /srv/posts _posts

# CMD ['jekyll', 'serve', '-H', '0.0.0.0']
