"""
guardrails.py — validity checks that run on every model evaluation.

Philosophy: the model never returns a number it cannot stand behind.
If an input or intermediate result violates a mathematical precondition
(an unstable queue, a probability outside [0, 1], throughput above demand),
the run stops with a precise explanation instead of silently returning
a wrong answer.

Every public model function calls these checks. The test suite additionally
asserts that the checks fire when they should (tests/test_guardrails.py).
"""

from __future__ import annotations


class ModelError(ValueError):
    """Raised when a model precondition or output invariant is violated."""


# ---------------------------------------------------------------- preconditions

def require_positive(name: str, value: float) -> None:
    if not (value > 0):
        raise ModelError(f"{name} must be > 0, got {value!r}")


def require_nonnegative(name: str, value: float) -> None:
    if not (value >= 0):
        raise ModelError(f"{name} must be >= 0, got {value!r}")


def require_stable(rho: float, station: str = "station") -> None:
    """A queue has a steady state only when utilization rho < 1.

    rho >= 1 means arrivals outstrip capacity: the queue grows without
    bound and every steady-state formula is invalid. This is the single
    most important guardrail in the model.
    """
    if not (0 <= rho < 1):
        raise ModelError(
            f"{station}: utilization rho = {rho:.4f} is not in [0, 1). "
            "The station cannot keep up with its arrivals; steady-state "
            "results do not exist. Add capacity or reduce load before "
            "asking the model anything else."
        )


# ---------------------------------------------------------------- output invariants

def check_probability(name: str, p: float, tol: float = 1e-9) -> float:
    """Probabilities must lie in [0, 1]. Values outside by more than
    floating-point tolerance indicate a bug, not noise."""
    if p < -tol or p > 1 + tol:
        raise ModelError(f"{name} = {p!r} is outside [0, 1]: internal error")
    return min(max(p, 0.0), 1.0)


def check_finite_nonnegative(name: str, value: float) -> float:
    import math
    if not math.isfinite(value) or value < 0:
        raise ModelError(f"{name} = {value!r} must be finite and >= 0")
    return value


def check_throughput(x: float, demand: float, capacity: float, tol: float = 1e-9) -> float:
    """Shipped orders can exceed neither customer demand nor bottleneck
    capacity (E5's definition of X). Anything else is an internal error."""
    if x > demand + tol:
        raise ModelError(f"throughput X = {x} exceeds demand {demand}")
    if x > capacity + tol:
        raise ModelError(f"throughput X = {x} exceeds bottleneck capacity {capacity}")
    return x
