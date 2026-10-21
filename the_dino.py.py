"""
THE DINO
========
A 2D fruit-catching game made with pygame.

HOW TO RUN
    1.  pip install pygame
    2.  python the_dino.py

CONTROLS
    Mouse   - click PLAY, then press and hold on the dinosaur and drag it anywhere.
    F11     - full screen on / off  (Esc also leaves full screen)

RULES
    Catch the falling fruit (each one = +1 FOOD).  Never touch a bomb!
    35 FOOD = level 2 (faster fruit)      65 FOOD = level 3 (tricky fruit + shields)
    100 FOOD = you win.   A bomb sends you back to level 1.

Everything (dinosaur, fruit, backgrounds, even the sound effects) is drawn or
made by the code below, so there are no image or sound files to carry around.
"""
import math
import random
import sys
import array

import pygame

# =============================================================================
#  SETTINGS  -  numbers you can play with
# =============================================================================
W, H = 1280, 720            # the game is drawn at this size, pygame scales it to your screen
FPS = 60

LEVEL_2_AT = 35             # FOOD needed to reach level 2   (FOOD never resets between levels)
LEVEL_3_AT = 65             # FOOD needed to reach level 3
WIN_AT = 100                # FOOD needed to win

# speed = how fast things fall (pixels per second), spawn_every = seconds between pairs of fruit,
# bomb_rate = bombs per second on average, wobble = 1 means things also drift and zig-zag sideways
LEVELS = {
    1: {"speed": (190, 320), "spawn_every": 1.40, "bomb_rate": 0.30, "wobble": 0},
    2: {"speed": (300, 470), "spawn_every": 1.35, "bomb_rate": 0.30, "wobble": 0},
    3: {"speed": (400, 620), "spawn_every": 1.05, "bomb_rate": 0.40, "wobble": 1},
}
SHIELD_RATE = 0.12          # shields per second on average (level 3 only)
SHIELD_SECONDS = 5.0        # how long the shield protects the dinosaur
SOUND_ON = True             # False = silent game

GROUND_TOP = 640            # where the grass starts on screen
FLOOR_Y = 664               # fruit and bombs land here
STAND_Y = 678               # y of the dinosaur's feet when it stands on the ground

DINO_W, DINO_H = 200, 170   # size of the dinosaur picture
DINO_FOOT = 164             # y (inside that picture) where the feet touch the ground
DINO_START_X = 40           # where the dinosaur stands (far left) when a game starts


# =============================================================================
#  SMALL HELPERS
# =============================================================================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(len(c1)))


def ease_out(t):
    t = clamp(t, 0.0, 1.0)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease_out_back(t, s=1.70158):
    """Overshoots a little and settles - makes pop-ups feel bouncy."""
    t = clamp(t, 0.0, 1.0) - 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def color_at(stops, t):
    """stops = [(0.0, color), (0.5, color), (1.0, color)]  ->  the color at position t."""
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if t <= p1:
            return lerp_color(c0, c1, (t - p0) / max(p1 - p0, 1e-6))
    return stops[-1][1]


def vertical_gradient(w, h, stops, alpha=False):
    surf = pygame.Surface((w, h), pygame.SRCALPHA) if alpha else pygame.Surface((w, h))
    for y in range(h):
        surf.fill(color_at(stops, y / max(h - 1, 1)), (0, y, w, 1))
    return surf


def shaded_circle(surf, cx, cy, r, dark, light, lx=-0.45, ly=-0.55, steps=16):
    """A ball with a light spot toward (lx, ly): many circles that shrink and brighten."""
    for i in range(steps):
        t = i / (steps - 1)
        rad = r * (1 - 0.78 * t)
        col = lerp_color(dark, light, t ** 1.1)
        pygame.draw.circle(surf, col, (cx + lx * r * 0.55 * t, cy + ly * r * 0.55 * t), max(rad, 1))


def shaded_ellipse(surf, cx, cy, rx, ry, dark, light, lx=-0.45, ly=-0.55, steps=16):
    for i in range(steps):
        t = i / (steps - 1)
        a = rx * (1 - 0.78 * t)
        b = ry * (1 - 0.78 * t)
        col = lerp_color(dark, light, t ** 1.1)
        x = cx + lx * rx * 0.55 * t
        y = cy + ly * ry * 0.55 * t
        pygame.draw.ellipse(surf, col, (x - a, y - b, 2 * a, 2 * b))


def star_points(cx, cy, r_out, r_in, angle=0.0, points=5):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = angle + math.pi * i / points - math.pi / 2
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def catmull(points, samples=8):
    """Turns a few points into a smooth curve (Catmull-Rom spline)."""
    p = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(points[-1])
    return out


def tube_polygon(points, widths, samples=8, extra=0.0):
    """A fat curved 'sausage': a smooth centre line with a width at each point -> polygon."""
    centre = catmull(points, samples)
    n = len(centre)
    left, right = [], []
    for k in range(n):
        seg = min(k // samples, len(widths) - 2)
        local = (k - seg * samples) / samples
        w = (lerp(widths[seg], widths[seg + 1], min(local, 1.0)) + extra) / 2
        a = centre[max(k - 1, 0)]
        b = centre[min(k + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        left.append((centre[k][0] + nx * w, centre[k][1] + ny * w))
        right.append((centre[k][0] - nx * w, centre[k][1] - ny * w))
    return left + right[::-1]


# =============================================================================
#  GLOWS AND SOFT SHADOWS  (small pictures made once and reused)
# =============================================================================
_glow_cache = {}
_shadow_cache = {}


def glow_sprite(radius, color, power=2.0):
    """A soft round light on a black background - added onto the screen it looks like a glow."""
    key = (radius, color, power)
    if key not in _glow_cache:
        surf = pygame.Surface((radius * 2, radius * 2))
        steps = max(radius // 2, 8)
        for i in range(steps, 0, -1):
            t = i / steps
            k = (1 - t) ** power
            col = (int(color[0] * k), int(color[1] * k), int(color[2] * k))
            pygame.draw.circle(surf, col, (radius, radius), max(int(radius * t), 1))
        _glow_cache[key] = surf.convert()
    return _glow_cache[key]


def add_glow(target, center, radius, color, power=2.0):
    radius = max(int(radius // 4) * 4, 4)
    g = glow_sprite(radius, color, power)
    target.blit(g, (int(center[0] - radius), int(center[1] - radius)), special_flags=pygame.BLEND_RGB_ADD)


def soft_shadow(w, h, alpha=120):
    """A dark oval that fades out toward its edge."""
    key = (int(w), int(h), alpha)
    if key not in _shadow_cache:
        w, h = int(w), int(h)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        steps = 12
        for i in range(steps):
            t = i / (steps - 1)
            sw = w * (1 - 0.85 * t)
            sh = h * (1 - 0.85 * t)
            a = int(alpha * ((i + 1) / steps) ** 1.4)
            pygame.draw.ellipse(surf, (0, 0, 0, a), (w / 2 - sw / 2, h / 2 - sh / 2, sw, sh))
        _shadow_cache[key] = surf.convert_alpha()
    return _shadow_cache[key]


def blit_center(target, sprite, x, y):
    target.blit(sprite, (int(round(x - sprite.get_width() / 2)), int(round(y - sprite.get_height() / 2))))


# =============================================================================
#  FONTS AND FANCY TEXT  (gradient fill + black outline + soft shadow)
# =============================================================================
_fonts = {}
_text_cache = {}


def get_font(kind, size):
    key = (kind, size)
    if key not in _fonts:
        if kind == "title":
            # Impact is a bold poster font that is on every Windows and Mac. If it is missing, we use another.
            bold = not pygame.font.match_font("impact")
            names = "impact,bahnschrift,arialblack,haettenschweiler,franklingothicheavy,arial"
        else:
            bold = True
            names = "arialrounded,arialroundedmtbold,trebuchetms,verdana,tahoma,arial"
        _fonts[key] = pygame.font.SysFont(names, size, bold=bold)
    return _fonts[key]


def fancy_text(text, kind, size, top, bottom, outline=(0, 0, 0), outline_px=3, shadow=(0, 4), shadow_alpha=110):
    """Returns a picture of the text: gradient fill, outline and a drop shadow."""
    key = (text, kind, size, top, bottom, outline, outline_px, shadow, shadow_alpha)
    if key in _text_cache:
        return _text_cache[key]
    font = get_font(kind, size)
    base = font.render(text, True, (255, 255, 255))
    w, h = base.get_size()
    pad = outline_px + 2
    sx, sy = shadow
    out_w = w + 2 * pad + abs(sx)
    out_h = h + 2 * pad + abs(sy)
    ox = pad + max(-sx, 0)
    oy = pad + max(-sy, 0)
    surf = pygame.Surface((out_w, out_h), pygame.SRCALPHA)
    steps = 16 if outline_px >= 3 else 8
    ring = [(math.cos(2 * math.pi * k / steps) * outline_px, math.sin(2 * math.pi * k / steps) * outline_px)
            for k in range(steps)]
    if shadow_alpha > 0:
        black = font.render(text, True, (0, 0, 0))
        sh = pygame.Surface((out_w, out_h), pygame.SRCALPHA)
        for dx, dy in ring + [(0, 0)]:
            sh.blit(black, (int(ox + sx + dx), int(oy + sy + dy)))
        sh.set_alpha(shadow_alpha)
        surf.blit(sh, (0, 0))
    dark = font.render(text, True, outline)
    for dx, dy in ring:
        surf.blit(dark, (int(ox + dx), int(oy + dy)))
    grad = vertical_gradient(w, h, [(0, top), (1, bottom)], alpha=True)
    fill = base.copy()
    fill.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(fill, (ox, oy))
    surf = surf.convert_alpha()
    _text_cache[key] = surf
    return surf


# =============================================================================
#  SOUND EFFECTS  (made from math - no sound files needed)
# =============================================================================
class Audio:
    def __init__(self):
        self.sounds = {}
        self.ok = False
        if not SOUND_ON:
            return
        try:
            pygame.mixer.pre_init(22050, -16, 2, 512)
            pygame.mixer.init()
            info = pygame.mixer.get_init()
            if not info or info[1] != -16:
                return
            self.rate, _, self.channels = info
            self._build()
            self.ok = True
        except Exception:
            self.ok = False   # no sound card or driver: the game just stays silent

    # ---- tiny synthesizer ----
    def _wave(self, duration, fn):
        n = int(self.rate * duration)
        return [fn(i / self.rate, i / max(n - 1, 1)) for i in range(n)]

    def _sweep(self, f0, f1, dur, vol=0.5, decay=6.0, shape="sine"):
        ratio = f1 / f0

        def fn(t, u):
            if abs(ratio - 1) < 1e-6:
                phase = 2 * math.pi * f0 * t
            else:
                phase = 2 * math.pi * f0 * dur * (ratio ** u - 1) / math.log(ratio)
            s = math.sin(phase)
            if shape == "square":
                s = 0.55 * (1 if s >= 0 else -1) + 0.45 * s
            return s * vol * math.exp(-decay * u) * min(1.0, t / 0.004)
        return self._wave(dur, fn)

    def _noise(self, dur, vol=0.6, decay=5.0, smooth=0.15):
        state = [0.0]

        def fn(t, u):
            state[0] += smooth * (random.uniform(-1, 1) - state[0])
            return state[0] * vol * math.exp(-decay * u)
        return self._wave(dur, fn)

    def _mix(self, *tracks):
        """tracks = (samples, start_time_in_seconds) pairs added together."""
        length = max(int(start * self.rate) + len(s) for s, start in tracks)
        out = [0.0] * length
        for s, start in tracks:
            off = int(start * self.rate)
            for i, v in enumerate(s):
                out[off + i] += v
        return out

    def _make(self, samples, volume=1.0):
        data = array.array("h")
        for v in samples:
            x = int(clamp(v * volume, -1.0, 1.0) * 30000)
            for _ in range(self.channels):
                data.append(x)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _build(self):
        notes = {"C5": 523, "E5": 659, "G5": 784, "C6": 1047, "E6": 1319, "G6": 1568}
        self.sounds["click"] = self._make(self._mix(
            (self._sweep(900, 1500, 0.07, 0.5, 18), 0)), 0.6)
        self.sounds["pop"] = self._make(self._mix(
            (self._sweep(520, 1100, 0.13, 0.55, 12), 0),
            (self._sweep(1040, 2200, 0.09, 0.25, 14), 0.01)), 0.7)
        self.sounds["thud"] = self._make(self._mix(
            (self._sweep(180, 60, 0.12, 0.6, 10), 0)), 0.35)
        self.sounds["shield"] = self._make(self._mix(
            (self._sweep(500, 1000, 0.18, 0.4, 6, "square"), 0),
            (self._sweep(750, 1500, 0.18, 0.4, 6, "square"), 0.09),
            (self._sweep(1000, 2000, 0.3, 0.4, 5, "square"), 0.18)), 0.5)
        self.sounds["boom"] = self._make(self._mix(
            (self._noise(0.95, 0.9, 4.0, 0.2), 0),
            (self._sweep(140, 32, 0.8, 0.9, 3.5), 0)), 0.9)
        self.sounds["puff"] = self._make(self._mix(
            (self._noise(0.4, 0.8, 8.0, 0.3), 0),
            (self._sweep(200, 70, 0.25, 0.5, 8), 0)), 0.6)
        self.sounds["faint"] = self._make(self._mix(
            (self._sweep(440, 330, 0.28, 0.45, 3, "square"), 0.0),
            (self._sweep(392, 294, 0.28, 0.45, 3, "square"), 0.3),
            (self._sweep(349, 247, 0.28, 0.45, 3, "square"), 0.6),
            (self._sweep(294, 150, 0.6, 0.45, 2.5, "square"), 0.9)), 0.55)
        self.sounds["levelup"] = self._make(self._mix(
            (self._sweep(notes["C5"], notes["C5"], 0.2, 0.4, 4, "square"), 0.00),
            (self._sweep(notes["E5"], notes["E5"], 0.2, 0.4, 4, "square"), 0.10),
            (self._sweep(notes["G5"], notes["G5"], 0.2, 0.4, 4, "square"), 0.20),
            (self._sweep(notes["C6"], notes["C6"], 0.55, 0.45, 3, "square"), 0.30),
            (self._sweep(notes["E6"], notes["E6"], 0.55, 0.3, 3), 0.30),
            (self._sweep(notes["G6"], notes["G6"], 0.55, 0.25, 3), 0.30)), 0.55)
        win = [(notes["C5"], 0.0), (notes["E5"], 0.12), (notes["G5"], 0.24), (notes["C6"], 0.36),
               (notes["G5"], 0.52), (notes["C6"], 0.64), (notes["E6"], 0.76), (notes["G6"], 0.92)]
        tracks = [(self._sweep(f, f, 0.3, 0.4, 4, "square"), start) for f, start in win]
        tracks.append((self._sweep(notes["C6"], notes["C6"], 1.0, 0.4, 2.5, "square"), 1.1))
        tracks.append((self._sweep(notes["E6"], notes["E6"], 1.0, 0.3, 2.5), 1.1))
        tracks.append((self._sweep(notes["G6"], notes["G6"], 1.0, 0.3, 2.5), 1.1))
        self.sounds["win"] = self._make(self._mix(*tracks), 0.55)
        self.sounds["whoosh"] = self._make(self._mix(
            (self._noise(0.5, 0.5, 2.5, 0.08), 0)), 0.45)

    def play(self, name):
        s = self.sounds.get(name)
        if s is not None:
            try:
                s.play()
            except Exception:
                pass


# =============================================================================
#  DRAWING TOOLS
# =============================================================================
SS = 2   # "supersampling": pictures are drawn twice as big, then shrunk, so edges look smooth


class Pen:
    """Draws in normal coordinates onto a bigger picture, then shrinks it smoothly."""

    def __init__(self, w, h, ss=SS, bg=(0, 0, 0)):
        self.w, self.h, self.ss = w, h, ss
        self.surf = pygame.Surface((w * ss, h * ss), pygame.SRCALPHA)
        # invisible background in the outline colour, so shrunk edges don't get a dark fringe
        self.surf.fill(tuple(bg) + (0,))

    def P(self, p):
        return (p[0] * self.ss, p[1] * self.ss)

    def poly(self, color, pts):
        pygame.draw.polygon(self.surf, color, [self.P(p) for p in pts])

    def poly_outline(self, fill, pts, outline, ow=2.0):
        """A filled shape with an outline (the outline is the shape stamped in 8 directions)."""
        for k in range(8):
            a = k * math.pi / 4
            dx, dy = math.cos(a) * ow, math.sin(a) * ow
            pygame.draw.polygon(self.surf, outline, [self.P((x + dx, y + dy)) for x, y in pts])
        self.poly(fill, pts)

    def ellipse(self, color, cx, cy, rx, ry):
        s = self.ss
        pygame.draw.ellipse(self.surf, color, ((cx - rx) * s, (cy - ry) * s, 2 * rx * s, 2 * ry * s))

    def circle(self, color, cx, cy, r):
        s = self.ss
        pygame.draw.circle(self.surf, color, (cx * s, cy * s), max(r * s, 1))

    def line(self, color, a, b, width):
        pygame.draw.line(self.surf, color, self.P(a), self.P(b), max(int(width * self.ss), 1))

    def tube(self, color, pts, widths, extra=0.0):
        poly = tube_polygon(pts, widths, 8, extra)
        pygame.draw.polygon(self.surf, color, [self.P(p) for p in poly])
        for p, w in ((pts[0], widths[0]), (pts[-1], widths[-1])):
            self.circle(color, p[0], p[1], (w + extra) / 2)

    def shaded_circle(self, cx, cy, r, dark, light, lx=-0.45, ly=-0.55, steps=16):
        s = self.ss
        shaded_circle(self.surf, cx * s, cy * s, r * s, dark, light, lx, ly, steps)

    def shaded_ellipse(self, cx, cy, rx, ry, dark, light, lx=-0.45, ly=-0.55, steps=16):
        s = self.ss
        shaded_ellipse(self.surf, cx * s, cy * s, rx * s, ry * s, dark, light, lx, ly, steps)

    def erase_circle(self, cx, cy, r):
        s = self.ss
        pygame.draw.circle(self.surf, (0, 0, 0, 0), (cx * s, cy * s), r * s)

    def finish(self):
        return pygame.transform.smoothscale(self.surf, (self.w, self.h)).convert_alpha()


def rotate_point(p, c, ang):
    """Turns point p around centre c by ang radians (positive = clockwise on screen)."""
    dx, dy = p[0] - c[0], p[1] - c[1]
    ca, sa = math.cos(ang), math.sin(ang)
    return (c[0] + dx * ca - dy * sa, c[1] + dx * sa + dy * ca)


def ellipse_points(cx, cy, rx, ry, deg=0.0, n=28):
    """Points around a tilted ellipse (tilted so its top leans left when deg is negative)."""
    out = []
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    for k in range(n):
        t = 2 * math.pi * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return out


# =============================================================================
#  THE DINOSAUR   (a cartoon T-rex, drawn from shapes)
# =============================================================================
DINO = {
    "outline": (12, 28, 90),
    "dark": (30, 74, 190),
    "base": (50, 116, 238),
    "light": (116, 178, 255),
    "belly": (176, 218, 255),
    "belly_dark": (118, 168, 238),
    "spike": (20, 50, 150),
    "far": (34, 84, 202),
    "claw": (244, 238, 214),
    "mouth": (122, 22, 48),
    "tongue": (240, 96, 120),
}
_dino_cache = {}


def render_dino(t, run=False, phase=0.0, blink=False, mouth=0.0, dead=False, dangle=False):
    """Draws the dinosaur facing right.  Remembers every pose it has drawn, so it is fast."""
    frame = int(t * 24) % 120          # the idle animation loops every 5 seconds
    step = 0
    if run:
        step = int((phase % (2 * math.pi)) / (2 * math.pi) * 24) % 24
        frame = 0
    mouth_q = int(clamp(mouth, 0, 1) * 8)
    key = (frame, step, bool(run), bool(blink), mouth_q, bool(dead), bool(dangle))
    if key in _dino_cache:
        return _dino_cache[key]
    if len(_dino_cache) > 800:
        _dino_cache.clear()

    c = DINO
    ph = step / 24 * 2 * math.pi
    tl = frame / 120 * 2 * math.pi
    mouth = mouth_q / 8
    pen = Pen(DINO_W, DINO_H, SS, bg=c["outline"])
    GY = DINO_FOOT
    ow = 2.2
    breathe = math.sin(2 * tl)
    bob = -abs(math.sin(ph)) * 3.5 if run else breathe * 1.2
    sway = math.sin(ph + 1.0) * 6 if run else math.sin(tl) * 3.5
    if dead or dangle:
        bob = breathe * 0.8
        sway = math.sin(4 * tl) * 4

    def shift(pts, dy):
        return [(x, y + dy) for x, y in pts]

    def foot(base_x):
        if dead or dangle:
            a = 4 * tl + base_x * 0.07
            return (base_x + 5 * math.sin(a), GY - 34 + 5 * math.cos(a))
        if run:
            p = ph + (0.0 if base_x < 90 else math.pi)
            return (base_x + 20 * math.sin(p), GY - 14 - max(0.0, math.cos(p)) * 17)
        return (base_x, GY - 14)

    def leg(hip, ankle, fill, width_hip):
        hx, hy = hip
        ax, ay = ankle
        dx, dy = ax - hx, ay - hy
        d = math.hypot(dx, dy) or 1.0
        knee = ((hx + ax) / 2 + dy / d * 14, (hy + ay) / 2 - dx / d * 14)
        pts = [hip, knee, ankle]
        widths = [width_hip, 18, 11]
        toe = [(ax - 7, ay - 4), (ax + 5, ay - 8), (ax + 18, ay - 3), (ax + 31, ay + 5), (ax + 35, ay + 11),
               (ax + 31, ay + 14), (ax - 7, ay + 14)]
        pen.tube(c["outline"], pts, widths, extra=2 * ow)
        pen.poly_outline(fill, toe, c["outline"], ow)
        pen.tube(fill, pts, widths)
        pen.line(c["outline"], (ax + 15, ay + 14), (ax + 21, ay + 5), 1.2)
        pen.line(c["outline"], (ax + 24, ay + 14), (ax + 29, ay + 8), 1.2)
        pen.poly(c["claw"], [(ax + 33, ay + 8), (ax + 42, ay + 12), (ax + 33, ay + 14)])
        pen.poly(c["claw"], [(ax + 22, ay + 11), (ax + 28, ay + 15), (ax + 21, ay + 15)])

    # ---- back spikes (behind everything) ----
    spikes = [(24, 97, -35, 9), (38, 89, -30, 11), (54, 80, -25, 13), (70, 70, -18, 14), (86, 63, -10, 15),
              (102, 60, -4, 15), (118, 60, 4, 14), (130, 54, 12, 13), (140, 42, 20, 12)]
    for sx, sy, ang, size in spikes:
        a = math.radians(ang)
        dx, dy = math.sin(a), -math.cos(a)
        tx, ty = math.cos(a), math.sin(a)
        bx, by = sx - dx * 3, sy - dy * 3 + bob
        pts = [(bx - tx * size * 0.5, by - ty * size * 0.5), (bx + dx * size * 1.4, by + dy * size * 1.4),
               (bx + tx * size * 0.5, by + ty * size * 0.5)]
        pen.poly_outline(c["spike"], pts, c["outline"], 1.8)

    # ---- far hind leg (darker, behind the body) ----
    leg((96, 110 + bob), foot(106), c["far"], 22)

    # ---- body outline (tail + neck + body share one outline) ----
    tail = [(74, 86 + bob), (52, 95 + bob), (30, 102 + bob + sway * 0.5), (8, 106 + bob + sway)]
    tail_w = [46, 30, 16, 5]
    neck = [(112, 84 + bob), (130, 66 + bob), (146, 48 + bob)]
    neck_w = [40, 32, 28]
    ry = 36 + breathe * 0.8
    pen.tube(c["outline"], tail, tail_w, extra=2 * ow)
    pen.tube(c["outline"], neck, neck_w, extra=2 * ow)
    pen.ellipse(c["outline"], 98, 96 + bob, 52 + ow, ry + ow)

    # ---- tail and neck fill ----
    pen.tube(c["dark"], tail, tail_w)
    pen.tube(c["base"], shift(tail, -2.5), [w - 5 for w in tail_w])
    pen.tube(c["light"], shift(tail, -8), [max(w * 0.22, 2) for w in tail_w])
    pen.tube(c["dark"], neck, neck_w)
    pen.tube(c["base"], shift(neck, -2.5), [w - 5 for w in neck_w])
    pen.tube(c["light"], [(x - 3, y - 4) for x, y in neck], [w * 0.22 for w in neck_w])

    # ---- body ----
    pen.ellipse(c["dark"], 98, 96 + bob, 52, ry)
    pen.shaded_ellipse(98, 93 + bob, 50, ry - 3, c["base"], c["light"], lx=-0.25, ly=-0.75, steps=14)
    # belly
    pen.shaded_ellipse(104, 112 + bob, 38, 17, c["belly_dark"], c["belly"], lx=0, ly=-0.6, steps=8)
    for i in range(5):
        x = 80 + i * 12
        e = 17 * math.sqrt(max(1 - ((x - 104) / 38) ** 2, 0)) - 3
        pen.line(c["belly_dark"], (x, 112 + bob - e), (x + 2, 112 + bob + e), 1.2)
    # scale spots
    for sx, sy in [(62, 84), (78, 74), (94, 70), (110, 72), (124, 76), (44, 92), (30, 100)]:
        pen.circle(c["dark"], sx, sy + bob, 3.6)
        pen.circle(c["base"], sx - 0.5, sy + bob - 0.6, 2.0)

    # ---- near hind leg ----
    leg((84, 116 + bob), foot(78), c["base"], 20)
    pen.poly_outline(c["base"], ellipse_points(87, 113 + bob, 19, 30, -24), c["outline"], ow)
    pen.poly(lerp_color(c["base"], c["light"], 0.45), ellipse_points(83, 106 + bob, 11, 19, -24))
    pen.poly(lerp_color(c["base"], c["light"], 0.8), ellipse_points(80, 100 + bob, 5, 9, -24))

    # ---- little arm ----
    arm = [(128, 98 + bob), (140, 108 + bob), (150, 106 + bob)]
    arm_w = [13, 10, 8]
    pen.tube(c["outline"], arm, arm_w, extra=2 * ow)
    pen.tube(c["base"], arm, arm_w)
    pen.poly(c["claw"], [(148, 101 + bob), (158, 103 + bob), (149, 106 + bob)])
    pen.poly(c["claw"], [(148, 105 + bob), (157, 109 + bob), (148, 109 + bob)])

    # ---- head ----
    hb = bob
    skull = shift([(138, 30), (146, 16), (162, 10), (180, 14), (194, 26), (198, 36), (196, 44), (182, 50),
                   (160, 54), (142, 54), (134, 44)], hb)
    pen.poly_outline(c["base"], skull, c["outline"], ow)
    pen.poly(c["dark"], shift([(142, 48), (160, 50), (182, 46), (194, 40), (196, 44), (182, 50), (160, 54), (142, 54)], hb))
    pen.poly(c["light"], shift([(146, 20), (162, 14), (180, 17), (191, 26), (176, 24), (160, 22)], hb))

    hinge = (148, 53 + hb)
    jaw = shift([(148, 52), (184, 50), (191, 55), (185, 61), (160, 65), (146, 60)], hb)
    ang = math.radians(mouth * 32 + (8 if dead else 0))
    jaw_r = [rotate_point(p, hinge, ang) for p in jaw]
    if mouth > 0.05 or dead:
        inside = [(150, 54 + hb), (190, 54 + hb), jaw_r[2], jaw_r[5]]
        pen.poly(c["mouth"], inside)
        tongue_c = rotate_point((166, 60 + hb), hinge, ang)
        pen.ellipse(c["tongue"], tongue_c[0], tongue_c[1], 12, 4)
    pen.poly_outline(c["base"], jaw_r, c["outline"], ow * 0.9)
    pen.poly(c["belly_dark"], [jaw_r[3], jaw_r[4], jaw_r[5], rotate_point((150, 56 + hb), hinge, ang), rotate_point((184, 57 + hb), hinge, ang)])
    for tx in (160, 169, 178, 187):
        pen.poly_outline((250, 250, 245), [(tx - 3, 53 + hb), (tx + 3, 53 + hb), (tx, 59 + hb)], c["outline"], 0.8)
    for tx in (164, 174, 183):
        top = jaw[0][1] + (jaw[1][1] - jaw[0][1]) * (tx - 148) / 36
        tri = [(tx - 2.5, top + 1), (tx + 2.5, top + 1), (tx, top - 4.5)]
        pen.poly((250, 250, 245), [rotate_point(p, hinge, ang) for p in tri])

    # nostril, brow, eye
    pen.ellipse(c["outline"], 188, 27 + hb, 2.8, 2.0)
    ex, ey = 164, 27 + hb
    if dead:
        pen.ellipse((250, 250, 250), ex, ey, 8, 8.5)
        pen.line(c["outline"], (ex - 5, ey - 5), (ex + 5, ey + 5), 2.6)
        pen.line(c["outline"], (ex - 5, ey + 5), (ex + 5, ey - 5), 2.6)
    elif blink:
        pen.ellipse(c["base"], ex, ey, 8.4, 9)
        pen.line(c["outline"], (ex - 6, ey + 1), (ex + 6, ey + 1), 2.4)
    else:
        pen.ellipse(c["outline"], ex, ey, 8.6, 9.2)
        pen.ellipse((252, 252, 252), ex, ey, 7.4, 8.1)
        pen.ellipse((10, 20, 62), ex + 1.8, ey + 0.8, 4.4, 5.2)
        pen.circle((255, 255, 255), ex + 0.6, ey - 1.6, 1.8)
        pen.circle((255, 255, 255), ex + 3.2, ey + 2.6, 0.9)
    brow_dy = 3 if dead else 0
    pen.line(c["outline"], (152, 17 + hb + brow_dy), (174, 20 + hb - brow_dy), 2.6)

    surf = pen.finish()
    _dino_cache[key] = surf
    return surf


# =============================================================================
#  FRUIT, BOMB, SHIELD AND BUBBLE PICTURES
# =============================================================================
def make_apple():
    pen = Pen(86, 92, 3, bg=(110, 10, 25))
    out = (110, 10, 25)
    pen.ellipse(out, 43, 56, 36, 33.5)
    pen.shaded_ellipse(43, 56, 34, 31.5, (168, 18, 34), (255, 112, 100), lx=-0.35, ly=-0.5, steps=20)
    pen.circle(out, 43, 26, 9.5)
    pen.erase_circle(43, 25, 6.2)
    pen.tube((60, 36, 12), [(43, 29), (45, 18), (50, 10)], [6, 5, 5], extra=3)
    pen.tube((124, 78, 34), [(43, 29), (45, 18), (50, 10)], [6, 5, 5])
    leaf = [(50, 14), (62, 5), (78, 8), (82, 14), (68, 19)]
    pen.poly_outline((86, 196, 62), leaf, (18, 86, 30), 1.6)
    pen.line((150, 232, 110), (54, 13), (76, 11), 1.2)
    pen.ellipse((255, 196, 190), 27, 44, 6.5, 11)
    pen.ellipse((255, 238, 232), 26, 41, 3.2, 6)
    pen.circle((255, 255, 255), 60, 70, 2.4)
    return pen.finish()


def make_banana():
    pen = Pen(114, 86, 3, bg=(118, 78, 10))
    out = (118, 78, 10)
    for dx, dy, dark, base, light in ((-8, 9, (200, 146, 16), (236, 196, 30), (252, 232, 120)),
                                      (0, 0, (214, 160, 18), (252, 214, 42), (255, 244, 156))):
        pts = [(20 + dx, 22 + dy), (38 + dx, 50 + dy), (68 + dx, 60 + dy), (100 + dx, 38 + dy)]
        widths = [10, 29, 29, 12]
        pen.tube(out, pts, widths, extra=6)
        pen.tube(dark, pts, widths)
        pen.tube(base, [(x, y - 2.5) for x, y in pts], [w - 6 for w in widths])
        pen.tube(light, [(x - 1, y - 7) for x, y in pts[1:3]], [7, 7])
        pen.circle((96, 60, 24), pts[0][0] - 1, pts[0][1] - 1, 5)
        pen.circle((70, 44, 20), pts[-1][0] + 1, pts[-1][1] - 1, 3.6)
    return pen.finish()


def make_grapes():
    pen = Pen(90, 108, 3, bg=(56, 18, 96))
    out = (56, 18, 96)
    pen.tube((60, 36, 12), [(45, 34), (45, 20), (40, 9)], [6, 5, 5], extra=3)
    pen.tube((124, 78, 34), [(45, 34), (45, 20), (40, 9)], [6, 5, 5])
    leaf = [(46, 18), (58, 6), (76, 8), (80, 16), (64, 22)]
    pen.poly_outline((86, 196, 62), leaf, (18, 86, 30), 1.6)
    rows = [(4, 36), (3, 53), (2, 70), (1, 87)]
    for count, y in rows:
        x0 = 45 - (count - 1) * 11.5
        for i in range(count):
            cx, cy = x0 + i * 23, y
            pen.circle(out, cx, cy, 13.8)
            pen.shaded_circle(cx, cy, 12.4, (82, 26, 134), (192, 126, 240), lx=-0.5, ly=-0.55, steps=12)
            pen.circle((236, 214, 255), cx - 4.2, cy - 4.6, 2.6)
    return pen.finish()


def make_bomb():
    pen = Pen(100, 120, 3, bg=(8, 8, 14))
    pen.circle((8, 8, 14), 50, 74, 38)
    pen.shaded_circle(50, 74, 36, (12, 12, 22), (112, 120, 152), lx=-0.45, ly=-0.55, steps=22)
    pen.ellipse((176, 186, 214), 36, 56, 8, 12.5)
    pen.ellipse((236, 240, 252), 34, 52, 3.6, 6)
    pen.poly_outline((128, 134, 150), [(35, 42), (65, 42), (61, 31), (39, 31)], (8, 8, 14), 2)
    pen.poly((176, 182, 198), [(38, 33), (62, 33), (63, 36), (37, 36)])
    pen.tube((46, 26, 10), [(52, 32), (57, 22), (56, 13), (63, 6)], [8, 8, 8, 7.5], extra=3.5)
    pen.tube((170, 118, 56), [(52, 32), (57, 22), (56, 13), (63, 6)], [8, 8, 8, 7.5])
    for p in [(55, 27), (57, 21), (57, 15), (60, 10)]:
        pen.line((96, 60, 26), (p[0] - 3.5, p[1] - 1.5), (p[0] + 3.5, p[1] + 1.5), 1.6)
    return pen.finish()


def shield_polygon(cx, cy, w, h):
    return [(cx - w / 2, cy - h / 2 + 8), (cx, cy - h / 2), (cx + w / 2, cy - h / 2 + 8), (cx + w / 2, cy + h * 0.05),
            (cx + w * 0.38, cy + h * 0.30), (cx, cy + h / 2), (cx - w * 0.38, cy + h * 0.30), (cx - w / 2, cy + h * 0.05)]


def make_shield_item():
    pen = Pen(84, 100, 3, bg=(20, 36, 110))
    cx, cy = 42, 50
    pen.poly_outline((255, 206, 72), shield_polygon(cx, cy, 72, 88), (20, 36, 110), 2.4)
    pen.poly((255, 240, 160), shield_polygon(cx - 1.5, cy - 2, 64, 78))
    pen.poly((226, 150, 30), shield_polygon(cx, cy + 1, 62, 76))
    for i in range(9):
        t = i / 8
        k = 1 - i * 0.045
        pen.poly(lerp_color((38, 84, 226), (138, 196, 255), t ** 0.9), shield_polygon(cx - 0.5 * t, cy - 2 - 5 * t, 56 * k, 70 * k))
    pen.poly_outline((255, 255, 255), star_points(cx, cy + 1, 15, 6.5), (20, 36, 110), 1.6)
    pen.poly((210, 232, 255), [(cx - 22, cy - 28), (cx - 8, cy - 32), (cx - 24, cy - 8)])
    return pen.finish()


def make_bubble(diameter=300):
    r = diameter // 2
    pen = Pen(diameter, diameter, 2, bg=(255, 170, 70))
    s = pen.ss
    surf = pen.surf
    steps = 30
    for i in range(steps):
        t = i / (steps - 1)
        rad = r * s * (1 - 0.97 * t)
        a = int(lerp(120, 28, t ** 0.8))
        pygame.draw.circle(surf, (255, 172, 72, a), (r * s, r * s), rad)
    pygame.draw.circle(surf, (80, 170, 255, 110), (r * s, r * s), (r - 1) * s, 7 * s)
    pygame.draw.circle(surf, (60, 150, 255, 240), (r * s, r * s), (r - 5) * s, 6 * s)
    pygame.draw.circle(surf, (190, 232, 255, 255), (r * s, r * s), (r - 7) * s, 2 * s)
    arc = [(r + math.cos(math.radians(a)) * (r - 20), r + math.sin(math.radians(a)) * (r - 20)) for a in range(200, 262, 4)]
    pygame.draw.lines(surf, (255, 255, 255, 215), False, [(x * s, y * s) for x, y in arc], 6 * s)
    pen.circle((255, 255, 255, 215), r + math.cos(math.radians(276)) * (r - 20), r + math.sin(math.radians(276)) * (r - 20), 4)
    return pen.finish()


def make_cloud(w, h, light, shade):
    pen = Pen(w, h, 2, bg=light)
    blobs = [(0.18, 0.64, 0.20), (0.36, 0.46, 0.28), (0.58, 0.40, 0.32), (0.78, 0.54, 0.24), (0.90, 0.68, 0.16)]
    for fx, fy, fr in blobs:
        pen.circle(shade, fx * w, (fy + 0.07) * h, fr * h)
    pen.poly(shade, [(0.12 * w, 0.70 * h), (0.95 * w, 0.70 * h), (0.95 * w, 0.88 * h), (0.12 * w, 0.88 * h)])
    for fx, fy, fr in blobs:
        pen.circle(light, fx * w, fy * h, fr * h)
    pen.poly(light, [(0.12 * w, 0.68 * h), (0.95 * w, 0.68 * h), (0.95 * w, 0.80 * h), (0.12 * w, 0.80 * h)])
    pen.poly(light, [(0.28 * w, 0.50 * h), (0.82 * w, 0.50 * h), (0.82 * w, 0.70 * h), (0.28 * w, 0.70 * h)])
    return pen.finish()


# =============================================================================
#  BACKGROUND WORLDS  (the home screen + one for each level)
# =============================================================================
THEMES = {
    "home": dict(
        sky=[(0, (22, 20, 80)), (0.36, (96, 48, 132)), (0.66, (232, 104, 108)), (0.90, (255, 176, 108)), (1, (255, 214, 140))],
        sun=(430, 470, 118, (255, 232, 170), (255, 140, 70)), moon=None, stars=70,
        volcano=((58, 34, 84), 940, 250, False),
        far=((104, 60, 138), (156, 100, 176)), mid=((74, 44, 112), (120, 78, 152)), near=((44, 28, 78), (92, 62, 122)),
        trees=((22, 14, 44), "palm"), ground=((70, 46, 90), (26, 18, 46)), grass=((128, 90, 148), (82, 58, 104)),
        fg=(18, 10, 34), cloud=((255, 188, 150), (214, 120, 140)), critter="ptero", embers=6, fireflies=True, smoke=True),
    1: dict(
        sky=[(0, (64, 142, 240)), (0.55, (140, 204, 252)), (1, (226, 246, 255))],
        sun=(1040, 150, 56, (255, 248, 190), (255, 236, 130)), moon=None, stars=0, volcano=None,
        far=((142, 178, 218), (190, 214, 240)), mid=((98, 178, 112), (152, 216, 152)), near=((58, 148, 78), (112, 192, 112)),
        trees=((28, 104, 62), "palm"), ground=((112, 202, 84), (98, 66, 40)), grass=((156, 230, 104), (84, 170, 66)),
        fg=(38, 120, 52), cloud=((255, 255, 255), (206, 224, 244)), critter="birds", embers=0, fireflies=False, smoke=False),
    2: dict(
        sky=[(0, (56, 36, 108)), (0.42, (190, 70, 122)), (0.76, (255, 138, 82)), (1, (255, 208, 124))],
        sun=(900, 470, 96, (255, 228, 156), (255, 160, 80)), moon=None, stars=40, volcano=None,
        far=((150, 84, 140), (204, 124, 164)), mid=((120, 58, 114), (172, 92, 132)), near=((82, 42, 88), (132, 72, 112)),
        trees=((46, 24, 62), "palm"), ground=((196, 112, 72), (94, 52, 52)), grass=((238, 152, 86), (162, 88, 68)),
        fg=(54, 28, 62), cloud=((255, 176, 150), (222, 114, 134)), critter="ptero", embers=0, fireflies=False, smoke=False),
    3: dict(
        sky=[(0, (6, 8, 26)), (0.55, (28, 22, 72)), (0.86, (98, 38, 82)), (1, (176, 64, 60))],
        sun=None, moon=(190, 130, 46), stars=110, volcano=((52, 36, 72), 900, 230, True),
        far=((42, 34, 86), (76, 62, 124)), mid=((30, 24, 66), (58, 46, 102)), near=((20, 16, 46), (46, 36, 80)),
        trees=((10, 8, 24), "dead"), ground=((64, 42, 54), (24, 16, 30)), grass=((92, 62, 72), (52, 36, 50)),
        fg=(8, 6, 18), cloud=None, critter=None, embers=14, fireflies=False, smoke=True, lava_ground=True),
}

RIDGES = [   # base_y, harmonics (how many bumps, how tall), jagged?, scroll speed in pixels per second
    (455, [(2, 80), (3, 46), (5, 24)], True, 5),
    (520, [(1, 36), (2, 22), (3, 12)], False, 12),
    (585, [(1, 24), (2, 14), (4, 8)], False, 24),
]


def ridge_y(x, base_y, harmonics, phases, jagged):
    y = base_y
    for (k, amp), ph in zip(harmonics, phases):
        if jagged:
            y -= amp * (1 - abs(math.sin(math.pi * k * x / W + ph)))     # sharp mountain peaks
        else:
            y -= amp * math.sin(2 * math.pi * k * x / W + ph)            # soft rolling hills
    return y


def draw_palm(pen, x, y, s, color, lean, rng):
    h = 150 * s
    trunk = [(x, y + 6), (x + lean * 0.3 * h, y - h * 0.4), (x + lean * 0.7 * h, y - h * 0.75), (x + lean * h, y - h)]
    pen.tube(color, trunk, [14 * s, 11 * s, 9 * s, 8 * s])
    cx, cy = trunk[-1]
    for k in range(8):
        ang = math.radians(-170 + k * (160 / 7))
        length = (72 + rng.uniform(-10, 10)) * s
        dx, dy = math.cos(ang), math.sin(ang)
        mid = (cx + dx * length * 0.55, cy + dy * length * 0.55 - 8 * s)
        tip = (cx + dx * length, cy + dy * length + 26 * s)
        pen.tube(color, [(cx, cy), mid, tip], [7 * s, 12 * s, 1.5 * s])


def draw_dead_tree(pen, x, y, s, color, rng):
    def branch(px, py, ang, length, width, depth):
        ex, ey = px + math.cos(ang) * length, py + math.sin(ang) * length
        mx = (px + ex) / 2 + rng.uniform(-6, 6) * s
        my = (py + ey) / 2 + rng.uniform(-6, 6) * s
        pen.tube(color, [(px, py), (mx, my), (ex, ey)], [width, width * 0.75, width * 0.55])
        if depth > 0:
            for da in (-0.55, 0.5):
                branch(ex, ey, ang + da + rng.uniform(-0.2, 0.2), length * 0.68, width * 0.55, depth - 1)
    branch(x, y + 4, -math.pi / 2 + rng.uniform(-0.15, 0.15), 70 * s, 10 * s, 3)


def make_layer(color, rim, ridge, seed, trees=None):
    """One strip of mountains or hills.  Its left and right edges match, so it can scroll forever."""
    base_y, harmonics, jagged, _speed = ridge
    rng = random.Random(seed)
    phases = [rng.uniform(0, 2 * math.pi) for _ in harmonics]
    top = int(max(min(ridge_y(x, base_y, harmonics, phases, jagged) for x in range(0, W, 8)) - 230, 0))
    h = GROUND_TOP + 30 - top
    pen = Pen(W, h, 2, bg=color)
    pts = [(x, ridge_y(x, base_y, harmonics, phases, jagged) - top) for x in range(0, W + 8, 8)]
    pen.poly(color, pts + [(W + 8, h), (0, h)])
    for a, b in zip(pts, pts[1:]):
        pen.line(rim, (a[0], a[1] + 1), (b[0], b[1] + 1), 3)
    if trees:
        tcolor, kind = trees
        positions = [70, 300, 560, 800, 1060, 1210] if kind == "palm" else [120, 420, 760, 1000, 1180]
        for x in positions:
            x += rng.uniform(-30, 30)
            gy = ridge_y(x, base_y, harmonics, phases, jagged) - top
            s = rng.uniform(0.8, 1.25)
            lean = rng.uniform(-0.25, 0.25)
            for dx in (-W, 0, W):          # draw copies at both edges so the strip tiles perfectly
                if kind == "palm":
                    draw_palm(pen, x + dx, gy, s, tcolor, lean, random.Random(int(x) + seed))
                else:
                    draw_dead_tree(pen, x + dx, gy, s, tcolor, random.Random(int(x) + seed))
    return pen.finish(), top


def make_volcano(surf, color, vx, top_y, erupting):
    base_y = GROUND_TOP
    pts = [(vx - 460, base_y + 10), (vx - 300, base_y - 70), (vx - 170, top_y + 110), (vx - 95, top_y + 20), (vx - 60, top_y),
           (vx + 60, top_y), (vx + 95, top_y + 20), (vx + 180, top_y + 115), (vx + 310, base_y - 70), (vx + 470, base_y + 10)]
    pygame.draw.polygon(surf, color, catmull(pts, 6))
    pygame.draw.ellipse(surf, lerp_color(color, (255, 120, 40), 0.85 if erupting else 0.25), (vx - 62, top_y - 7, 124, 16))
    if erupting:
        streams = [[(vx - 50, top_y + 6), (vx - 86, top_y + 56), (vx - 130, top_y + 112), (vx - 182, top_y + 176), (vx - 236, top_y + 230)],
                   [(vx + 54, top_y + 6), (vx + 92, top_y + 62), (vx + 142, top_y + 128), (vx + 200, top_y + 192), (vx + 250, top_y + 238)]]
        for line in streams:
            pygame.draw.polygon(surf, (226, 80, 24), tube_polygon(line, [14, 15, 12, 9, 5], 8))
            pygame.draw.polygon(surf, (255, 190, 70), tube_polygon(line, [6, 7, 5, 3.5, 2], 8))


def make_sky(th, rng):
    surf = vertical_gradient(W, H, th["sky"])
    if th["sun"]:
        sx, sy, sr, core, glow = th["sun"]
        add_glow(surf, (sx, sy), int(sr * 3.4), glow, 2.2)
        pygame.draw.circle(surf, lerp_color(core, glow, 0.35), (sx, sy), sr + 5)
        pygame.draw.circle(surf, core, (sx, sy), sr)
    if th["moon"]:
        mx, my, mr = th["moon"]
        add_glow(surf, (mx, my), int(mr * 4.2), (110, 130, 220), 2.0)
        pygame.draw.circle(surf, (226, 232, 250), (mx, my), mr)
        for cx_, cy_, cr in [(-14, -10, 9), (12, 6, 12), (-6, 18, 6), (16, -18, 5)]:
            pygame.draw.circle(surf, (196, 204, 232), (mx + cx_, my + cy_), cr)
    if th["volcano"]:
        color, vx, top_y, erupting = th["volcano"]
        make_volcano(surf, color, vx, top_y, erupting)
    return surf.convert()


def make_ground(th, rng):
    gh = H - GROUND_TOP + 12
    top_c, bot_c = th["ground"]
    grad = vertical_gradient(W, gh, [(0, top_c), (1, bot_c)], alpha=True)
    edge = [(x, 8 + 4 * math.sin(x / 90.0) + 3 * math.sin(x / 37.0 + 1)) for x in range(0, W + 10, 10)]
    mask = pygame.Surface((W, gh), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), edge + [(W, gh), (0, gh)])
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    light, dark = th["grass"]
    pygame.draw.lines(grad, lerp_color(top_c, (255, 255, 255), 0.22), False, edge, 5)
    for x in range(0, W, 5):
        ey = 8 + 4 * math.sin(x / 90.0) + 3 * math.sin(x / 37.0 + 1)
        hh = rng.uniform(6, 18)
        col = light if rng.random() < 0.55 else dark
        pygame.draw.polygon(grad, col, [(x - 3, ey + 4), (x + rng.uniform(-4, 4), ey - hh), (x + 3, ey + 4)])
    for _ in range(170):
        x, y = rng.uniform(0, W), rng.uniform(34, gh - 4)
        col = lerp_color(top_c, bot_c, rng.uniform(0.3, 1.0))
        col = lerp_color(col, (0, 0, 0) if rng.random() < 0.5 else (255, 255, 255), 0.14)
        r = rng.uniform(2, 6)
        pygame.draw.ellipse(grad, col, (x, y, r * 2, r))
    for _ in range(7):
        x, y, r = rng.uniform(0, W), rng.uniform(46, gh - 14), rng.uniform(7, 15)
        pygame.draw.ellipse(grad, lerp_color(bot_c, (150, 150, 160), 0.35), (x, y, r * 2.2, r * 1.2))
        pygame.draw.ellipse(grad, lerp_color(bot_c, (210, 210, 220), 0.35), (x + 2, y + 1, r * 1.5, r * 0.6))
    if th.get("lava_ground"):
        for _ in range(11):
            x, y = rng.uniform(0, W), rng.uniform(34, gh - 18)
            direction = rng.choice([-1, 1])
            pts = [(x, y)]
            for _ in range(6):
                x += direction * rng.uniform(10, 30)
                y = clamp(y + rng.uniform(-5, 7), 30, gh - 8)
                pts.append((x, y))
            pygame.draw.lines(grad, (255, 110, 30), False, pts, 4)
            pygame.draw.lines(grad, (255, 214, 90), False, pts, 2)
    return grad.convert_alpha()


def make_foreground(th, rng):
    h = 90
    pen = Pen(W, h, 2, bg=th["fg"])
    col = th["fg"]
    for _ in range(150):
        x = rng.uniform(-10, W + 10)
        bh = rng.uniform(14, 46)
        lean = rng.uniform(-9, 9)
        shade = lerp_color(col, (255, 255, 255), rng.uniform(0, 0.12))
        pen.poly(shade, [(x - 4, h + 2), (x + lean, h - bh), (x + 5, h + 2)])
    return pen.finish(), H - h


def make_vignette():
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 120))
    steps = 26
    for i in range(steps):
        t = i / (steps - 1)
        rx = lerp(W * 0.78, W * 0.22, t)
        ry = lerp(H * 0.82, H * 0.22, t)
        a = int(120 * (1 - t) ** 1.6)
        pygame.draw.ellipse(surf, (0, 0, 0, a), (W / 2 - rx, H / 2 - ry, 2 * rx, 2 * ry))
    return surf.convert_alpha()


class World:
    """A complete background: sky, drifting clouds, scrolling hills, ground and glowing details."""

    def __init__(self, key):
        th = THEMES[key]
        self.th = th
        seed = 7 if key == "home" else key * 11
        rng = random.Random(seed)
        self.sky = make_sky(th, rng)
        self.layers = []
        for i, ridge in enumerate(RIDGES):
            colors = (th["far"], th["mid"], th["near"])[i]
            surf, top = make_layer(colors[0], colors[1], ridge, seed + i, trees=th["trees"] if i == 2 else None)
            self.layers.append((surf.convert_alpha(), top, ridge[3]))
        self.ground = make_ground(th, rng)
        self.fg, self.fg_y = make_foreground(th, rng)
        self.fg = self.fg.convert_alpha()
        self.clouds = []
        if th["cloud"]:
            light, shade = th["cloud"]
            sprites = [make_cloud(260, 120, light, shade), make_cloud(200, 96, light, shade), make_cloud(330, 140, light, shade)]
            for i in range(6):
                spr = sprites[i % 3]
                self.clouds.append({"x": rng.uniform(-100, W), "y": rng.uniform(30, 250), "spr": spr, "v": rng.uniform(8, 22)})
        self.stars = [(rng.uniform(0, W), rng.uniform(0, 330), rng.uniform(0, 6.3), rng.choice([1, 1, 2])) for _ in range(th["stars"])]
        self.critters = []
        if th["critter"] == "birds":
            self.critters = [{"x": rng.uniform(0, W), "y": rng.uniform(90, 260), "v": rng.uniform(40, 70), "ph": rng.uniform(0, 6), "s": rng.uniform(0.8, 1.3)} for _ in range(4)]
        elif th["critter"] == "ptero":
            self.critters = [{"x": rng.uniform(0, W), "y": rng.uniform(110, 240), "v": rng.uniform(50, 80), "ph": rng.uniform(0, 6), "s": rng.uniform(0.9, 1.3)} for _ in range(2)]
        self.parts = []
        self.fireflies = [[rng.uniform(0, W), rng.uniform(380, 630), rng.uniform(0, 6.3), rng.uniform(0.4, 1.0)] for _ in range(26)] if th["fireflies"] else []
        self.t = 0.0
        self.rng = random.Random(seed + 99)

    # ---- animation ----
    def update(self, dt):
        self.t += dt
        for c in self.clouds:
            c["x"] += c["v"] * dt
            if c["x"] > W + 40:
                c["x"] = -c["spr"].get_width() - 20
        for c in self.critters:
            c["x"] += c["v"] * dt
            if c["x"] > W + 100:
                c["x"] = -100
                c["y"] = self.rng.uniform(90, 260)
        th = self.th
        if th["volcano"]:
            vx, top = th["volcano"][1], th["volcano"][2]
            if th["embers"] and self.rng.random() < th["embers"] * dt:
                self.parts.append({"k": "ember", "x": vx + self.rng.uniform(-40, 40), "y": top, "vx": self.rng.uniform(-50, 50),
                                   "vy": self.rng.uniform(-170, -80), "age": 0.0, "life": self.rng.uniform(2.0, 3.6)})
            if th["smoke"] and self.rng.random() < 3.2 * dt:
                self.parts.append({"k": "smoke", "x": vx + self.rng.uniform(-30, 30), "y": top - 6, "vx": self.rng.uniform(8, 26),
                                   "vy": self.rng.uniform(-44, -26), "age": 0.0, "life": self.rng.uniform(5.0, 8.0)})
        if th.get("lava_ground") and self.rng.random() < 5 * dt:
            self.parts.append({"k": "ember", "x": self.rng.uniform(0, W), "y": GROUND_TOP + self.rng.uniform(10, 60), "vx": self.rng.uniform(-20, 20),
                               "vy": self.rng.uniform(-90, -40), "age": 0.0, "life": self.rng.uniform(1.0, 2.0)})
        for p in self.parts:
            p["age"] += dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
        self.parts = [p for p in self.parts if p["age"] < p["life"]]

    def draw(self, surf):
        t = self.t
        surf.blit(self.sky, (0, 0))
        for x, y, ph, size in self.stars:
            b = 0.55 + 0.45 * math.sin(t * 2.2 + ph)
            col = (int(120 + 135 * b), int(130 + 125 * b), int(160 + 95 * b))
            pygame.draw.circle(surf, col, (int(x), int(y)), size)
        for c in self.clouds:
            surf.blit(c["spr"], (int(c["x"]), int(c["y"])))
        for c in self.critters:
            if self.th["critter"] == "birds":
                self._bird(surf, c)
            else:
                self._ptero(surf, c)
        for p in self.parts:                      # smoke and embers float behind the hills
            u = p["age"] / p["life"]
            if p["k"] == "smoke":
                size = int((50 + u * 120) // 8 * 8)
                spr = soft_shadow(size, size, 90)
                spr.set_alpha(int(255 * (1 - u)))
                surf.blit(spr, (int(p["x"] - size / 2), int(p["y"] - size / 2)))
        if self.th["volcano"]:
            vx, top = self.th["volcano"][1], self.th["volcano"][2]
            flick = 1.0 + 0.12 * math.sin(t * 9) + 0.08 * math.sin(t * 23)
            strength = 1.0 if self.th["volcano"][3] else 0.45
            add_glow(surf, (vx, top), int(150 * flick), (int(255 * strength), int(110 * strength), int(40 * strength)), 1.8)
        for i, (layer, top, speed) in enumerate(self.layers):
            off = int(t * speed) % W
            surf.blit(layer, (-off, top))
            surf.blit(layer, (W - off, top))
            if i == 1:
                self._ember_pass(surf)
        surf.blit(self.ground, (0, GROUND_TOP - 8))
        for f in self.fireflies:
            fx = f[0] + math.sin(t * 0.6 * f[3] + f[2]) * 40
            fy = f[1] + math.cos(t * 0.5 * f[3] + f[2] * 2) * 26
            b = max(0.0, math.sin(t * 1.6 * f[3] + f[2]))
            if b > 0.05:
                add_glow(surf, (fx, fy), 14, (int(190 * b), int(255 * b), int(70 * b)), 1.4)

    def _ember_pass(self, surf):
        for p in self.parts:
            if p["k"] == "ember":
                u = p["age"] / p["life"]
                k = 1 - u
                add_glow(surf, (p["x"], p["y"]), 10, (int(255 * k), int(150 * k), int(50 * k)), 1.2)

    def draw_foreground(self, surf):
        surf.blit(self.fg, (0, self.fg_y))

    def _bird(self, surf, c):
        s = c["s"]
        flap = math.sin(self.t * 8 + c["ph"])
        x = c["x"]
        y = c["y"] + math.sin(self.t * 1.3 + c["ph"]) * 8
        col = (44, 66, 96)
        pts = [(x - 16 * s, y - 6 * s * flap - 2 * s), (x - 7 * s, y - 4 * s * flap - 7 * s), (x, y), (x + 7 * s, y - 4 * s * flap - 7 * s), (x + 16 * s, y - 6 * s * flap - 2 * s)]
        pygame.draw.lines(surf, col, False, pts, 3)

    def _ptero(self, surf, c):
        s = c["s"]
        flap = math.sin(self.t * 5 + c["ph"])
        x = c["x"]
        y = c["y"] + math.sin(self.t * 1.1 + c["ph"]) * 10
        col = lerp_color(self.th["near"][0], (0, 0, 0), 0.3)
        pygame.draw.polygon(surf, col, [(x + 8 * s, y - 3 * s), (x - 46 * s, y - 36 * s * flap - 4 * s), (x - 20 * s, y + 4 * s), (x - 6 * s, y + 8 * s)])
        pygame.draw.polygon(surf, col, [(x - 20 * s, y), (x + 20 * s, y - 5 * s), (x + 24 * s, y + 5 * s), (x - 16 * s, y + 8 * s)])
        pygame.draw.polygon(surf, col, [(x + 18 * s, y - 6 * s), (x + 46 * s, y - 1 * s), (x + 20 * s, y + 3 * s)])
        pygame.draw.polygon(surf, col, [(x + 16 * s, y - 5 * s), (x + 6 * s, y - 16 * s), (x + 8 * s, y - 2 * s)])
        pygame.draw.polygon(surf, col, [(x - 16 * s, y + 4 * s), (x - 34 * s, y + 10 * s), (x - 14 * s, y + 8 * s)])


# =============================================================================
#  PANELS, BUTTONS AND ICONS
# =============================================================================
def make_panel(w, h, radius=22, top=(255, 255, 255), bottom=(188, 220, 255), border=(0, 0, 0), bw=4):
    """A glossy rounded rectangle (white fading to light blue) with a black border."""
    s = 2
    W2, H2, R2 = w * s, h * s, radius * s
    surf = pygame.Surface((W2, H2), pygame.SRCALPHA)
    surf.fill(border + (0,))
    pygame.draw.rect(surf, border + (255,), (0, 0, W2, H2), border_radius=R2)
    ins = bw * s
    grad = vertical_gradient(W2 - 2 * ins, H2 - 2 * ins, [(0, top), (1, bottom)], alpha=True)
    mask = pygame.Surface(grad.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, grad.get_width(), grad.get_height()), border_radius=max(R2 - ins, 2))
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(grad, (ins, ins))
    pygame.draw.rect(surf, (96, 156, 255, 255), (ins, ins, W2 - 2 * ins, H2 - 2 * ins), 3 * s, border_radius=max(R2 - ins, 2))
    gloss = pygame.Surface((W2, H2), pygame.SRCALPHA)
    pygame.draw.rect(gloss, (255, 255, 255, 120), (ins + 6 * s, ins + 5 * s, W2 - 2 * ins - 12 * s, (H2 - 2 * ins) * 0.40),
                     border_radius=max(R2 - ins - 4 * s, 2))
    surf.blit(gloss, (0, 0))
    return pygame.transform.smoothscale(surf, (w, h)).convert_alpha()


def make_play_icon(size):
    pen = Pen(size, size, 3, bg=(0, 0, 0))
    tri = [(0.22 * size, 0.10 * size), (0.92 * size, 0.5 * size), (0.22 * size, 0.90 * size)]
    pen.poly_outline((40, 120, 255), tri, (0, 0, 0), 0.08 * size)
    pen.poly((130, 190, 255), [(0.30 * size, 0.24 * size), (0.70 * size, 0.46 * size), (0.30 * size, 0.46 * size)])
    return pen.finish()


def make_restart_icon(size):
    pen = Pen(size, size, 3, bg=(0, 0, 0))
    c = size / 2
    r = size * 0.30
    pts = [(c + math.cos(math.radians(a)) * r, c + math.sin(math.radians(a)) * r) for a in range(-40, 250, 10)]
    for p in pts:
        pen.circle((0, 0, 0), p[0], p[1], size * 0.13)
    end = pts[-1]
    head = [(end[0] - size * 0.20, end[1] - size * 0.10), (end[0] + size * 0.16, end[1] - size * 0.04), (end[0] - size * 0.02, end[1] + size * 0.22)]
    pen.poly_outline((40, 120, 255), head, (0, 0, 0), 0.06 * size)
    for p in pts:
        pen.circle((40, 120, 255), p[0], p[1], size * 0.085)
    return pen.finish()


# =============================================================================
#  GAME OBJECTS
# =============================================================================
RADIUS = {"apple": 32, "banana": 34, "grapes": 34, "bomb": 30, "shield": 34}   # how big each thing is for hits
FRUITS = ["apple", "banana", "grapes"]
FRUIT_COLORS = {"apple": [(255, 70, 70), (255, 150, 150)], "banana": [(255, 224, 60), (255, 246, 160)],
                "grapes": [(176, 96, 230), (222, 170, 255)]}
CONFETTI = [(255, 90, 90), (255, 214, 60), (90, 200, 255), (120, 230, 120), (210, 120, 255), (255, 150, 60)]


def make_rays(size=480):
    """Golden light rays (used behind the LEVEL banner)."""
    surf = pygame.Surface((size, size))
    c = size / 2
    n = 14
    for i in range(n):
        a0 = i * 2 * math.pi / n
        a1 = a0 + math.pi / n
        pygame.draw.polygon(surf, (255, 214, 110), [(c, c), (c + math.cos(a0) * c * 1.5, c + math.sin(a0) * c * 1.5),
                                                      (c + math.cos(a1) * c * 1.5, c + math.sin(a1) * c * 1.5)])
    surf.blit(glow_sprite(size // 2, (255, 255, 255), 1.0), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return surf.convert()


class Assets:
    """Builds every picture once, when the game starts."""

    def __init__(self):
        self.sprites = {"apple": make_apple(), "banana": make_banana(), "grapes": make_grapes(),
                        "bomb": make_bomb(), "shield": make_shield_item()}
        self.bubble = make_bubble(300)
        self.vignette = make_vignette()
        self.rays = make_rays()
        self.worlds = {key: World(key) for key in ("home", 1, 2, 3)}
        self._rot = {}
        for i in range(120):                    # draw the dinosaur's idle and run animation now, so the game never stutters
            render_dino(i / 24.0 + 0.001)
        for i in range(24):
            render_dino(0.0, run=True, phase=i / 24 * 2 * math.pi + 0.01)

    def rotated(self, kind, angle, step=6):
        q = int(round(angle / step)) % int(360 / step)
        key = (kind, q)
        if key not in self._rot:
            self._rot[key] = pygame.transform.rotozoom(self.sprites[kind], q * step, 1.0)
        return self._rot[key]


class Item:
    """One falling thing: a fruit, a bomb or a shield."""

    def __init__(self, kind, x, level):
        cfg = LEVELS[level]
        self.kind = kind
        self.base_x = x
        self.x = x
        self.y = -70.0
        self.vy = random.uniform(*cfg["speed"])
        self.vx = 0.0
        self.amp = 0.0
        self.freq = random.uniform(1.6, 2.8)
        self.phase = random.uniform(0, 6.28)
        if cfg["wobble"]:                       # level 3: things drift and zig-zag, so they are harder to catch
            self.vx = random.choice([-1, 1]) * random.uniform(40, 150)
            self.amp = random.uniform(30, 80)
        self.angle = random.uniform(0, 360)
        self.spin = random.uniform(-70, 70)
        self.age = 0.0
        self.radius = RADIUS[kind]

    def update(self, dt):
        self.age += dt
        self.y += self.vy * dt
        self.base_x += self.vx * dt
        if self.base_x < 70:
            self.base_x, self.vx = 70, abs(self.vx)
        elif self.base_x > W - 70:
            self.base_x, self.vx = W - 70, -abs(self.vx)
        self.x = clamp(self.base_x + math.sin(self.age * self.freq + self.phase) * self.amp, 40, W - 40)
        self.angle += self.spin * dt


class Particle:
    __slots__ = ("kind", "x", "y", "vx", "vy", "life", "age", "size", "color", "gravity", "drag", "angle", "spin")

    def __init__(self, kind, x, y, vx, vy, life, size, color, gravity=0.0, drag=0.0, spin=0.0):
        self.kind, self.x, self.y, self.vx, self.vy = kind, x, y, vx, vy
        self.life, self.age, self.size, self.color = life, 0.0, size, color
        self.gravity, self.drag, self.spin = gravity, drag, spin
        self.angle = random.uniform(0, 6.28)


class Effects:
    """Sparkles, explosions, splashes and confetti."""

    def __init__(self):
        self.items = []

    def add(self, *args, **kwargs):
        self.items.append(Particle(*args, **kwargs))
        if len(self.items) > 700:
            del self.items[:100]

    def clear(self):
        self.items = []

    def sparkle(self, x, y, colors, n=14, speed=300):
        for _ in range(n):
            a = random.uniform(0, 6.28)
            sp = random.uniform(0.35, 1.0) * speed
            self.add("glow", x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(0.4, 0.8), random.uniform(14, 24),
                     random.choice(colors), drag=2.5)
        for _ in range(max(n // 2, 3)):
            a = random.uniform(0, 6.28)
            sp = random.uniform(0.3, 1.0) * speed
            self.add("star", x, y, math.cos(a) * sp, math.sin(a) * sp - 60, random.uniform(0.5, 0.9), random.uniform(9, 16),
                     random.choice([(255, 244, 150), (255, 255, 255)]), gravity=260, drag=1.5, spin=random.uniform(-6, 6))

    def splash(self, x, y, color):
        for _ in range(12):
            self.add("dot", x, y, random.uniform(-190, 190), random.uniform(-300, -90), random.uniform(0.45, 0.85),
                     random.uniform(4, 9), color, gravity=900)

    def ring(self, x, y, color, size, life=0.5):
        self.add("ring", x, y, 0, 0, life, size, color)

    def explosion(self, x, y, big=True):
        scale = 1.0 if big else 0.55
        for _ in range(int(30 * scale) + 6):
            a = random.uniform(0, 6.28)
            sp = random.uniform(0.2, 1.0) * 560 * scale
            self.add("glow", x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(0.5, 1.1), random.uniform(26, 48) * scale,
                     random.choice([(255, 150, 40), (255, 210, 80), (255, 90, 30), (255, 255, 200)]), drag=2.2)
        for _ in range(int(20 * scale) + 4):
            a = random.uniform(0, 6.28)
            sp = random.uniform(0.3, 1.0) * 620 * scale
            self.add("dot", x, y, math.cos(a) * sp, math.sin(a) * sp - 160, random.uniform(0.6, 1.1), random.uniform(4, 9),
                     random.choice([(40, 40, 50), (90, 90, 100), (255, 170, 60)]), gravity=800)
        for _ in range(int(9 * scale) + 3):
            self.add("smoke", x + random.uniform(-30, 30), y + random.uniform(-20, 20), random.uniform(-50, 50),
                     random.uniform(-110, -30), random.uniform(1.0, 1.7), random.uniform(60, 110) * scale, (60, 60, 70))
        self.ring(x, y, (255, 200, 100), 280 * scale, 0.55)
        self.ring(x, y, (255, 255, 255), 170 * scale, 0.35)

    def confetti(self, x, y, n=60, speed=520, up=True):
        for _ in range(n):
            a = random.uniform(-math.pi, 0) if up else random.uniform(0, 6.28)
            sp = random.uniform(0.3, 1.0) * speed
            self.add("confetti", x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(1.8, 3.0), random.uniform(9, 15),
                     random.choice(CONFETTI), gravity=520, drag=0.7, spin=random.uniform(-9, 9))

    def update(self, dt):
        for p in self.items:
            p.age += dt
            p.vy += p.gravity * dt
            if p.drag:
                k = max(0.0, 1 - p.drag * dt)
                p.vx *= k
                p.vy *= k
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.angle += p.spin * dt
        self.items = [p for p in self.items if p.age < p.life]

    def draw(self, surf):
        for p in self.items:
            u = p.age / p.life
            x, y = int(p.x), int(p.y)
            if p.kind == "glow":
                k = round((1 - u) * 5) / 5          # only a few brightness steps, so the glow pictures can be re-used
                if k > 0:
                    add_glow(surf, (x, y), max(int(p.size * (1 - u * 0.5)), 4), (int(p.color[0] * k), int(p.color[1] * k), int(p.color[2] * k)), 1.3)
            elif p.kind == "dot":
                pygame.draw.circle(surf, p.color, (x, y), max(int(p.size * (1 - u * 0.6)), 1))
            elif p.kind == "star":
                s = p.size * (1 - u * 0.6)
                pygame.draw.polygon(surf, p.color, star_points(p.x, p.y, s, s * 0.45, p.angle))
            elif p.kind == "confetti":
                s = p.size * (1 - max(0.0, (u - 0.8) / 0.2))
                w, h = s, s * 0.6 * abs(math.cos(p.angle * 0.9)) + 1
                ca, sa = math.cos(p.angle), math.sin(p.angle)
                pts = [(p.x + dx * ca - dy * sa, p.y + dx * sa + dy * ca) for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]
                pygame.draw.polygon(surf, p.color, pts)
            elif p.kind == "smoke":
                size = int((p.size * (0.5 + u)) // 8 * 8) + 8
                spr = soft_shadow(size, size, 120)
                spr.set_alpha(int(255 * (1 - u)))
                surf.blit(spr, (x - size // 2, y - size // 2))
            elif p.kind == "ring":
                r = int(p.size * ease_out(u))
                if r > 4:
                    k = 1 - u
                    tmp = pygame.Surface((r * 2 + 12, r * 2 + 12))
                    pygame.draw.circle(tmp, (int(p.color[0] * k), int(p.color[1] * k), int(p.color[2] * k)), (r + 6, r + 6), r, max(int(10 * k), 2))
                    surf.blit(tmp, (x - r - 6, y - r - 6), special_flags=pygame.BLEND_RGB_ADD)


class FloatText:
    """A '+1' that floats up and fades away."""

    def __init__(self, text, x, y):
        self.text, self.x, self.y, self.age = text, x, y, 0.0
        self.life = 0.9


# =============================================================================
#  THE DINOSAUR CHARACTER  (position, dragging, animation state)
# =============================================================================
HIT_CIRCLES = [(98, 100, 46), (164, 38, 32), (84, 138, 26), (40, 104, 20)]   # body, head, legs, tail (in the dino picture)


class Dino:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = DINO_START_X + DINO_W / 2        # centre of the picture
        self.y = float(STAND_Y)                   # feet
        self.facing = 1
        self.held = False
        self.grab = (0.0, 0.0)
        self.speed = 0.0
        self.vxs = 0.0
        self.phase = 0.0
        self.blink = 0.0
        self.blink_timer = random.uniform(1.0, 3.0)
        self.chomp = 0.0
        self.anticipate = 0.0
        self.squash_t = 99.0
        self.state = "alive"        # alive / dead / cheer
        self.dead_t = 0.0
        self.cheer_t = 0.0

    def airborne(self):
        return self.y < STAND_Y - 8

    def circles(self):
        """Where the dinosaur can be touched, in screen coordinates."""
        left, top = self.x - DINO_W / 2, self.y - DINO_FOOT
        out = []
        for cx, cy, r in HIT_CIRCLES:
            if self.facing < 0:
                cx = DINO_W - cx
            out.append((left + cx, top + cy, r))
        return out

    def try_grab(self, pos):
        if self.state != "alive":
            return False
        for cx, cy, r in self.circles():
            if math.hypot(pos[0] - cx, pos[1] - cy) < r + 16:
                self.held = True
                self.grab = (pos[0] - self.x, pos[1] - self.y)
                return True
        return False

    def eat(self):
        self.chomp = 0.32
        self.squash_t = 0.0

    def die(self):
        self.state = "dead"
        self.dead_t = 0.0
        self.held = False

    def cheer(self):
        self.state = "cheer"
        self.cheer_t = 0.0
        self.held = False

    def update(self, dt, mouse):
        self.blink_timer -= dt
        if self.blink_timer <= 0:
            self.blink = 0.13
            self.blink_timer = random.uniform(2.0, 4.5)
        if self.blink > 0:
            self.blink -= dt
        self.chomp = max(0.0, self.chomp - dt)
        self.squash_t += dt
        if self.state == "alive":
            ox, oy = self.x, self.y
            if self.held:
                tx = clamp(mouse[0] - self.grab[0], 70, W - 70)
                ty = clamp(mouse[1] - self.grab[1], 190, H - 8)
                k = 1 - math.exp(-dt * 30)
                self.x += (tx - self.x) * k
                self.y += (ty - self.y) * k
            vx = (self.x - ox) / max(dt, 1e-4)
            vy = (self.y - oy) / max(dt, 1e-4)
            self.speed += (math.hypot(vx, vy * 0.6) - self.speed) * min(1.0, dt * 10)
            self.vxs += (vx - self.vxs) * min(1.0, dt * 8)
            if abs(self.vxs) > 70:
                self.facing = 1 if self.vxs > 0 else -1
            self.phase += self.speed * dt * 0.06
        elif self.state == "dead":
            self.dead_t += dt
        else:
            self.cheer_t += dt

    def draw(self, surf, t, scale=1.0):
        alive = self.state == "alive"
        run = alive and not self.airborne() and self.speed > 45
        dangle = self.state == "dead" or (alive and self.airborne())
        mouth = self.anticipate
        if self.chomp > 0:
            mouth = max(mouth, math.sin((1 - self.chomp / 0.32) * math.pi))
        if self.state == "cheer":
            mouth = 0.7
        img = render_dino(t, run, self.phase, self.blink > 0, mouth, self.state == "dead", dangle)
        sx, sy, hop = 1.0, 1.0, 0.0
        if alive and self.squash_t < 0.6:
            s = math.exp(-9 * self.squash_t) * math.sin(self.squash_t * 28) * 0.13
            sx, sy = 1 + s * 0.9, 1 - s
        elif self.state == "dead":
            p = clamp(self.dead_t / 0.5, 0.0, 1.0)
            sy = math.cos(p * math.pi)              # 1 -> -1 : the dino flips over onto its back
            hop = math.sin(p * math.pi) * 80 * scale
            if p >= 1:
                b = self.dead_t - 0.5
                hop = abs(math.sin(b * 9)) * 18 * math.exp(-b * 4) * scale
        elif self.state == "cheer":
            hop = abs(math.sin(self.cheer_t * 7)) * 28 * scale
        w = max(int(DINO_W * scale * sx), 2)
        h = max(int(DINO_H * scale * max(abs(sy), 0.04)), 2)
        if (w, h) != img.get_size():
            img = pygame.transform.smoothscale(img, (w, h))
        if sy < 0:
            img = pygame.transform.flip(img, False, True)
        if self.facing < 0:
            img = pygame.transform.flip(img, True, False)
        if self.state == "dead":
            top = self.y - 79 * scale - hop - h / 2
        else:
            top = self.y - DINO_FOOT * scale * max(abs(sy), 0.04) - hop
        surf.blit(img, (int(self.x - w / 2), int(top)))


# =============================================================================
#  BUTTONS
# =============================================================================
CLICK_STEPS_TIME = 0.55   # seconds the click animation lasts before the button does its job


def make_button_surface(w, h, label, size, icon):
    panel = make_panel(w, h, radius=int(h * 0.30), top=(255, 255, 255), bottom=(174, 212, 255), bw=5)
    gap = 14
    icon_s = None
    if icon == "play":
        icon_s = make_play_icon(int(h * 0.56))
    elif icon == "restart":
        icon_s = make_restart_icon(int(h * 0.56))
    icon_w = icon_s.get_width() + gap if icon_s else 0
    while True:                                   # make the text smaller until icon + text fit inside the button
        text = fancy_text(label, "title", size, (112, 186, 255), (16, 66, 214), outline_px=4, shadow=(0, 3), shadow_alpha=70)
        if text.get_width() + icon_w <= w - 90 or size <= 24:
            break
        size -= 4
    x = (w - (text.get_width() + icon_w)) // 2
    if icon_s:
        panel.blit(icon_s, (x, (h - icon_s.get_height()) // 2 - 2))
        x += icon_w
    panel.blit(text, (x, (h - text.get_height()) // 2 - 3))
    return panel


class Button:
    """A glossy button: breathes, glows when the mouse is over it, squashes and springs back when clicked."""

    def __init__(self, cx, cy, w, h, label, size, icon, on_press=None, on_done=None):
        self.cx, self.cy, self.w, self.h = cx, cy, w, h
        self.base = make_button_surface(w, h, label, size, icon)
        self.white = self.base.copy()
        self.white.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_ADD)    # same shape, all white
        self.on_press, self.on_done = on_press, on_done
        self.visible = False
        self.hover = 0.0
        self.press_t = None
        self.appear_t = 1.0
        self.t = random.uniform(0, 6)

    def show(self):
        self.visible = True
        self.press_t = None
        self.appear_t = 0.0

    def hide(self):
        self.visible = False
        self.press_t = None

    def busy(self):
        return self.press_t is not None

    def contains(self, pos):
        return abs(pos[0] - self.cx) <= self.w / 2 and abs(pos[1] - self.cy) <= self.h / 2

    def click(self, pos):
        if self.visible and not self.busy() and self.appear_t > 0.6 and self.contains(pos):
            self.press_t = 0.0
            if self.on_press:
                self.on_press(self)
            return True
        return False

    def scale(self):
        s = 1.0 + 0.02 * math.sin(self.t * 3.0) + 0.07 * self.hover
        if self.appear_t < 1.0:
            s *= ease_out_back(self.appear_t, 2.2)
        if self.press_t is not None:
            p = self.press_t
            if p < 0.1:
                s *= 1 - 0.14 * ease_out(p / 0.1)                         # pushed in
            else:
                q = p - 0.1
                s *= 1 - 0.14 * math.exp(-7 * q) * math.cos(14 * q)       # springs back with a wobble
        return s

    def update(self, dt, mouse):
        self.t += dt
        if self.appear_t < 1.0:
            self.appear_t = min(1.0, self.appear_t + dt / 0.5)
        target = 1.0 if (self.visible and not self.busy() and self.contains(mouse)) else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 14)
        if self.press_t is not None:
            self.press_t += dt
            if self.press_t >= CLICK_STEPS_TIME:
                self.press_t = None
                if self.on_done:
                    self.on_done()

    def draw(self, surf):
        if not self.visible:
            return
        s = self.scale()
        if s <= 0.03:
            return
        w, h = max(int(self.w * s), 2), max(int(self.h * s), 2)
        frame = self.base
        sweep = (self.t * 0.6) % 2.2          # a shiny streak sweeps across now and then
        if sweep < 1.0:
            sx = lerp(-self.w * 0.3, self.w * 1.1, sweep)
            streak = pygame.Surface(self.base.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(streak, (255, 255, 255, 130), [(sx + self.w * 0.10, 0), (sx + self.w * 0.24, 0),
                                                               (sx + self.w * 0.14, self.h), (sx, self.h)])
            streak.blit(self.white, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)   # keep the streak inside the button
            frame = self.base.copy()
            frame.blit(streak, (0, 0))
        img = pygame.transform.smoothscale(frame, (w, h))
        if self.press_t is not None and self.press_t < 0.25:
            img.fill((60, 60, 60, 0), special_flags=pygame.BLEND_RGBA_ADD)         # flashes brighter when pressed
        shadow = soft_shadow(int(w * 0.92) // 8 * 8, int(h * 0.55) // 8 * 8, 150)
        surf.blit(shadow, (int(self.cx - shadow.get_width() / 2), int(self.cy + h * 0.28)))
        if self.hover > 0.03:
            k = round(0.55 * self.hover * 12) / 12
            add_glow(surf, (self.cx, self.cy), int(max(w, h) * 0.75), (int(120 * k), int(190 * k), int(255 * k)), 1.6)
        surf.blit(img, (int(self.cx - w / 2), int(self.cy - h / 2)))


class Banner:
    """Big text that pops onto the screen ('LEVEL 2', 'GAME OVER', 'YOU WIN!')."""

    def __init__(self, text, sub, top, bottom, hold=None, rays=True, cy=300):
        self.text, self.sub, self.top, self.bottom = text, sub, top, bottom
        self.hold, self.rays, self.t, self.cy = hold, rays, 0.0, cy


GOLD = ((255, 246, 160), (255, 168, 28))
RED = ((255, 160, 150), (226, 38, 60))
LEVEL_TIPS = {1: "Catch the fruit - dodge the bombs!", 2: "The fruit falls faster!", 3: "Tricky fruit - and SHIELDS appear!"}


def draw_bar(surf, x, y, w, h, frac, c1, c2, ticks=()):
    pygame.draw.rect(surf, (0, 0, 0), (x - 3, y - 3, w + 6, h + 6), border_radius=h // 2 + 3)
    pygame.draw.rect(surf, (30, 46, 100), (x, y, w, h), border_radius=h // 2)
    fw = int(w * clamp(frac, 0.0, 1.0))
    if fw > 0:
        fw = max(fw, h)
        pygame.draw.rect(surf, c2, (x, y, fw, h), border_radius=h // 2)
        pygame.draw.rect(surf, c1, (x, y, fw, h * 0.62), border_radius=h // 2)
        pygame.draw.rect(surf, lerp_color(c1, (255, 255, 255), 0.55), (x + h * 0.4, y + h * 0.14, max(fw - h * 0.8, 1), max(h * 0.22, 1)), border_radius=3)
    for tk in ticks:
        tx = x + int(w * tk)
        pygame.draw.line(surf, (255, 255, 255), (tx, y - 1), (tx, y + h), 2)


# =============================================================================
#  THE GAME
# =============================================================================
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.canvas = pygame.Surface((W, H))
        self.fade_buf = pygame.Surface((W, H))
        self.iris = pygame.Surface((W, H), pygame.SRCALPHA)
        self.white = pygame.Surface((W, H))
        self.white.fill((255, 255, 255))
        self.black = pygame.Surface((W, H))
        self.running = True
        self.fullscreen = False
        self.t = 0.0
        self.mouse = (W // 2, H // 2)
        self.cursor = None
        self.audio = Audio()
        self.assets = Assets()
        self.fx = Effects()
        self.dino = Dino()
        self.home_dino = Dino()
        self.home_dino.x, self.home_dino.y = 250.0, STAND_Y + 12.0
        self.scene = "home"
        self.world = self.assets.worlds["home"]
        self.prev_world = None
        self.mix = 1.0
        self.trans = None
        self.banner = None
        self.float_texts = []
        self.shake = 0.0
        self.flash = 0.0
        self.dim = 0.0
        self.reset_play_state()
        self.play_btn = Button(W / 2, 410, 340, 118, "PLAY", 78, "play", self.on_play_press, self.on_play_done)
        self.restart_btn = Button(W / 2, 470, 400, 110, "RESTART", 62, "restart", self.on_button_press, self.on_restart_done)
        self.win_btn = Button(W / 2, 440, 660, 110, "START FROM LEVEL 1", 54, "restart", self.on_button_press, self.on_restart_done)
        self.play_btn.show()

    # ---------------------------------------------------------------- state
    def reset_play_state(self):
        self.score = 0
        self.level = 1
        self.items = []
        self.shield_t = 0.0
        self.shield_age = 0.0
        self.spawn_timer = 1.8
        self.bomb_grace = 3.0
        self.food_pop = 99.0
        self.level_pulse = 99.0
        self.dead_t = 0.0
        self.win_t = 0.0
        self.game_over_shown = False
        self.faint_played = False
        self.float_texts = []

    def buttons(self):
        return (self.play_btn, self.restart_btn, self.win_btn)

    def set_world(self, key, instant=False):
        new = self.assets.worlds[key]
        if new is self.world:
            return
        if instant:
            self.world, self.prev_world, self.mix = new, None, 1.0
        else:
            self.prev_world, self.world, self.mix = self.world, new, 0.0

    def set_fullscreen(self, on):
        if on == self.fullscreen:
            return
        try:
            pygame.display.toggle_fullscreen()
            self.fullscreen = on
        except Exception:
            pass
        self.screen = pygame.display.get_surface() or self.screen

    # ---------------------------------------------------------------- transitions
    def start_transition(self, kind, center_out, center_in, action, dur_out, dur_in):
        self.trans = {"kind": kind, "stage": "out", "t": 0.0, "dur_out": dur_out, "dur_in": dur_in,
                      "c_out": center_out, "c_in": center_in, "action": action}

    def update_transition(self, dt):
        tr = self.trans
        if not tr:
            return
        tr["t"] += dt
        if tr["stage"] == "out" and tr["t"] >= tr["dur_out"]:
            tr["action"]()                       # the screen is fully covered: switch scenes now
            tr["stage"], tr["t"] = "in", 0.0
        elif tr["stage"] == "in" and tr["t"] >= tr["dur_in"]:
            self.trans = None

    def draw_transition(self, surf):
        tr = self.trans
        if not tr:
            return
        if tr["stage"] == "out":
            cover = ease_in_out(tr["t"] / tr["dur_out"])
            center = tr["c_out"]
        else:
            cover = 1 - ease_in_out(tr["t"] / tr["dur_in"])
            center = tr["c_in"]
        if tr["kind"] == "fade":
            self.black.set_alpha(int(255 * cover))
            surf.blit(self.black, (0, 0))
            return
        max_r = math.hypot(W, H)
        r = max_r * (1 - cover)
        if r <= 0.5:
            surf.fill((0, 0, 0))
        elif r < max_r:
            self.iris.fill((0, 0, 0, 255))
            pygame.draw.circle(self.iris, (0, 0, 0, 0), center, int(r))
            surf.blit(self.iris, (0, 0))
            pygame.draw.circle(surf, (255, 255, 255), center, int(r), 6)
            pygame.draw.circle(surf, (120, 190, 255), center, int(r) + 6, 4)

    # ---------------------------------------------------------------- button actions
    def on_button_press(self, btn):
        self.audio.play("click")
        self.fx.sparkle(btn.cx, btn.cy, [(120, 190, 255), (255, 255, 255)], 10, 260)

    def on_play_press(self, btn):
        self.audio.play("click")
        self.fx.ring(btn.cx, btn.cy, (140, 200, 255), 300, 0.6)
        self.fx.ring(btn.cx, btn.cy, (255, 255, 255), 200, 0.4)
        self.fx.sparkle(btn.cx, btn.cy, [(255, 230, 120), (120, 200, 255), (255, 255, 255)], 26, 520)

    def on_play_done(self):
        self.audio.play("whoosh")
        self.start_transition("iris", (int(self.play_btn.cx), int(self.play_btn.cy)),
                              (DINO_START_X + DINO_W / 2, STAND_Y - 80), self.begin_game, 0.55, 0.85)

    def on_restart_done(self):
        self.audio.play("whoosh")
        self.start_transition("fade", None, None, self.begin_game, 0.3, 0.5)

    def begin_game(self):
        """Runs while the screen is covered: switches to the play scene."""
        if self.scene == "home":                  # full screen when you press PLAY (not again on every restart)
            self.set_fullscreen(True)
        self.reset_play_state()
        self.dino.reset()
        self.fx.clear()
        self.dim = 0.0
        self.restart_btn.hide()
        self.win_btn.hide()
        self.play_btn.hide()
        self.scene = "play"
        self.set_world(1, instant=True)
        self.banner = Banner("LEVEL 1", LEVEL_TIPS[1], GOLD[0], GOLD[1], hold=2.6)

    # ---------------------------------------------------------------- input
    def handle(self, e):
        if e.type == pygame.QUIT:
            self.running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_F11:
                self.set_fullscreen(not self.fullscreen)
            elif e.key == pygame.K_ESCAPE and self.fullscreen:
                self.set_fullscreen(False)
        elif e.type == pygame.MOUSEMOTION:
            self.mouse = e.pos
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.mouse = e.pos
            if self.trans:
                return
            for b in self.buttons():
                if b.click(e.pos):
                    return
            if self.scene == "play":
                self.dino.try_grab(e.pos)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.dino.held = False

    # ---------------------------------------------------------------- update
    def update(self, dt):
        self.t += dt
        self.world.update(dt)
        if self.prev_world is not None:
            self.prev_world.update(dt)
            self.mix += dt / 1.4
            if self.mix >= 1.0:
                self.prev_world, self.mix = None, 1.0
        self.shake = max(0.0, self.shake - 45 * dt)
        self.flash = max(0.0, self.flash - 2.2 * dt)
        for b in self.buttons():
            b.update(dt, self.mouse if not self.trans else (-999, -999))
        self.update_transition(dt)
        if self.scene == "home":
            self.home_dino.update(dt, self.mouse)
        else:
            self.update_play(dt)
        self.fx.update(dt)
        self.update_cursor()

    def update_cursor(self):
        kind = pygame.SYSTEM_CURSOR_ARROW
        if not self.trans:
            if any(b.visible and not b.busy() and b.contains(self.mouse) for b in self.buttons()):
                kind = pygame.SYSTEM_CURSOR_HAND
            elif self.scene == "play" and self.dino.held:
                kind = pygame.SYSTEM_CURSOR_SIZEALL
            elif self.scene == "play" and self.dino.state == "alive" and any(
                    math.hypot(self.mouse[0] - cx, self.mouse[1] - cy) < r + 16 for cx, cy, r in self.dino.circles()):
                kind = pygame.SYSTEM_CURSOR_HAND
        if kind != self.cursor:
            self.cursor = kind
            try:
                pygame.mouse.set_cursor(kind)
            except Exception:
                pass

    def spawn_pair(self):
        xs = []
        while len(xs) < 2:
            x = random.randint(70, W - 70)
            if all(abs(x - o) > 150 for o in xs):
                xs.append(x)
        for x in xs:
            self.items.append(Item(random.choice(FRUITS), x, self.level))

    def update_play(self, dt):
        d = self.dino
        cfg = LEVELS[self.level]
        d.update(dt, self.mouse)
        self.food_pop += dt
        self.level_pulse += dt
        if self.banner:
            self.banner.t += dt
            if self.banner.hold is not None and self.banner.t > self.banner.hold:
                self.banner = None
        for ft in self.float_texts:
            ft.age += dt
            ft.y -= 80 * dt
        self.float_texts = [f for f in self.float_texts if f.age < f.life]

        # ---- spawning (only while playing) ----
        if self.scene == "play":
            self.spawn_timer -= dt
            self.bomb_grace -= dt
            if self.spawn_timer <= 0:
                self.spawn_pair()
                self.spawn_timer += cfg["spawn_every"]
            if self.bomb_grace <= 0 and random.random() < cfg["bomb_rate"] * dt:
                self.items.append(Item("bomb", random.randint(70, W - 70), self.level))
            if (self.level == 3 and self.shield_t <= 0 and random.random() < SHIELD_RATE * dt
                    and not any(i.kind == "shield" for i in self.items)):
                self.items.append(Item("shield", random.randint(100, W - 100), self.level))

        # ---- shield timer ----
        if self.shield_t > 0:
            self.shield_t -= dt
            self.shield_age += dt
            if self.shield_t <= 0:
                self.fx.sparkle(d.x, d.y - 82, [(120, 190, 255), (255, 190, 100)], 16, 300)

        # ---- the dinosaur looks hungry when a fruit is close to its head ----
        d.anticipate = 0.0
        if self.scene == "play":
            head = d.circles()[1]
            for it in self.items:
                if it.kind in FRUITS and math.hypot(it.x - head[0], it.y - head[1]) < 190 and it.y < head[1] + 40:
                    d.anticipate = 0.55
                    break

        # ---- move everything and see what happened ----
        for it in self.items[:]:
            if it not in self.items:          # it was removed earlier in this same loop (win / game over)
                continue
            it.update(dt)
            if it.kind == "bomb" and random.random() < 40 * dt:
                self.fx.add("glow", it.x + 13, it.y - 68, random.uniform(-70, 70), random.uniform(-150, -50), 0.4, 9,
                            (255, 200, 90), gravity=240)
            if it.y >= FLOOR_Y:
                self.land(it)
                self.items.remove(it)
                continue
            if self.scene != "play":
                continue
            if it.kind == "bomb" and self.shield_t > 0:
                bx, by = d.x, d.y - 82
                if math.hypot(it.x - bx, it.y - by) < it.radius + 138:
                    self.fx.explosion(it.x, it.y, big=False)
                    self.fx.ring(bx, by, (120, 190, 255), 200, 0.4)
                    self.audio.play("puff")
                    self.shake = max(self.shake, 7)
                    self.items.remove(it)
                    continue
            for cx, cy, r in d.circles():
                if math.hypot(it.x - cx, it.y - cy) < it.radius + r:
                    self.items.remove(it)
                    if it.kind == "bomb":
                        self.kill(it)
                    elif it.kind == "shield":
                        self.get_shield(it)
                    else:
                        self.eat(it)
                    break
            if self.scene != "play":
                continue

        # ---- scene specific ----
        if self.scene == "dead":
            self.dead_t += dt
            self.dim += (0.5 - self.dim) * min(1.0, dt * 3)
            if self.dead_t > 0.55 and not self.faint_played:
                self.faint_played = True
                self.audio.play("faint")
            if self.dead_t > 1.3 and not self.game_over_shown:
                self.game_over_shown = True
                self.banner = Banner("GAME OVER", "You collected %d FOOD" % self.score, RED[0], RED[1], hold=None, rays=False, cy=235)
                self.restart_btn.show()
        elif self.scene == "win":
            self.win_t += dt
            self.dim += (0.25 - self.dim) * min(1.0, dt * 3)
            if random.random() < 40 * dt:
                self.fx.add("confetti", random.uniform(0, W), -20, random.uniform(-60, 60), random.uniform(120, 260), 5.0,
                            random.uniform(9, 15), random.choice(CONFETTI), gravity=60, drag=0.3, spin=random.uniform(-9, 9))
            if self.win_t > 1.6 and not self.win_btn.visible and not self.win_btn.busy():
                self.win_btn.show()

    def land(self, it):
        """A thing reached the ground."""
        if it.kind == "bomb":
            self.fx.explosion(it.x, FLOOR_Y, big=False)
            self.audio.play("puff")
        elif it.kind == "shield":
            self.fx.sparkle(it.x, FLOOR_Y - 10, [(120, 190, 255)], 8, 200)
        else:
            self.fx.splash(it.x, FLOOR_Y - 8, FRUIT_COLORS[it.kind][0])

    def eat(self, it):
        self.score += 1
        self.dino.eat()
        self.food_pop = 0.0
        self.audio.play("pop")
        self.fx.sparkle(it.x, it.y, FRUIT_COLORS[it.kind], 14, 320)
        self.float_texts.append(FloatText("+1", it.x, it.y - 30))
        new_level = 3 if self.score >= LEVEL_3_AT else 2 if self.score >= LEVEL_2_AT else 1
        if new_level > self.level:
            self.level_up(new_level)
        if self.score >= WIN_AT:
            self.win()

    def level_up(self, level):
        self.level = level
        self.level_pulse = 0.0
        self.set_world(level)
        self.banner = Banner("LEVEL %d" % level, LEVEL_TIPS[level], GOLD[0], GOLD[1], hold=2.6)
        self.flash = 0.7
        self.audio.play("levelup")
        self.fx.confetti(W / 2, 330, 90, 760)
        self.spawn_timer = max(self.spawn_timer, 1.3)
        self.bomb_grace = 2.5

    def get_shield(self, it):
        self.shield_t = SHIELD_SECONDS
        self.shield_age = 0.0
        self.audio.play("shield")
        self.fx.ring(self.dino.x, self.dino.y - 82, (120, 190, 255), 240, 0.5)
        self.fx.sparkle(it.x, it.y, [(120, 190, 255), (255, 190, 100), (255, 255, 255)], 20, 380)

    def kill(self, it):
        self.scene = "dead"
        self.dead_t = 0.0
        self.shield_t = 0.0
        self.dino.die()
        self.banner = None
        self.fx.explosion(it.x, it.y, big=True)
        self.shake = 24
        self.flash = 0.9
        self.audio.play("boom")

    def win(self):
        self.scene = "win"
        self.win_t = 0.0
        self.shield_t = 0.0
        self.dino.cheer()
        for it in self.items:
            self.fx.sparkle(it.x, it.y, [(255, 244, 150), (255, 255, 255)], 8, 240)
        self.items = []
        self.banner = Banner("YOU WIN!", "You collected %d FOOD!" % self.score, GOLD[0], GOLD[1], hold=None, cy=235)
        self.flash = 0.6
        self.audio.play("win")
        self.fx.confetti(W / 2, 420, 120, 820)

    # ---------------------------------------------------------------- drawing: world and things
    def draw_world(self, surf):
        if self.prev_world is None:
            self.world.draw(surf)
        else:
            self.prev_world.draw(surf)
            self.world.draw(self.fade_buf)
            self.fade_buf.set_alpha(int(255 * ease_in_out(self.mix)))
            surf.blit(self.fade_buf, (0, 0))

    def draw_dino_shadow(self, surf, d, scale=1.0):
        sy = max(STAND_Y + 12 if scale > 1 else STAND_Y, d.y)
        height = sy - d.y
        k = clamp(1 - height / 520, 0.35, 1.0)
        w = int(150 * k * scale) // 8 * 8
        sh = soft_shadow(w, max(int(w * 0.22) // 4 * 4, 8), 140)
        sh.set_alpha(int(255 * k))
        surf.blit(sh, (int(d.x - w / 2), int(sy - 8)))

    def draw_item(self, surf, it):
        a = self.assets
        r = it.radius
        # soft drop shadow behind the picture, and a shadow on the ground that grows as it gets close
        glow = soft_shadow(int(r * 2.3) // 4 * 4, int(r * 2.3) // 4 * 4, 70)
        surf.blit(glow, (int(it.x - glow.get_width() / 2 + 6), int(it.y - glow.get_height() / 2 + 10)))
        if it.kind == "bomb":
            spr = a.sprites["bomb"]
            surf.blit(spr, (int(it.x - 50), int(it.y - 74)))
            tx, ty = it.x + 13, it.y - 68
            fl = 17 + 6 * math.sin(self.t * 31 + it.phase) + 3 * math.sin(self.t * 47)
            add_glow(surf, (tx, ty - 8), 34 + int(4 * math.sin(self.t * 25)), (255, 150, 50), 1.6)
            pygame.draw.polygon(surf, (255, 120, 20), [(tx, ty - fl), (tx + 6, ty - fl * 0.35), (tx + 5, ty), (tx - 5, ty), (tx - 6, ty - fl * 0.35)])
            pygame.draw.polygon(surf, (255, 205, 60), [(tx, ty - fl * 0.78), (tx + 3.6, ty - fl * 0.3), (tx + 3, ty), (tx - 3, ty), (tx - 3.6, ty - fl * 0.3)])
            pygame.draw.polygon(surf, (255, 255, 220), [(tx, ty - fl * 0.45), (tx + 1.8, ty - fl * 0.15), (tx + 1.5, ty), (tx - 1.5, ty), (tx - 1.8, ty - fl * 0.15)])
        elif it.kind == "shield":
            add_glow(surf, (it.x, it.y), 62 + int(8 * math.sin(self.t * 6)), (60, 130, 255), 1.5)
            img = a.rotated("shield", math.sin(it.age * 3.2) * 10, 2)
            blit_center(surf, img, it.x, it.y)
        else:
            blit_center(surf, a.rotated(it.kind, it.angle), it.x, it.y)

    def draw_item_ground_shadow(self, surf, it):
        closeness = clamp(1 - (FLOOR_Y - it.y) / 560, 0.0, 1.0)
        w = int(lerp(26, 78, closeness)) // 6 * 6
        sh = soft_shadow(w, max(int(w * 0.28) // 2 * 2, 6), 120)
        sh.set_alpha(int(255 * (0.25 + 0.75 * closeness)))
        surf.blit(sh, (int(it.x - w / 2), int(FLOOR_Y + 6 - sh.get_height() / 2)))

    def draw_bubble(self, surf):
        if self.shield_t <= 0:
            return
        if self.shield_t < 1.2 and int(self.shield_t * 8) % 2 == 0:
            return                                       # blinks when about to run out
        pop = ease_out_back(self.shield_age / 0.3, 2.0)
        s = pop * (1 + 0.03 * math.sin(self.t * 6))
        size = max(int(300 * s), 4)
        img = pygame.transform.smoothscale(self.assets.bubble, (size, size))
        blit_center(surf, img, self.dino.x, self.dino.y - 82)

    def draw_play_scene(self, surf):
        self.draw_world(surf)
        self.draw_dino_shadow(surf, self.dino)
        for it in self.items:
            self.draw_item_ground_shadow(surf, it)
        for it in self.items:
            self.draw_item(surf, it)
        self.dino.draw(surf, self.t)
        self.draw_bubble(surf)
        self.fx.draw(surf)
        self.world.draw_foreground(surf)
        surf.blit(self.assets.vignette, (0, 0))

    # ---------------------------------------------------------------- drawing: home screen
    def draw_home_scene(self, surf):
        self.draw_world(surf)
        hd = self.home_dino
        self.draw_dino_shadow(surf, hd, 1.5)
        hd.draw(surf, self.t, 1.5)
        decor = [("apple", 340, 330, 0.0), ("banana", 1090, 300, 1.7), ("grapes", 990, 520, 3.1), ("bomb", 1160, 500, 4.4)]
        a = self.assets
        for kind, x, y, ph in decor:
            y += math.sin(self.t * 1.6 + ph) * 12
            if kind == "bomb":
                surf.blit(a.sprites["bomb"], (int(x - 50), int(y - 74)))
                tx, ty = x + 13, y - 68
                fl = 17 + 6 * math.sin(self.t * 31)
                add_glow(surf, (tx, ty - 8), 34, (255, 150, 50), 1.6)
                pygame.draw.polygon(surf, (255, 120, 20), [(tx, ty - fl), (tx + 6, ty - fl * 0.35), (tx + 5, ty), (tx - 5, ty), (tx - 6, ty - fl * 0.35)])
                pygame.draw.polygon(surf, (255, 205, 60), [(tx, ty - fl * 0.7), (tx + 3.6, ty - fl * 0.3), (tx + 3, ty), (tx - 3, ty), (tx - 3.6, ty - fl * 0.3)])
            else:
                blit_center(surf, a.rotated(kind, math.sin(self.t + ph) * 14, 2), x, y)
        self.world.draw_foreground(surf)
        surf.blit(a.vignette, (0, 0))

    def draw_home_ui(self, screen):
        t = self.t
        cx = W / 2
        title = fancy_text("THE DINO", "title", 170, (150, 214, 255), (24, 80, 226), outline=(6, 14, 56), outline_px=9,
                           shadow=(0, 10), shadow_alpha=150)
        s = 1 + 0.018 * math.sin(t * 2.2)
        ty = 156 + math.sin(t * 1.6) * 6
        add_glow(screen, (cx, ty), 380, (110, 60, 20), 2.0)
        img = pygame.transform.smoothscale(title, (int(title.get_width() * s), int(title.get_height() * s)))
        blit_center(screen, img, cx, ty)
        for i, (dx, dy, size, ph) in enumerate([(-390, -60, 26, 0), (400, -30, 20, 1.5), (-330, 70, 16, 3), (350, 80, 24, 4.5), (60, -118, 14, 2.2)]):
            k = 0.5 + 0.5 * math.sin(t * 3 + ph)
            pygame.draw.polygon(screen, (255, 244, 170), star_points(cx + dx, ty + dy, size * (0.5 + 0.5 * k), size * 0.22 * (0.5 + 0.5 * k), t * 0.5 + ph, 4))
        sub = fancy_text("CATCH THE FRUIT  -  DODGE THE BOMBS", "ui", 30, (255, 255, 255), (214, 232, 255), outline=(14, 20, 60), outline_px=3,
                         shadow=(0, 3), shadow_alpha=120)
        blit_center(screen, sub, cx, 270)
        foot = fancy_text("F11 = full screen", "ui", 18, (255, 255, 255), (220, 230, 255), outline=(14, 20, 60), outline_px=2, shadow=(0, 2), shadow_alpha=100)
        screen.blit(foot, (24, H - 40))

    # ---------------------------------------------------------------- drawing: HUD
    def draw_hud(self, screen):
        a = self.assets
        pw, ph = 340, 132                       # size of each panel
        # ---------- LEVEL panel (top left) ----------
        tmp = pygame.Surface((pw + 20, ph + 20), pygame.SRCALPHA)
        tmp.blit(self.hud_panel(pw, ph), (10, 10))
        label = fancy_text("LEVEL %d" % self.level, "title", 46, (112, 186, 255), (16, 66, 214), outline_px=3, shadow=(0, 3), shadow_alpha=80)
        tmp.blit(label, (34, 10 + 40 - label.get_height() // 2))
        for i in range(3):
            on = i < self.level
            col = (255, 206, 60) if on else (150, 160, 190)
            sx, sy = 10 + pw - 92 + i * 28, 10 + 40
            pygame.draw.polygon(tmp, (0, 0, 0), star_points(sx, sy, 14, 6.5, 0))
            pygame.draw.polygon(tmp, col, star_points(sx, sy, 11, 4.9, 0))
        lo, hi = {1: (0, LEVEL_2_AT), 2: (LEVEL_2_AT, LEVEL_3_AT), 3: (LEVEL_3_AT, WIN_AT)}[self.level]
        draw_bar(tmp, 34, 10 + 84, pw - 48, 22, (self.score - lo) / (hi - lo), (120, 232, 110), (46, 170, 70))
        count = fancy_text("%d / %d" % (self.score - lo, hi - lo), "ui", 15, (255, 255, 255), (255, 255, 255), outline=(10, 20, 60), outline_px=2, shadow=(0, 0), shadow_alpha=0)
        tmp.blit(count, (10 + pw // 2 - count.get_width() // 2, 10 + 84 + 11 - count.get_height() // 2))
        glow_u = clamp(self.level_pulse / 0.9, 0.0, 1.0)
        if self.level_pulse < 0.9:
            add_glow(screen, (24 + pw / 2, 18 + ph / 2), int(260 * math.sin(glow_u * math.pi)) + 8, (90, 120, 40), 1.6)
            k = 1 + 0.08 * math.sin(glow_u * math.pi)
            tmp = pygame.transform.smoothscale(tmp, (int(tmp.get_width() * k), int(tmp.get_height() * k)))
        blit_center(screen, tmp, 24 + pw / 2, 18 + ph / 2)

        # ---------- FOOD panel (top right) ----------
        tmp = pygame.Surface((pw + 20, ph + 20), pygame.SRCALPHA)
        tmp.blit(self.hud_panel(pw, ph), (10, 10))
        pop = clamp(self.food_pop / 0.4, 0.0, 1.0)
        bump = math.sin(pop * math.pi)                         # 0 -> 1 -> 0 right after catching a fruit
        icon = a.sprites["apple"]
        isz = int(62 * (1 + 0.28 * bump))
        icon = pygame.transform.smoothscale(icon, (isz, int(isz * icon.get_height() / icon.get_width())))
        blit_center(tmp, icon, 10 + 58, 10 + 52)
        food = fancy_text("FOOD", "title", 30, (112, 186, 255), (16, 66, 214), outline_px=3, shadow=(0, 2), shadow_alpha=80)
        tmp.blit(food, (10 + 106, 10 + 26 - food.get_height() // 2))
        col = ((255, 246, 150), (255, 160, 30)) if pop < 1.0 else ((112, 186, 255), (16, 66, 214))
        num = fancy_text(str(self.score), "title", 56, col[0], col[1], outline_px=4, shadow=(0, 3), shadow_alpha=90)
        base_w = num.get_width()
        ns = 1 + 0.35 * bump
        if ns != 1.0:
            num = pygame.transform.smoothscale(num, (int(num.get_width() * ns), int(num.get_height() * ns)))
        tmp.blit(num, (10 + 106, 10 + 66 - num.get_height() // 2))
        goal = fancy_text("/ %d" % WIN_AT, "title", 26, (190, 204, 236), (140, 158, 205), outline=(10, 20, 60), outline_px=2, shadow=(0, 2), shadow_alpha=60)
        tmp.blit(goal, (10 + 106 + base_w + 12, 10 + 76 - goal.get_height() // 2))
        draw_bar(tmp, 34, 10 + 98, pw - 48, 16, self.score / WIN_AT, (255, 224, 90), (255, 160, 40),
                 ticks=(LEVEL_2_AT / WIN_AT, LEVEL_3_AT / WIN_AT))
        blit_center(screen, tmp, W - 24 - pw / 2, 18 + ph / 2)

    def hud_panel(self, w, h):
        if not hasattr(self, "_hud_panel"):
            self._hud_panel = make_panel(w, h, radius=24)
        return self._hud_panel

    def draw_float_texts(self, screen):
        for ft in self.float_texts:
            u = ft.age / ft.life
            img = fancy_text(ft.text, "title", 54, (255, 250, 170), (255, 170, 30), outline_px=4, shadow=(0, 3), shadow_alpha=100)
            s = ease_out_back(min(u / 0.2, 1.0), 2.5)
            img = pygame.transform.smoothscale(img, (max(int(img.get_width() * s), 2), max(int(img.get_height() * s), 2)))
            img.set_alpha(int(255 * (1 - clamp((u - 0.55) / 0.45, 0.0, 1.0))))
            blit_center(screen, img, ft.x, ft.y)

    def draw_banner(self, screen):
        b = self.banner
        if not b:
            return
        t = b.t
        alpha = 1.0
        if b.hold is not None:
            alpha = 1 - clamp((t - (b.hold - 0.5)) / 0.5, 0.0, 1.0)
        pop = ease_out_back(t / 0.45, 2.4)
        cy = b.cy - (1 - alpha) * 40
        if b.rays and alpha > 0:
            rr = pygame.transform.rotozoom(self.assets.rays, t * 40, 1.6 * min(pop, 1.1))
            k = int(150 * alpha * clamp(t / 0.3, 0, 1))
            rr.fill((k, k, k, 255), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(rr, (int(W / 2 - rr.get_width() / 2), int(cy - rr.get_height() / 2)), special_flags=pygame.BLEND_RGB_ADD)
        text = fancy_text(b.text, "title", 150, b.top, b.bottom, outline=(20, 10, 40), outline_px=8, shadow=(0, 10), shadow_alpha=150)
        s = max(pop, 0.01) * (1 + 0.02 * math.sin(t * 5))
        img = pygame.transform.smoothscale(text, (max(int(text.get_width() * s), 2), max(int(text.get_height() * s), 2)))
        img.set_alpha(int(255 * alpha))
        blit_center(screen, img, W / 2, cy)
        if b.sub:
            sub = fancy_text(b.sub, "ui", 40, (255, 255, 255), (222, 236, 255), outline=(14, 20, 60), outline_px=3, shadow=(0, 3), shadow_alpha=120)
            sub = sub.copy()
            sub.set_alpha(int(255 * alpha * clamp((t - 0.25) / 0.3, 0.0, 1.0)))
            blit_center(screen, sub, W / 2, cy + 112)

    # ---------------------------------------------------------------- drawing: everything
    def draw(self):
        if self.scene == "home":
            self.draw_home_scene(self.canvas)
        else:
            self.draw_play_scene(self.canvas)
        screen = self.screen
        ox = oy = 0
        if self.shake > 0.5:
            ox = int(random.uniform(-self.shake, self.shake))
            oy = int(random.uniform(-self.shake, self.shake))
            screen.fill((0, 0, 0))
        screen.blit(self.canvas, (ox, oy))
        if self.scene == "home":
            self.draw_home_ui(screen)
            self.play_btn.draw(screen)
            self.fx.draw(screen)
        else:
            if self.dim > 0.01:
                self.black.set_alpha(int(255 * self.dim))
                screen.blit(self.black, (0, 0))
            self.draw_hud(screen)
            self.draw_float_texts(screen)
            self.draw_banner(screen)
            self.restart_btn.draw(screen)
            self.win_btn.draw(screen)
        if self.flash > 0.01:
            self.white.set_alpha(int(255 * min(self.flash, 1.0) * 0.8))
            screen.blit(self.white, (0, 0))
        self.draw_transition(screen)


# =============================================================================
#  START THE GAME
# =============================================================================
def main():
    pygame.mixer.pre_init(22050, -16, 2, 512)
    pygame.init()
    flags = pygame.SCALED | pygame.RESIZABLE
    try:
        screen = pygame.display.set_mode((W, H), flags, vsync=1)
    except Exception:
        screen = pygame.display.set_mode((W, H), flags)
    pygame.display.set_caption("THE DINO")

    # a quick loading screen while the pictures and sounds are being made
    screen.fill((20, 18, 60))
    font = pygame.font.Font(None, 56)
    text = font.render("Loading THE DINO...", True, (230, 236, 255))
    screen.blit(text, (W // 2 - text.get_width() // 2, H // 2 - text.get_height() // 2))
    pygame.display.flip()

    game = Game(screen)
    clock = pygame.time.Clock()
    while game.running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for event in pygame.event.get():
            game.handle(event)
        game.update(dt)
        game.draw()
        pygame.display.flip()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
