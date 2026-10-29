# Safe, Time-Optimal Control of an Exothermic Semi-Batch Reactor

You are controlling a jacketed **semi-batch reactor** running the exothermic liquid-phase reaction

    A + B -> C        (heat of reaction: -200 kJ per mol of B reacted)

The reactor starts with reactant A only. Reactant B is fed in gradually. If B is fed faster than it reacts, unreacted B **accumulates**, and when it finally reacts it can release enough heat to push the temperature past the safety limit (thermal runaway). The cooling jacket has limited capacity, so feeding too fast is dangerous and feeding too slowly wastes time.

Write a controller that finishes the batch **as fast as possible without ever exceeding the safety temperature**.

## Process model (used by the simulator)

State: volume `V` [L], moles `nA`, `nB` [mol], reactor temperature `T` [K], jacket temperature `Tj` [K].

    k(T)   = k_ref * exp(-EaR * (1/T - 1/T_ref))
    r      = k(T) * (nA/V) * (nB/V) * V                         [mol/s]

    dV/dt  = F
    dnA/dt = -r
    dnB/dt = F * cB_in - r
    dT/dt  = (F/V) * (T_in - T) + (dH * r) / (rhocp * V) - UA * (T - Tj) / (rhocp * V)
    dTj/dt = (Tj_cmd - Tj) / tau_j

Nominal parameters:

| Parameter | Value | Meaning |
|---|---|---|
| `V0` | 50 L | initial volume |
| `nA0` | 100 mol | initial moles of A |
| `cB_in` | 5 mol/L | B concentration in feed |
| `nB_target` | 105 mol | total B to feed (5% excess) |
| `F_max` | 0.02 L/s | maximum feed rate |
| `k_ref` | 0.01 L/(mol·s) | rate constant at `T_ref` |
| `T_ref` | 350 K | reference temperature |
| `EaR` | 10000 K | activation energy / R |
| `dH` | 200 kJ/mol | heat released per mol reacted |
| `rhocp` | 4.0 kJ/(L·K) | volumetric heat capacity |
| `UA` | 0.15 kW/K | jacket heat-transfer coefficient |
| `T0` | 320 K | initial reactor temperature |
| `T_in` | 300 K | feed temperature |
| `Tj0` | 320 K | initial jacket temperature |
| `Tj_min`, `Tj_max` | 290 K, 370 K | jacket command limits |
| `tau_j` | 60 s | jacket time constant |
| `T_max` | **360 K** | **safety limit, must never be exceeded** |

## What the controller can see

The controller is sampled every **10 s** (zero-order hold). At each sample it receives only:

- `t` – time [s]
- `T` – reactor temperature [K]
- `V` – reactor volume [L]
- `Tj` – jacket temperature [K]

**Concentrations (`nA`, `nB`) and the reaction rate are not measured.**

## Required interface

Create the file **`/app/controller.py`** containing:

```python
class Controller:
    def __init__(self, params: dict):
        # params keys: V0, cB_in, nB_target, F_max, T_max, Tj_min, Tj_max, T0, dt
        ...

    def step(self, t: float, T: float, V: float, Tj: float) -> tuple[float, float]:
        # return (F, Tj_cmd): feed rate [L/s] and jacket temperature command [K]
        ...
```

- Outputs are clipped to `0 <= F <= F_max` and `Tj_min <= Tj_cmd <= Tj_max`.
- The simulator stops the feed automatically once `nB_target` mol of B has been fed.
- The controller must be **deterministic**: the same inputs in the same order must always give the same outputs. Do not use randomness, wall-clock time, files, or the network.
- The controller may only use the values passed to it. Imports are limited to `math`, `collections`, `dataclasses`, `typing`, `functools`, `itertools`, `statistics`, `bisect` and `heapq`. File access, introspection (`inspect`, `sys`, frame or `__globals__` access, `eval`/`exec`, `getattr`) and randomness are not allowed.
- A copy of the nominal simulator is available at `/app/simulator.py`. Run `python3 /app/simulator.py` to test your controller on the nominal plant.

## Scenarios

The controller is tested on the nominal plant **and on hidden fault scenarios** it is not told about. Faults can include, alone or combined:

- up to 30% loss of jacket heat transfer (`UA` fouling)
- up to 2x faster reaction kinetics (`k_ref`)
- feed temperature up to 15 K higher than nominal (`T_in`)
- up to 2.5x slower jacket response (`tau_j`)

The controller only ever receives the nominal `params`, so it must stay safe without knowing which fault is present.

## Success criteria (every scenario must pass)

1. **Safety:** reactor temperature stays at or below **360 K** at every moment of the simulation.
2. **Completion:** all `nB_target` mol of B is fed **and** conversion of A reaches **at least 95%**.
3. **Speed:** the batch completes within the time budget for that scenario. The budget is 125% of the time taken by a reference controller on the same scenario. For the nominal scenario the budget is **4675 s**.
4. **Determinism:** two runs on the same scenario give identical results.
