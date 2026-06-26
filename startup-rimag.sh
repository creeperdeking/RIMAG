#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl gnupg git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

usermod -aG docker ubuntu || true

mkdir -p /opt/rimag
mkdir -p /opt/openmc-data
mkdir -p /opt/rimag-results

cd /opt/rimag

if [ ! -d RIMAG ]; then
    git clone --branch "__BRANCH__" "__REPO__" RIMAG
fi

cd /opt/rimag/RIMAG

git fetch origin "__BRANCH__"
git checkout "__BRANCH__"
git pull origin "__BRANCH__"

gcloud storage rsync "__BUCKET__/openmc-data" /opt/openmc-data --recursive

cat > .env <<EOF
OPENMC_DATA_DIR=/opt/openmc-data
RIMAG_THREADS=24
EOF

docker compose build