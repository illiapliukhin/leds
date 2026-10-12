"""Cable physics: all cables are verlet ropes simulated together in one numpy array (PBD distance
constraints, Jacobi, stretch-only so slack cables sag). The wall is vertical, so 'gravity' is +y on screen.
Cables are pinned to the real connector positions; over-stretch is reported so the cable can unplug."""
import numpy as np

SEG = 14
G = np.array([0.0, 2500.0])           # mm/s^2 (reduced: the cables also lie against the boards)

class Ropes:
    def __init__(s):
        s.keys = []; s.P = np.zeros((0, SEG + 1, 2)); s.Q = s.P.copy(); s.L = np.zeros(0)
    def sync(s, specs):
        """specs: {key: (A(xy), B(xy) or None if the far end is free, length_mm)}"""
        keys = list(specs)
        if keys != s.keys:
            old = {k: (s.P[i], s.Q[i]) for i, k in enumerate(s.keys)}
            P = np.zeros((len(keys), SEG + 1, 2)); Q = P.copy()
            for i, k in enumerate(keys):
                if k in old: P[i], Q[i] = old[k]
                else:
                    A, B, L = specs[k]; B = B if B is not None else (A[0], A[1] + L * 0.8)
                    t = np.linspace(0, 1, SEG + 1)[:, None]
                    P[i] = np.array(A) * (1 - t) + np.array(B) * t; Q[i] = P[i]
            s.keys, s.P, s.Q = keys, P, Q
        n = len(keys)
        s.A = np.array([specs[k][0] for k in keys], float).reshape(n, 2)
        s.Bfix = np.array([specs[k][1] is not None for k in keys], bool)
        s.B = np.array([specs[k][1] if specs[k][1] is not None else (0, 0) for k in keys], float).reshape(n, 2)
        s.L = np.array([specs[k][2] for k in keys], float)
        # bending stiffness: FFC = semi-stiff ribbon, JST/power wires = soft but well damped
        s.K = np.array([0.45 if str(k[0]) in 'fF' else 0.12 for k in keys], float)
    def step(s, dt, iters=16):
        if not len(s.keys): return
        h = min(dt, 1 / 30); sub = 2
        for _ in range(sub):
            hs = h / sub
            # heavy damping: velocity retained per substep ~0.72 -> settles in ~0.3 s; sleep threshold kills residual sway
            dmp = np.where(s.Bfix, 0.6, 0.8)[:, None, None]         # a free (unplugged) end drops quickly, then stops
            V = (s.P - s.Q) * dmp
            V[np.abs(V).max(axis=(1, 2)) < 0.05] = 0
            s.Q = s.P.copy(); s.P = s.P + V + G * hs * hs * np.where(s.Bfix, 1.0, 4.0)[:, None, None]
            rest = (s.L / SEG)[:, None]
            for _ in range(iters):
                s.P[:, 0] = s.A; s.P[s.Bfix, -1] = s.B[s.Bfix]
                d = s.P[:, 1:] - s.P[:, :-1]
                ln = np.sqrt((d * d).sum(-1)) + 1e-9
                c = np.maximum(ln - rest, 0) / ln * 0.5                 # stretch-only (ropes go slack)
                corr = d * c[..., None]
                s.P[:, :-1] += corr; s.P[:, 1:] -= corr
                mid = 0.5 * (s.P[:, :-2] + s.P[:, 2:])                     # bending: pull toward neighbours' midpoint
                s.P[:, 1:-1] += (mid - s.P[:, 1:-1]) * (s.K[:, None, None] * 0.25)
            s.P[:, 0] = s.A; s.P[s.Bfix, -1] = s.B[s.Bfix]
    def tension(s):
        """end-to-end distance / cable length (>1 = stretched beyond its length)"""
        if not len(s.keys): return np.zeros(0)
        d = np.where(s.Bfix, np.linalg.norm(s.B - s.A, axis=1), 0)
        return d / np.maximum(s.L, 1e-6)
    def pts(s, i): return s.P[i]
