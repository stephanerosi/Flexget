FROM circleci/python:3.6

# Install extra repos
RUN sudo sed -i 's/debian jessie main$/debian jessie main contrib non-free/' /etc/apt/sources.list

# Install unrar used by some flexget tests
RUN sudo apt-get update; sudo apt-get install -qy unrar

# Use virtualenv as we test on py2.7, keeps it consistant
RUN sudo pip install virtualenv
