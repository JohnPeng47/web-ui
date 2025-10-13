#!/bin/bash

cd cnc

python -m alembic -x env=production upgrade head
python -m alembic -x env=testing upgrade head

echo "Installing mitmproxy CA certificate for MITMProxy ..."
python -m scripts.install_ca_cert

cd ..