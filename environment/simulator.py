"""
Semi-batch reactor simulator (nominal plant).

Reaction: A + B -> C (exothermic). B is fed into a jacketed reactor that
initially contains only A. The controller sees T, V and Tj every `dt`
seconds and returns a feed rate F and a jacket temperature command.

Usage:
    python3 simulator.py            # runs /app/controller.py on the nominal plant
"""
import importlib.util
import math
import sys

NOMINAL = dict(
    V0=50.0,          # initial volume [L]
    nA0=100.0,        # initial moles of A [mol]
    cB_in=5.0,        # B concentration in feed [mol/L]
    nB_target=105.0,  # total B to feed [mol]
    F_max=0.02,       # max feed rate [L/s]
    k_ref=0.01,       # rate constant at T_ref [L/(mol s)]
    T_ref=350.0,      # [K]
    EaR=10000.0,      # activation energy / R [K]
    dH=200.0,         # heat released per mol reacted [kJ/mol]
    rhocp=4.0,        # volumetric heat capacity [kJ/(L K)]
    UA=0.15,          # jacket heat-transfer coefficient [kW/K]
    T0=320.0,         # initial reactor temperature [K]
    T_in=300.0,       # feed temperature [K]
    Tj0=320.0,        # initial jacket temperature [K]
    Tj_min=290.0,     # jacket command limits [K]
    Tj_max=370.0,
    tau_j=60.0,       # jacket time constant [s]
    T_max=360.0,      # safety limit [K]
)

PUBLIC_KEYS = ["V0", "cB_in", "nB_target", "F_max", "T_max", "Tj_min", "Tj_max", "T0"]

DT_CONTROL = 10.0   # controller sample time [s]
H = 0.5             # integration step [s] (explicit Euler)
T_END = 10000.0     # max simulated time [s]
CONVERSION_TARGET = 0.95


def simulate(controller_cls, overrides=None, t_end=T_END):
    """Run one batch. `overrides` changes plant parameters (used for fault scenarios).

    Returns a dict with peak temperature, completion time (None if not completed)
    and final conversion of A.
    """
    p = dict(NOMINAL)
    p.update(overrides or {})

    public = {k: NOMINAL[k] for k in PUBLIC_KEYS}   # controller only sees nominal values
    public["dt"] = DT_CONTROL
    ctrl = controller_cls(public)

    V, nA, nB, T, Tj = p["V0"], p["nA0"], 0.0, p["T0"], p["Tj0"]
    fed, t, peak, done = 0.0, 0.0, T, None
    steps_per_sample = int(round(DT_CONTROL / H))

    while t < t_end - 1e-9:
        F, Tj_cmd = ctrl.step(t, T, V, Tj)
        F = min(max(float(F), 0.0), p["F_max"])
        Tj_cmd = min(max(float(Tj_cmd), p["Tj_min"]), p["Tj_max"])
        if not (math.isfinite(F) and math.isfinite(Tj_cmd)):
            raise ValueError("controller returned a non-finite value")

        for _ in range(steps_per_sample):
            Fe = F if fed < p["nB_target"] else 0.0
            k = p["k_ref"] * math.exp(-p["EaR"] * (1.0 / T - 1.0 / p["T_ref"]))
            r = k * (nA / V) * (nB / V) * V
            dT = (Fe / V) * (p["T_in"] - T) \
                + p["dH"] * r / (p["rhocp"] * V) \
                - p["UA"] * (T - Tj) / (p["rhocp"] * V)

            nA -= r * H
            nB += (Fe * p["cB_in"] - r) * H
            fed += Fe * p["cB_in"] * H
            V += Fe * H
            T += dT * H
            Tj += (Tj_cmd - Tj) / p["tau_j"] * H
            t += H
            peak = max(peak, T)

            if done is None and fed >= p["nB_target"] - 1e-9 \
                    and nA <= (1.0 - CONVERSION_TARGET) * p["nA0"]:
                done = t
        if done is not None:
            break

    return {"peak_T": peak, "time": done, "conversion": 1.0 - nA / p["nA0"]}


def load_controller(path="/app/controller.py"):
    spec = importlib.util.spec_from_file_location("controller", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Controller


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/app/controller.py"
    res = simulate(load_controller(path))
    print(f"peak T     : {res['peak_T']:.2f} K (limit {NOMINAL['T_max']} K)")
    print(f"batch time : {res['time']} s")
    print(f"conversion : {res['conversion']:.3f}")
