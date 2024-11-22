FROM google/cloud-sdk:501.0.0-slim

ARG tf_version=1.9.8-1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y gnupg=2.2.40-1.1 software-properties-common=0.99.30-4.1~deb12u1 wget=1.21.3-1+b2 gettext-base=0.21-12 --no-install-recommends \
  && wget -nv -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | tee /usr/share/keyrings/hashicorp-archive-keyring.gpg \
  && echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list \
  && apt-get update \
  && apt-get -y install terraform=${tf_version} --no-install-recommends \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/0.5.2/install.sh | sh

ENV PATH=$PATH:/root/.local/bin

ENTRYPOINT [ "/bin/bash" ]
