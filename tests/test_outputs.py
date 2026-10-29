"""
Verifier for the semi-batch reactor control task.

Runs /app/controller.py on the nominal plant and on hidden fault scenarios,
using the tests' own copy of the simulator (the agent cannot modify it).
"""
import ast
import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from reactor_sim import NOMINAL, simulate  # noqa: E402

CONTROLLER_PATH = "/app/controller.py"

# Hidden scenarios: plant overrides and time budget [s].
# Budget = 1.25 x the reference controller's batch time on that scenario.
SCENARIOS = {
    "nominal":       ({}, 4675),
    "fouling":       ({"UA": 0.105}, 5162),
    "fast_kinetics": ({"k_ref": 0.02}, 4275),
    "hot_feed":      ({"T_in": 315.0}, 4250),
    "slow_jacket":   ({"tau_j": 150.0}, 5075),
    "fouling_fast":  ({"UA": 0.11, "k_ref": 0.018, "tau_j": 120.0}, 5238),
    "hot_slow":      ({"T_in": 312.0, "tau_j": 140.0, "UA": 0.12}, 5288),
    "worst_case":    ({"UA": 0.105, "k_ref": 0.02, "T_in": 315.0, "tau_j": 150.0}, 5625),
}

ALLOWED_IMPORTS = {"math", "collections", "dataclasses", "typing",
                   "functools", "itertools", "statistics", "bisect", "heapq"}
FORBIDDEN_NAMES = {"__import__", "eval", "exec", "compile", "open", "globals",
                   "locals", "vars", "getattr", "setattr", "breakpoint", "input"}
FORBIDDEN_ATTRS = {"f_back", "f_locals", "f_globals", "gi_frame", "tb_frame",
                   "__globals__", "__code__", "__subclasses__", "__builtins__"}


def load_controller():
    spec = importlib.util.spec_from_file_location("agent_controller", CONTROLLER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Controller


@pytest.fixture(scope="module")
def Controller():
    assert os.path.isfile(CONTROLLER_PATH), "/app/controller.py not found"
    return load_controller()


def test_controller_is_pure_python():
    """No introspection, I/O or randomness: the controller may only use its inputs."""
    tree = ast.parse(open(CONTROLLER_PATH).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] in ALLOWED_IMPORTS, f"import not allowed: {a.name}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in ALLOWED_IMPORTS, \
                f"import not allowed: {node.module}"
        elif isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_NAMES, f"use of '{node.id}' not allowed"
        elif isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_ATTRS, f"access to '{node.attr}' not allowed"


def test_interface(Controller):
    params = {k: NOMINAL[k] for k in
              ["V0", "cB_in", "nB_target", "F_max", "T_max", "Tj_min", "Tj_max", "T0"]}
    params["dt"] = 10.0
    out = Controller(params).step(0.0, NOMINAL["T0"], NOMINAL["V0"], NOMINAL["Tj0"])
    assert isinstance(out, tuple) and len(out) == 2, "step() must return (F, Tj_cmd)"
    assert all(isinstance(x, (int, float)) for x in out)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_scenario(Controller, name):
    overrides, budget = SCENARIOS[name]
    res = simulate(Controller, overrides)
    assert res["peak_T"] <= NOMINAL["T_max"], \
        f"{name}: safety limit exceeded, peak T = {res['peak_T']:.2f} K"
    assert res["time"] is not None, \
        f"{name}: batch not completed (conversion {res['conversion']:.3f})"
    assert res["time"] <= budget, \
        f"{name}: too slow, {res['time']:.0f} s > budget {budget} s"


def test_deterministic(Controller):
    overrides, _ = SCENARIOS["worst_case"]
    assert simulate(Controller, overrides) == simulate(Controller, overrides), \
        "controller is not deterministic"
