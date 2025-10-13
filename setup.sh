#!/bin/bash

cd cnc

python -m alembic -x env=production upgrade head
python -m alembic -x env=testing upgrade head

cd ..