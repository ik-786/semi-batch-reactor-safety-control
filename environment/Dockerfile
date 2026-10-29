# Environment for the semi-batch reactor control task.
# The agent writes /app/controller.py; /app/simulator.py lets it test on the nominal plant.
FROM python:3.11-slim

WORKDIR /app

# Nominal simulator only. Hidden fault scenarios live in the tests, not here.
COPY simulator.py /app/simulator.py

CMD ["bash"]
