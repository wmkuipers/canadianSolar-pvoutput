FROM python:3.7.10-slim-stretch
LABEL maintainer="Willem Kuipers <willem@kuipers.co.uk>"

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip=9.0.1-2+deb9u2 && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir pip==21.1.3 && \
    pip install --no-cache-dir pipenv==2021.5.29


WORKDIR /inverter-pvoutput
COPY ["resources/*", "./"]

RUN pipenv install --system --ignore-pipfile
CMD ["/inverter-pvoutput/startup.sh"]