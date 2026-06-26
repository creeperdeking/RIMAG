FROM openmc/openmc:v0.15.3

ENV PYTHONUNBUFFERED=1
ENV RIMAG_WORKDIR=/work

WORKDIR /opt/rimag

COPY requirements-rimag.txt /opt/rimag/requirements-rimag.txt
RUN python -m pip install --no-cache-dir -r /opt/rimag/requirements-rimag.txt

COPY . /opt/rimag

COPY docker/entrypoint.sh /usr/local/bin/rimag-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/rimag-entrypoint && chmod +x /usr/local/bin/rimag-entrypoint

ENTRYPOINT ["rimag-entrypoint"]

CMD ["python", "start_sim.py", "Simulation data.ods", "7", "--run-mode", "keff"]