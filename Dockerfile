# Dockerfile for Yandex Transport Monitor
# Architectures: armhf (Orange PI, Raspberry PI)
#                x86-64

# Use Ubuntu 18.04 as basis
FROM ubuntu:18.04

# ----- CHANGE THESE ARGUMENTS TO YOUR DESIRES ----- #
# -- ИЗМЕНИТЕ ДАННЫЕ АРГУМЕНТЫ ДЛЯ ВАШЕЙ СИТУАЦИИ -- #
# TimeZone / Часовой Пояс
ARG timezone=Europe/Moscow

# -------------------------------------------------- #

# Setting frontend to non-interactive, no questions asked, ESPECIALLY for locales.
ENV DEBIAN_FRONTEND=noninteractive

# Install all required software, right way.
# We're using all latest package versions here. Risky.
RUN apt-get update && \
    apt-get install -y \
    locales \
    tzdata \
    # Install python3
    python3 \
    # Install python3-pip
    python3-pip

# Install required python packages
RUN pip3 install psycopg2-binary \
                 python-telegram-bot

# Dealing with goddamn locales
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# Setting the goddamn TimeZone
ENV TZ=${timezone}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Cleaning
RUN apt-get clean

# Creating the user
RUN mkdir -p /home/sender_bot
RUN useradd sender_bot --home /home/sender_bot --shell /bin/bash

# Copying the project
ADD sender_bot.py /home/sender_bot

# Setting permissions
RUN chown -R sender_bot:sender_bot /home/sender_bot
WORKDIR /home/sender_bot

# Setting up entry point for this container, it's designed to run as an executable.
# ENTRYPOINT HERE
USER sender_bot:sender_bot

# No entry point, you need to provide CLI parameters to the sender bot anyway.
