#!/bin/bash
set -ex

cd /home/richkingsasu/TVCB-PROD/src/webhook-handler

rm -rf venv
python3 -m venv venv
. venv/bin/activate

pip install -r requirements.txt

export PROJECT_ID=tvcb-prod
export TV_SECRET=tnO0jwQ+6orwTPSwgVcYL0Q7OTQuxnrrhfaj72GqVSdRFHY0tp+gVcuJZ2d+8Catg4iO/z6k1XmRUtfjX9Hybw==

python -m gunicorn -w 2 -b 0.0.0.0:8080 main:app