ARG IMAGE_SOURCE

FROM ${IMAGE_SOURCE}continuumio/miniconda3:4.10.3p1

LABEL maintainer="OBS2CO"
USER root

# Montage du volume temporaire et utilisation pour yum le site du cnes
# Il faut utiliser le secret dans le même run que le montage sinon cela ne fonctionnera pas
RUN --mount=type=secret,id=proxy_http_cnes \ 
    export http_proxy=$(cat /run/secrets/proxy_http_cnes) && export https_proxy=$(cat /run/secrets/proxy_https_cnes) && \
    apt-get update && \
    apt-get install -y ca-certificates

#Ajout des certificats
COPY certs/* /usr/local/share/ca-certificates/
RUN ls /usr/local/share/ca-certificates/ &&\ 
    update-ca-certificates

RUN mkdir -p /app/sisppeo

COPY . /app/sisppeo

RUN --mount=type=secret,id=arti_conda_repo \
    CONDA_SSL_VERIFY=/etc/ssl/certs/ca-certificates.crt conda install --override-channels -c $(cat /run/secrets/arti_conda_repo) sisppeo

WORKDIR /app/sisppeo

#Install last version

RUN PIP_CERT=/etc/ssl/certs/ca-certificates.crt pip uninstall -y sisppeo

RUN cd /app/sisppeo && /opt/conda/bin/python setup.py build && /opt/conda/bin/python setup.py install
RUN ls -l /app/sisppeo
RUN ls -l /app/sisppeo/build/lib

RUN sisppeo --version

#To be launched
#ENTRYPOINT ["python", "/app/sisppeo/launcher.py", "/app/sisppeo/config.yml"]
