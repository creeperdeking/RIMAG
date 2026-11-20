FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV RIMAG_WORKDIR=/work
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV PATH=/opt/venv/bin:/usr/local/bin:${PATH}

# OpenMC 0.16.0 with periodic z-cones, from
# https://github.com/creeperdeking/openmc (branch periodic-zcone).
# The web-app geometry uses those cones when conical_pitch is not zero.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python-is-python3 \
        git build-essential cmake ca-certificates \
        libhdf5-dev libpng-dev libpugixml-dev libfmt-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
    && pip install --upgrade pip setuptools wheel

WORKDIR /opt/openmc
RUN git clone --depth 1 --branch periodic-zcone https://github.com/creeperdeking/openmc.git . \
    && git fetch --depth 1 origin tag v0.16.0

# Land periodic z-cone jumps slightly inside the arrival halfspace so
# cell search does not lose the particle (weight-window splits hit this).
COPY docker/openmc-zcone-landing-nudge.patch /tmp/openmc-zcone-landing-nudge.patch
RUN git apply /tmp/openmc-zcone-landing-nudge.patch

RUN mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release -DOPENMC_USE_MPI=OFF -DOPENMC_BUILD_TESTS=OFF \
             -DCMAKE_INSTALL_PREFIX=/usr/local .. \
    && make -j"$(nproc)" \
    && make install

RUN pip install --no-cache-dir /opt/openmc

WORKDIR /opt/rimag

COPY requirements-rimag.txt /opt/rimag/requirements-rimag.txt
RUN python -m pip install --no-cache-dir -r /opt/rimag/requirements-rimag.txt

COPY . /opt/rimag

COPY docker/entrypoint.sh /usr/local/bin/rimag-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/rimag-entrypoint && chmod +x /usr/local/bin/rimag-entrypoint

ENTRYPOINT ["rimag-entrypoint"]

CMD ["python", "start_sim.py", "Simulation data.ods", "7", "--run-mode", "keff"]
