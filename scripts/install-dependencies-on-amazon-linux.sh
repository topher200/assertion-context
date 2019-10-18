#!/bin/bash

# installs the dependencies necessary to run docker-compose from a fresh Amazon
# Linux box. use this to create a fresh AMI

# install docker (https://docs.aws.amazon.com/AmazonECS/latest/developerguide/docker-basics.html#install_docker)
sudo amazon-linux-extras install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user
sudo systemctl enable docker

# install docker-compose (https://docs.docker.com/compose/install/)
sudo curl -L "https://github.com/docker/compose/releases/download/1.24.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# install dynaconf, for configuration handling
sudo yum install -y python3
sudo pip3 install dynaconf
