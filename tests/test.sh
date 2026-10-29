#!/bin/bash
# Runs the verifier and writes the reward (1 = pass, 0 = fail).
pip install --quiet pytest==8.3.3
mkdir -p /logs/verifier
if pytest -q /tests/test_outputs.py -rA; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
