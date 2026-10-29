#!/bin/bash
# Reference solution: writes a working controller to /app/controller.py
cat > /app/controller.py <<'PY'
"""
Reference controller for the exothermic semi-batch reactor.

Idea: keep the reactor hot enough that B reacts almost as soon as it is fed
(so little unreacted B can accumulate), and only feed as fast as the jacket
still has cooling headroom to remove the heat.

1. Jacket: PI + derivative control holds T at a setpoint 6 K below the limit.
2. Heat-up: the jacket heats the reactor. A small, capped pre-feed starts at
   330 K so the reaction helps with heating without building up dangerous
   amounts of unreacted B.
3. Feeding: feed rate is proportional to cooling headroom (how far the jacket
   command is above its minimum). Less headroom -> less feed. This adapts
   automatically to fouling, faster kinetics or a hot feed, without knowing them.
4. Safety cut-offs: stop feeding if T gets within 4 K of the limit or is rising
   fast.
5. End of batch: as A runs out, B reacts more slowly, so the feed is throttled
   to avoid accumulation near the end.
"""


class Controller:
    SETPOINT_MARGIN = 6.0     # K below T_max
    CUTOFF_MARGIN = 4.0       # stop feeding this close to T_max [K]
    MAX_RISE_RATE = 0.06      # stop feeding if T rises faster than this [K/s]
    PREFEED_START_T = 330.0   # start small pre-feed during heat-up [K]
    PREFEED_CAP = 15.0        # max mol of B fed before reaching setpoint
    KP, KI, KD = 4.0, 0.05, 60.0

    def __init__(self, params):
        self.p = params
        self.T_sp = params["T_max"] - self.SETPOINT_MARGIN
        self.nA_est = params["nB_target"] / 1.05   # B target is 5% excess over A
        self.integral = 0.0
        self.fed = 0.0          # mol of B fed so far (we know what we commanded)
        self.prev_T = None
        self.at_temperature = False

    def _feed_for_moles(self, moles):
        """Feed rate that delivers `moles` of B in one sample period."""
        return moles / (self.p["cB_in"] * self.p["dt"])

    def step(self, t, T, V, Tj):
        p, dt = self.p, self.p["dt"]
        dTdt = 0.0 if self.prev_T is None else (T - self.prev_T) / dt
        self.prev_T = T

        # 1. Jacket temperature: PI + D on reactor temperature, with anti-windup
        err = self.T_sp - T
        u = self.T_sp + self.KP * err + self.integral - self.KD * dTdt
        if p["Tj_min"] < u < p["Tj_max"]:
            self.integral += self.KI * err * dt
        Tj_cmd = max(p["Tj_min"], min(p["Tj_max"], u))

        if T >= self.T_sp - 3.0:
            self.at_temperature = True

        # 2. Heat-up phase: small capped pre-feed
        if not self.at_temperature:
            F = 0.0
            if T >= self.PREFEED_START_T and self.fed < self.PREFEED_CAP:
                F = min(p["F_max"], self._feed_for_moles(self.PREFEED_CAP - self.fed))
            self.fed += F * p["cB_in"] * dt
            return F, Tj_cmd

        # 3. Feed in proportion to remaining cooling headroom
        headroom = max(0.0, min(1.0, (Tj_cmd - p["Tj_min"] - 5.0) / 15.0))

        # 5. Throttle near the end of the batch (little A left -> slower reaction)
        late = max(0.15, min(1.0, (self.nA_est - self.fed) / 30.0))

        F = p["F_max"] * headroom * late

        # 4. Safety cut-offs
        if T > p["T_max"] - self.CUTOFF_MARGIN or dTdt > self.MAX_RISE_RATE:
            F = 0.0

        F = min(F, self._feed_for_moles(p["nB_target"] - self.fed))
        self.fed += F * p["cB_in"] * dt
        return F, Tj_cmd
PY
