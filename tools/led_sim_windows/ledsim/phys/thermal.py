"""Finite-difference thermal model of the board: 2-D grid (dx) over the real outline, in-plane conductance
from the copper density of each layer rasterised from the .kicad_pcb (zones + tracks + pads), FR-4 between,
convection + linearised radiation on both faces, explicit integration with the CFL-stable step
dt <= 0.2·dx²·C/k_max. Part junctions sit on their cell through ΨJB (or θJB) and get their power from the
electrical solution."""
import gzip, json, math
import numpy as np
import pygame

K_CU, K_FR4 = 385.0, 0.30                   # W/m·K
RC_FR4, RC_CU = 1.85e6, 3.45e6              # volumetric heat capacity J/m³K
H_CONV, EPS = 7.0, 0.90                     # natural convection per face (assumption: still air, vertical wall), emissivity
SIGMA = 5.670e-8
THICK = 1.6e-3
T_LAYERS = [35e-6, 17.5e-6, 17.5e-6, 35e-6]

def copper_density(pcb, x0, y0, nx, ny, dx_mm, sub=4):
    """fraction of copper per cell for each of the 4 layers (rasterised at dx/sub)."""
    W, H = nx * sub, ny * sub; sc = sub / dx_mm
    out = np.zeros((4, ny, nx))
    for L in range(4):
        s = pygame.Surface((W, H)); s.fill((0, 0, 0))
        P = lambda x, y: ((x - x0) * sc, (y - y0) * sc)
        for z in pcb['zones']:
            if z[0] == L and len(z[2]) >= 6:
                pygame.draw.polygon(s, (255, 255, 255), [P(z[2][k], z[2][k + 1]) for k in range(0, len(z[2]), 2)])
        for t in pcb['tracks']:
            if t[0] != L: continue
            Q = t[3]; w = max(1, int(round(t[1] * sc)))
            pygame.draw.lines(s, (255, 255, 255), False, [P(Q[k], Q[k + 1]) for k in range(0, len(Q), 2)], w)
        for p in pcb['pads']:
            if (p[8] >> L) & 1:
                cx, cy = P(p[2], p[3]); w, h = p[4] * sc, p[5] * sc
                pygame.draw.rect(s, (255, 255, 255), (cx - w / 2, cy - h / 2, max(1, w), max(1, h)))
        a = pygame.surfarray.array_red(s).T.astype(np.float32) / 255
        out[L] = a.reshape(ny, sub, nx, sub).mean((1, 3))
    return out

class BoardThermal:
    def __init__(s, pcb, dx_mm=2.5):
        xs = [q[0] for sg in pcb['outline'] for q in sg]; ys = [q[1] for sg in pcb['outline'] for q in sg]
        s.x0, s.y0 = min(xs), min(ys); s.cx, s.cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        s.nx = int(math.ceil((max(xs) - s.x0) / dx_mm)); s.ny = int(math.ceil((max(ys) - s.y0) / dx_mm)); s.dx = dx_mm * 1e-3
        cu = copper_density(pcb, s.x0, s.y0, s.nx, s.ny, dx_mm)
        s.cu = cu
        tcu = sum(cu[L] * T_LAYERS[L] for L in range(4))
        s.k_sheet = K_CU * tcu + K_FR4 * (THICK - tcu)                       # W/K (in-plane sheet conductance k·t)
        s.C = (RC_CU * tcu + RC_FR4 * (THICK - tcu)) * s.dx * s.dx           # J/K per cell
        s.G_face = 2 * s.dx * s.dx                                          # m² (both faces)
        kmax = (s.k_sheet / THICK).max(); rcmin = (s.C / (s.dx * s.dx * THICK)).min()
        s.dt_max = 0.2 * s.dx * s.dx * rcmin / kmax
        s.T = np.zeros((s.ny, s.nx)); s.Ta = 25.0
        # inter-cell conductances (harmonic mean of sheet conductance; square cells: G = k·t)
        ks = s.k_sheet
        s.Gx = 2 * ks[:, 1:] * ks[:, :-1] / (ks[:, 1:] + ks[:, :-1])
        s.Gy = 2 * ks[1:, :] * ks[:-1, :] / (ks[1:, :] + ks[:-1, :])
    def reset(s, Ta): s.Ta = Ta; s.T[:] = Ta
    def cell(s, x_mm, y_mm):
        """board-local coordinates (mm from outline centre)"""
        i = int((y_mm + s.cy - s.y0) / (s.dx * 1e3)); j = int((x_mm + s.cx - s.x0) / (s.dx * 1e3))
        return min(max(i, 0), s.ny - 1), min(max(j, 0), s.nx - 1)
    def h_eff(s, T):
        Tk = T + 273.15; Ta = s.Ta + 273.15
        return H_CONV + EPS * SIGMA * (Tk * Tk + Ta * Ta) * (Tk + Ta)
    def step(s, Q, dt_total):
        """Q: W per cell (ny,nx). Integrates dt_total seconds with stable sub-steps."""
        n = max(1, int(math.ceil(dt_total / s.dt_max))); dt = dt_total / n
        T = s.T
        for _ in range(n):
            q = Q - s.h_eff(T) * s.G_face * (T - s.Ta)
            fx = s.Gx * (T[:, 1:] - T[:, :-1]); fy = s.Gy * (T[1:, :] - T[:-1, :])
            q[:, :-1] += fx; q[:, 1:] -= fx; q[:-1, :] += fy; q[1:, :] -= fy
            T = T + dt * q / s.C
        s.T = T
        return n
    def steady_theta(s, x_mm, y_mm, P=1.0, psi=0.0, t=2000.0):
        """θJA (°C/W) of a part at (x,y) on this board: run to steady state with P watts."""
        s.reset(25.0); Q = np.zeros_like(s.T); i, j = s.cell(x_mm, y_mm); Q[i, j] = P
        for _ in range(int(t / 20)):
            s.step(Q, 20.0)
        return (s.T[i, j] - 25.0) / P + psi

_cache = {}
def board_thermal(path, dx_mm=2.5):
    if (path, dx_mm) not in _cache:
        _cache[(path, dx_mm)] = BoardThermal(json.load(gzip.open(path, 'rt', encoding='utf-8')), dx_mm)
    return _cache[(path, dx_mm)]
