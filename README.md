# Semi-Batch Reactor Safety Control

A Terminal-Bench-style benchmark task in chemical process control. The agent has to write a controller that finishes an exothermic semi-batch reaction as fast as possible **without ever exceeding the reactor's safety temperature**, even under faults it is not told about.

## The problem

Reactant A is in a jacketed reactor. Reactant B is fed in gradually, and the reaction `A + B -> C` releases heat.

- Feed B **too fast** and unreacted B accumulates. When it reacts all at once, the temperature runs away past the 360 K limit.
- Feed B **too slowly** and the batch is safe but takes far too long.

The controller is sampled every 10 s and only sees reactor temperature, volume and jacket temperature. **Concentrations and reaction rate are not measured.** It returns a feed rate and a jacket temperature command.

## What makes it hard

- **Partial observability:** the controller has to infer how much unreacted B is in the reactor from temperature behaviour alone.
- **Hidden faults:** the verifier runs the controller on the nominal plant and on 7 unseen fault scenarios (jacket fouling, faster kinetics, hot feed, slow jacket and combinations). The controller only ever receives nominal parameters.
- **Safety and speed together:** every scenario must stay at or below 360 K at every integration step, reach 95% conversion, and finish within 125% of a reference controller's batch time.

## Repository layout

```
instruction.md            Full task statement given to the agent
environment/
  Dockerfile              Python 3.11 environment
  simulator.py            Nominal plant simulator the agent can use for testing
tests/
  test.sh                 Runs the verifier and writes the reward (1 = pass, 0 = fail)
  test_outputs.py         pytest verifier: 8 scenarios, safety, budget, determinism, code checks
  reactor_sim.py          Verifier's own copy of the simulator
solution/
  solve.sh                Reference solution: writes a working /app/controller.py
```

## Verifier design

The tests are built so that a controller can only pass by actually solving the control problem:

- **Hidden scenarios live only in `tests/`.** The agent's environment contains just the nominal simulator, so fault values cannot be read or tuned against.
- **The verifier uses its own simulator copy.** Editing `/app/simulator.py` has no effect on grading.
- **Peak temperature is checked at every 0.5 s integration step**, not only at the 10 s samples, so a controller cannot briefly cross the limit between samples.
- **Static code checks** reject introspection (`inspect`, `sys`, frame or `__globals__` access, `eval`/`exec`), file access and randomness, so the controller cannot reach into the simulator to read hidden state.
- **Determinism** is checked by running the worst-case scenario twice.

## Validation

| Controller | Result |
|---|---|
| Reference solution | 11/11 tests pass (nominal peak 357.96 K, batch time 3740 s) |
| Does nothing | Fails (batch never completes) |
| Full feed without control | Fails (exceeds 360 K) |
| Very slow constant feed | Fails (over time budget) |
| Uses `inspect` to cheat | Fails (static code check) |

## Running it

Run these from the repository root with Docker running.

**Build the environment**

```bash
docker build -t reactor-env environment
```

**Oracle check (reference solution should pass, reward 1)**

Linux / macOS:
```bash
docker run --rm -v "$PWD/tests:/tests" -v "$PWD/solution:/solution" reactor-env \
  bash -c "bash /solution/solve.sh && bash /tests/test.sh; cat /logs/verifier/reward.txt"
```

Windows (Command Prompt):
```bat
docker run --rm -v "%cd%\tests:/tests" -v "%cd%\solution:/solution" reactor-env bash -c "bash /solution/solve.sh && bash /tests/test.sh; cat /logs/verifier/reward.txt"
```

**Null check (no controller should fail, reward 0)**

Linux / macOS:
```bash
docker run --rm -v "$PWD/tests:/tests" reactor-env \
  bash -c "bash /tests/test.sh; cat /logs/verifier/reward.txt"
```

Windows (Command Prompt):
```bat
docker run --rm -v "%cd%\tests:/tests" reactor-env bash -c "bash /tests/test.sh; cat /logs/verifier/reward.txt"
```

The last line prints the reward: `1` if all tests pass, `0` otherwise.

## Author

Imran Khan · M.Tech CSE, IIT Bombay · [LinkedIn](https://www.linkedin.com/in/imran-khan-83a947156/)
