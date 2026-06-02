#!/usr/bin/env python
"""
DELVE  -  a roguelike for BlackBerry Q10 / Term49
Pure Python stdlib. Requires curses (built into Python on QNX/Linux).

Run:   python dungeon.py
Keys:  Arrow keys (metamode on Q10), or hjkl / wasd
       i = inventory   g = grab   . = wait   q = quit
"""
import curses
import random
import math
import sys
import os

# ═══════════════════════════════ CONSTANTS ═══════════════════════════════

VERSION   = '1.0'
MAP_W     = 70
MAP_H     = 32
MSG_LINES = 4

# Tile types
WALL  = '#'
FLOOR = '.'
STAIR = '>'
DOOR  = '+'

# Colors (pair numbers)
C_NORMAL  = 1
C_PLAYER  = 2
C_ENEMY   = 3
C_ITEM    = 4
C_GOLD    = 5
C_STAIR   = 6
C_WALL    = 7
C_DOOR    = 8
C_UI      = 9
C_MSG     = 10
C_DMGRED  = 11
C_HEALGRN = 12
C_DIM     = 13

# Enemy templates: (name, char, hp, atk, defense, xp, color, speed)
ENEMY_TYPES = [
    ('Rat',      'r', 6,  2, 0, 5,   C_ENEMY, 1),
    ('Goblin',   'g', 12, 4, 1, 15,  C_ENEMY, 1),
    ('Orc',      'O', 22, 7, 2, 30,  C_ENEMY, 1),
    ('Troll',    'T', 40, 10,4, 60,  C_DMGRED,2),
    ('Wraith',   'W', 18, 8, 3, 45,  C_DIM  ,1),
    ('Dragon',   'D', 60, 14,6, 120, C_DMGRED,1),
]
# which enemies appear on which floors (0-indexed floor)
FLOOR_ENEMIES = [
    [0,1],      # floor 1
    [0,1,2],    # floor 2
    [1,2,3],    # floor 3
    [2,3,4],    # floor 4
    [3,4,5],    # floor 5+
]

# Item templates: (name, char, color, kind, value)
ITEM_TYPES = [
    ('Health Potion', '!', C_HEALGRN, 'potion_hp',  20),
    ('Big Potion',    '!', C_HEALGRN, 'potion_hp',  50),
    ('Gold Coin',     '$', C_GOLD,    'gold',        0),
    ('Gold Pile',     '$', C_GOLD,    'gold',        0),
    ('Sword',         '/', C_ITEM,    'weapon',      3),
    ('Great Sword',   '/', C_ITEM,    'weapon',      6),
    ('Shield',        ']', C_ITEM,    'armor',       2),
    ('Chain Mail',    ']', C_ITEM,    'armor',       4),
]

FLOOR_ITEMS = [
    [0,2,4,6],
    [0,1,2,3,4,6],
    [0,1,2,3,4,5,6,7],
    [1,3,4,5,6,7],
    [1,3,5,7],
]

XP_TABLE = [0, 50, 120, 230, 400, 650, 1000, 1500, 2200, 3200]

# ═══════════════════════════════ DUNGEON GEN ═════════════════════════════

class Rect:
    def __init__(self, x, y, w, h):
        self.x1, self.y1 = x, y
        self.x2, self.y2 = x+w, y+h

    def center(self):
        return ((self.x1+self.x2)//2, (self.y1+self.y2)//2)

    def overlaps(self, other, margin=1):
        return (self.x1 - margin < other.x2 and
                self.x2 + margin > other.x1 and
                self.y1 - margin < other.y2 and
                self.y2 + margin > other.y1)


def generate_dungeon(floor_num):
    """Mixed dungeon: rooms+corridors + cave erosion patches."""
    grid = [[WALL]*MAP_W for _ in range(MAP_H)]
    rooms = []

    # ── rectangular rooms ──
    attempts = 0
    while len(rooms) < 12 and attempts < 200:
        attempts += 1
        w = random.randint(4, 12)
        h = random.randint(3, 8)
        x = random.randint(1, MAP_W - w - 1)
        y = random.randint(1, MAP_H - h - 1)
        r = Rect(x, y, w, h)
        if any(r.overlaps(other) for other in rooms):
            continue
        for ry in range(r.y1, r.y2):
            for rx in range(r.x1, r.x2):
                grid[ry][rx] = FLOOR
        rooms.append(r)

    # ── connect rooms with L-shaped corridors ──
    for i in range(1, len(rooms)):
        x1, y1 = rooms[i-1].center()
        x2, y2 = rooms[i].center()
        if random.random() < 0.5:
            _hcorridor(grid, x1, x2, y1)
            _vcorridor(grid, y1, y2, x2)
        else:
            _vcorridor(grid, y1, y2, x1)
            _hcorridor(grid, x1, x2, y2)

    # ── cave erosion patches (cellular automata, limited area) ──
    num_patches = random.randint(2, 5)
    for _ in range(num_patches):
        cx = random.randint(5, MAP_W-6)
        cy = random.randint(5, MAP_H-6)
        pr = random.randint(4, 9)
        # seed random cells
        for py in range(max(1,cy-pr), min(MAP_H-1,cy+pr)):
            for px in range(max(1,cx-pr), min(MAP_W-1,cx+pr)):
                if math.sqrt((px-cx)**2+(py-cy)**2) < pr:
                    if random.random() < 0.55:
                        grid[py][px] = FLOOR
        # one pass of smoothing
        for _ in range(2):
            new = [row[:] for row in grid]
            for py in range(1, MAP_H-1):
                for px in range(1, MAP_W-1):
                    n = sum(1 for dy in (-1,0,1) for dx in (-1,0,1)
                            if grid[py+dy][px+dx] == FLOOR)
                    if n >= 5: new[py][px] = FLOOR
                    elif n <= 2: new[py][px] = WALL
            grid = new

    # ── add some doors on corridor-room junctions ──
    for room in rooms:
        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            bx = room.x1 + dx
            by = room.y1 + dy
            if 0 < bx < MAP_W-1 and 0 < by < MAP_H-1:
                if grid[by][bx] == FLOOR and random.random() < 0.12:
                    grid[by][bx] = DOOR

    # player start = center of first room
    start = rooms[0].center() if rooms else (2, 2)

    # stairs = center of last room
    sx, sy = rooms[-1].center() if rooms else (MAP_W-3, MAP_H-3)
    grid[sy][sx] = STAIR

    return grid, start, rooms


def _hcorridor(grid, x1, x2, y):
    for x in range(min(x1,x2), max(x1,x2)+1):
        if 0 < y < MAP_H-1 and 0 < x < MAP_W-1:
            grid[y][x] = FLOOR

def _vcorridor(grid, y1, y2, x):
    for y in range(min(y1,y2), max(y1,y2)+1):
        if 0 < y < MAP_H-1 and 0 < x < MAP_W-1:
            grid[y][x] = FLOOR


def is_walkable(grid, x, y):
    if x < 0 or x >= MAP_W or y < 0 or y >= MAP_H:
        return False
    return grid[y][x] in (FLOOR, STAIR, DOOR)

# ═══════════════════════════════ ENTITIES ════════════════════════════════

class Entity:
    def __init__(self, x, y):
        self.x, self.y = x, y

class Player(Entity):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.hp     = 30
        self.max_hp = 30
        self.xp     = 0
        self.level  = 1
        self.gold   = 0
        self.atk    = 4
        self.defense= 1
        self.weapon = None
        self.armor  = None
        self.inventory = []   # list of Item
        self.floor  = 1

    def xp_to_next(self):
        if self.level >= len(XP_TABLE):
            return 99999
        return XP_TABLE[self.level]

    def gain_xp(self, amount):
        self.xp += amount
        msgs = []
        while self.level < len(XP_TABLE) and self.xp >= self.xp_to_next():
            self.level += 1
            self.max_hp += 8
            self.hp = min(self.hp + 8, self.max_hp)
            self.atk += 2
            self.defense += 1
            msgs.append('LEVEL UP! Now level {}.'.format(self.level))
        return msgs

    def total_atk(self):
        return self.atk + (self.weapon.value if self.weapon else 0)

    def total_def(self):
        return self.defense + (self.armor.value if self.armor else 0)

    def attack_roll(self):
        base = self.total_atk()
        return random.randint(max(1, base-2), base+3)

    def take_damage(self, raw):
        dmg = max(1, raw - self.total_def())
        self.hp -= dmg
        return dmg


class Enemy(Entity):
    def __init__(self, x, y, etype_idx):
        super().__init__(x, y)
        t = ENEMY_TYPES[etype_idx]
        self.name    = t[0]
        self.char    = t[1]
        self.hp      = t[2] + random.randint(-2, 4)
        self.max_hp  = self.hp
        self.atk     = t[3]
        self.defense = t[4]
        self.xp      = t[5]
        self.color   = t[6]
        self.speed   = t[7]
        self.alive   = True
        self._tick   = 0

    def attack_roll(self):
        return random.randint(max(1,self.atk-2), self.atk+2)

    def take_damage(self, raw):
        dmg = max(1, raw - self.defense)
        self.hp -= dmg
        if self.hp <= 0:
            self.alive = False
        return dmg

    def move_towards(self, tx, ty, grid, occupied):
        dx = 0 if tx == self.x else (1 if tx > self.x else -1)
        dy = 0 if ty == self.y else (1 if ty > self.y else -1)
        # try diagonal, then cardinal
        for nx, ny in [(self.x+dx, self.y+dy),
                       (self.x+dx, self.y),
                       (self.x,    self.y+dy)]:
            if is_walkable(grid, nx, ny) and (nx,ny) not in occupied:
                self.x, self.y = nx, ny
                return


class Item(Entity):
    def __init__(self, x, y, itype_idx):
        super().__init__(x, y)
        t = ITEM_TYPES[itype_idx]
        self.name  = t[0]
        self.char  = t[1]
        self.color = t[2]
        self.kind  = t[3]
        self.value = t[4]
        if self.kind == 'gold':
            self.value = random.randint(3, 25)
            self.name  = '{} gold'.format(self.value)
        self.picked = False

# ═══════════════════════════════ GAME STATE ══════════════════════════════

class Game:
    def __init__(self):
        self.player  = None
        self.grid    = None
        self.enemies = []
        self.items   = []
        self.messages= []   # (text, color)
        self.turn    = 0
        self.state   = 'playing'  # playing | inventory | dead | win
        self.inv_sel = 0
        self.floor   = 1

    def new_floor(self, floor_num, player=None):
        self.floor   = floor_num
        self.grid, start, rooms = generate_dungeon(floor_num)
        self.enemies = []
        self.items   = []

        if player is None:
            self.player = Player(start[0], start[1])
        else:
            self.player = player
            self.player.x, self.player.y = start
            self.player.floor = floor_num

        fi = min(floor_num-1, len(FLOOR_ENEMIES)-1)
        # spawn enemies (skip first room)
        for room in rooms[1:]:
            count = random.randint(1, 3)
            for _ in range(count):
                ex = random.randint(room.x1+1, room.x2-1)
                ey = random.randint(room.y1+1, room.y2-1)
                if self.grid[ey][ex] == FLOOR:
                    eidx = random.choice(FLOOR_ENEMIES[fi])
                    self.enemies.append(Enemy(ex, ey, eidx))

        # spawn items
        ii = min(floor_num-1, len(FLOOR_ITEMS)-1)
        item_count = random.randint(4, 9)
        for _ in range(item_count):
            room = random.choice(rooms)
            ix = random.randint(room.x1+1, room.x2-1)
            iy = random.randint(room.y1+1, room.y2-1)
            if self.grid[iy][ix] == FLOOR:
                iidx = random.choice(FLOOR_ITEMS[ii])
                self.items.append(Item(ix, iy, iidx))

        self.msg('Entered floor {}.'.format(floor_num), C_UI)

    def msg(self, text, color=C_MSG):
        self.messages.append((text, color))
        if len(self.messages) > 60:
            self.messages.pop(0)

    def last_msgs(self, n):
        return self.messages[-n:]

    def occupied(self):
        s = {(e.x, e.y) for e in self.enemies if e.alive}
        return s

    def enemy_at(self, x, y):
        for e in self.enemies:
            if e.alive and e.x == x and e.y == y:
                return e
        return None

    def item_at(self, x, y):
        for it in self.items:
            if not it.picked and it.x == x and it.y == y:
                return it
        return None

    def move_player(self, dx, dy):
        nx, ny = self.player.x + dx, self.player.y + dy
        if not (0 <= nx < MAP_W and 0 <= ny < MAP_H):
            return

        tile = self.grid[ny][nx]

        # door — open it
        if tile == DOOR:
            self.grid[ny][nx] = FLOOR
            self.msg('You open the door.')
            self.tick_enemies()
            return

        # attack enemy
        e = self.enemy_at(nx, ny)
        if e:
            dmg = e.take_damage(self.player.attack_roll())
            self.msg('You hit {} for {} dmg.'.format(e.name, dmg), C_DMGRED)
            if not e.alive:
                lvl_msgs = self.player.gain_xp(e.xp)
                self.msg('{} slain! +{} XP'.format(e.name, e.xp), C_GOLD)
                for m in lvl_msgs:
                    self.msg(m, C_HEALGRN)
            else:
                # enemy counter-attacks immediately
                edm = self.player.take_damage(e.attack_roll())
                self.msg('{} hits you for {}.'.format(e.name, edm), C_ENEMY)
            self.tick_enemies()
            return

        # walk
        if is_walkable(self.grid, nx, ny):
            self.player.x, self.player.y = nx, ny

            # auto-pickup gold
            it = self.item_at(nx, ny)
            if it and it.kind == 'gold':
                self.player.gold += it.value
                it.picked = True
                self.msg('Picked up {}.'.format(it.name), C_GOLD)

            # stairs
            if tile == STAIR:
                self.msg('Press > to descend.', C_STAIR)

            self.tick_enemies()

    def descend(self):
        if self.grid[self.player.y][self.player.x] == STAIR:
            if self.floor >= 10:
                self.state = 'win'
                return
            self.new_floor(self.floor + 1, self.player)
        else:
            self.msg('Not on stairs.')

    def grab(self):
        it = self.item_at(self.player.x, self.player.y)
        if not it:
            self.msg('Nothing here to pick up.')
            return
        if it.kind == 'gold':
            self.player.gold += it.value
            it.picked = True
            self.msg('Picked up {}.'.format(it.name), C_GOLD)
        else:
            self.player.inventory.append(it)
            it.picked = True
            self.msg('Picked up {}.'.format(it.name), C_ITEM)

    def use_item(self, idx):
        inv = [i for i in self.player.inventory if not i.picked or True]
        # filter to real inventory
        inv = self.player.inventory
        if idx >= len(inv): return
        it = inv[idx]
        if it.kind == 'potion_hp':
            heal = it.value
            old = self.player.hp
            self.player.hp = min(self.player.max_hp, self.player.hp + heal)
            actual = self.player.hp - old
            self.player.inventory.pop(idx)
            self.msg('Drank {}. Healed {} HP.'.format(it.name, actual), C_HEALGRN)
        elif it.kind == 'weapon':
            old = self.player.weapon
            self.player.weapon = it
            self.player.inventory.pop(idx)
            if old: self.player.inventory.append(old)
            self.msg('Equipped {}.'.format(it.name), C_ITEM)
        elif it.kind == 'armor':
            old = self.player.armor
            self.player.armor = it
            self.player.inventory.pop(idx)
            if old: self.player.inventory.append(old)
            self.msg('Equipped {}.'.format(it.name), C_ITEM)
        self.inv_sel = max(0, min(self.inv_sel, len(self.player.inventory)-1))

    def tick_enemies(self):
        self.turn += 1
        px, py = self.player.x, self.player.y
        occ = self.occupied()
        occ.add((px, py))

        for e in self.enemies:
            if not e.alive: continue
            e._tick += 1
            if e._tick < e.speed:
                continue
            e._tick = 0

            dist = abs(e.x-px) + abs(e.y-py)
            if dist <= 1 and not (e.x == px and e.y == py):
                # adjacent — attack player
                dmg = self.player.take_damage(e.attack_roll())
                self.msg('{} hits you for {}.'.format(e.name, dmg), C_ENEMY)
                if self.player.hp <= 0:
                    self.state = 'dead'
                    return
            elif dist <= 8:
                # chase
                occ.discard((e.x, e.y))
                e.move_towards(px, py, self.grid, occ)
                occ.add((e.x, e.y))
            else:
                # wander
                dx, dy = random.choice([(0,1),(0,-1),(1,0),(-1,0),(0,0)])
                nx2, ny2 = e.x+dx, e.y+dy
                if is_walkable(self.grid, nx2, ny2) and (nx2,ny2) not in occ:
                    occ.discard((e.x,e.y))
                    e.x, e.y = nx2, ny2
                    occ.add((e.x,e.y))

# ═══════════════════════════════ RENDERING ═══════════════════════════════

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_NORMAL,  curses.COLOR_WHITE,   -1)
    curses.init_pair(C_PLAYER,  curses.COLOR_CYAN,    -1)
    curses.init_pair(C_ENEMY,   curses.COLOR_RED,     -1)
    curses.init_pair(C_ITEM,    curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_GOLD,    curses.COLOR_YELLOW,  -1)
    curses.init_pair(C_STAIR,   curses.COLOR_GREEN,   -1)
    curses.init_pair(C_WALL,    curses.COLOR_WHITE,   -1)
    curses.init_pair(C_DOOR,    curses.COLOR_YELLOW,  -1)
    curses.init_pair(C_UI,      curses.COLOR_CYAN,    -1)
    curses.init_pair(C_MSG,     curses.COLOR_WHITE,   -1)
    curses.init_pair(C_DMGRED,  curses.COLOR_RED,     -1)
    curses.init_pair(C_HEALGRN, curses.COLOR_GREEN,   -1)
    curses.init_pair(C_DIM,     curses.COLOR_BLUE,    -1)

def cp(n, bold=False):
    attr = curses.color_pair(n)
    if bold: attr |= curses.A_BOLD
    return attr

def safe_addch(win, y, x, ch, attr=0):
    h, w = win.getmaxyx()
    if 0 <= y < h and 0 <= x < w-1:
        try: win.addch(y, x, ch, attr)
        except curses.error: pass

def safe_addstr(win, y, x, s, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h: return
    if x >= w: return
    s = s[:max(0, w-x-1)]
    try: win.addstr(y, x, s, attr)
    except curses.error: pass

def render(stdscr, game):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    p = game.player

    # camera — centre on player
    cam_x = p.x - w//2
    cam_y = p.y - (h - MSG_LINES - 2)//2
    cam_x = max(0, min(cam_x, MAP_W - w))
    cam_y = max(0, min(cam_y, MAP_H - (h - MSG_LINES - 2)))

    map_h = h - MSG_LINES - 2   # rows for map
    map_w = w

    # ── draw map ──
    for sy in range(map_h):
        my = sy + cam_y
        if my < 0 or my >= MAP_H: continue
        for sx in range(map_w):
            mx = sx + cam_x
            if mx < 0 or mx >= MAP_W: continue
            tile = game.grid[my][mx]
            if tile == WALL:
                safe_addch(stdscr, sy, sx, ord('#'), cp(C_WALL))
            elif tile == FLOOR:
                safe_addch(stdscr, sy, sx, ord('.'), cp(C_DIM))
            elif tile == STAIR:
                safe_addch(stdscr, sy, sx, ord('>'), cp(C_STAIR, True))
            elif tile == DOOR:
                safe_addch(stdscr, sy, sx, ord('+'), cp(C_DOOR, True))

    # ── items ──
    for it in game.items:
        if it.picked: continue
        sx, sy = it.x - cam_x, it.y - cam_y
        if 0 <= sx < map_w and 0 <= sy < map_h:
            safe_addch(stdscr, sy, sx, ord(it.char), cp(it.color, True))

    # ── enemies ──
    for e in game.enemies:
        if not e.alive: continue
        sx, sy = e.x - cam_x, e.y - cam_y
        if 0 <= sx < map_w and 0 <= sy < map_h:
            safe_addch(stdscr, sy, sx, ord(e.char), cp(e.color, True))

    # ── player ──
    px_s, py_s = p.x - cam_x, p.y - cam_y
    if 0 <= px_s < map_w and 0 <= py_s < map_h:
        safe_addch(stdscr, py_s, px_s, ord('@'), cp(C_PLAYER, True))

    # ── status bar ──
    bar_y = map_h
    bar = ' DELVE  FL:{:<2}  HP:{:>3}/{:<3}  ATK:{:<3}  DEF:{:<2}  XP:{:>4}/{:<4}  LVL:{:<2}  GOLD:{:<4}'.format(
        game.floor,
        p.hp, p.max_hp,
        p.total_atk(), p.total_def(),
        p.xp, p.xp_to_next(),
        p.level,
        p.gold
    )
    # hp color
    if p.hp <= p.max_hp // 4:
        hp_attr = cp(C_DMGRED, True)
    elif p.hp <= p.max_hp // 2:
        hp_attr = cp(C_GOLD, True)
    else:
        hp_attr = cp(C_HEALGRN, True)

    safe_addstr(stdscr, bar_y, 0, ' '*w, cp(C_UI))
    safe_addstr(stdscr, bar_y, 0, bar[:w-1], cp(C_UI, True))

    # equip line
    eq_y = bar_y + 1
    wpn  = p.weapon.name if p.weapon else 'fists'
    arm  = p.armor.name  if p.armor  else 'rags'
    inv_count = len(p.inventory)
    eq = ' WPN: {:<16} ARM: {:<16} INV: {} items  [i]nventory [g]rab [>]descend [q]uit'.format(
        wpn, arm, inv_count)
    safe_addstr(stdscr, eq_y, 0, ' '*w, cp(C_DIM))
    safe_addstr(stdscr, eq_y, 0, eq[:w-1], cp(C_DIM, True))

    # ── message log ──
    msgs = game.last_msgs(MSG_LINES)
    for i, (txt, col) in enumerate(msgs):
        my2 = eq_y + 1 + i
        safe_addstr(stdscr, my2, 1, txt[:w-2], cp(col))

    stdscr.refresh()


def render_inventory(stdscr, game):
    h, w = stdscr.getmaxyx()
    p = game.player
    inv = p.inventory

    # dim background
    stdscr.erase()

    box_w = min(50, w-4)
    box_h = min(len(inv)+8, h-4)
    bx = (w - box_w)//2
    by = (h - box_h)//2

    # border
    for y in range(by, by+box_h):
        safe_addstr(stdscr, y, bx, ' '*box_w, cp(C_UI))

    safe_addstr(stdscr, by,   bx+2, ' INVENTORY ', cp(C_PLAYER, True))
    safe_addstr(stdscr, by+1, bx+2,
        'WPN: {}  ARM: {}'.format(
            p.weapon.name if p.weapon else 'none',
            p.armor.name  if p.armor  else 'none'),
        cp(C_DIM, True))
    safe_addstr(stdscr, by+2, bx+2,
        'Gold: {}   HP: {}/{}'.format(p.gold, p.hp, p.max_hp),
        cp(C_GOLD, True))

    if not inv:
        safe_addstr(stdscr, by+4, bx+4, '(empty)', cp(C_DIM))
    else:
        for i, it in enumerate(inv):
            row = by + 4 + i
            if row >= by + box_h - 2: break
            sel = (i == game.inv_sel)
            prefix = '> ' if sel else '  '
            line = '{}{}) {} '.format(prefix, i+1, it.name)
            if it.kind == 'potion_hp':
                line += '(heals {})'.format(it.value)
            elif it.kind in ('weapon','armor'):
                line += '(+{} {})'.format(it.value, 'atk' if it.kind=='weapon' else 'def')
            attr = cp(C_PLAYER, True) if sel else cp(C_NORMAL)
            safe_addstr(stdscr, row, bx+2, line[:box_w-4], attr)

    safe_addstr(stdscr, by+box_h-2, bx+2,
        '[u]se  [arrow up/dn]  [i/esc] close', cp(C_DIM))
    stdscr.refresh()


def render_dead(stdscr, game):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    p = game.player
    lines = [
        '',
        ' ██╗   ██╗ ██████╗ ██╗   ██╗    ██████╗ ██╗███████╗██████╗ ',
        ' ╚██╗ ██╔╝██╔═══██╗██║   ██║    ██╔══██╗██║██╔════╝██╔══██╗',
        '  ╚████╔╝ ██║   ██║██║   ██║    ██║  ██║██║█████╗  ██║  ██║',
        '   ╚██╔╝  ██║   ██║██║   ██║    ██║  ██║██║██╔══╝  ██║  ██║',
        '    ██║   ╚██████╔╝╚██████╔╝    ██████╔╝██║███████╗██████╔╝',
        '    ╚═╝    ╚═════╝  ╚═════╝     ╚═════╝ ╚═╝╚══════╝╚═════╝ ',
        '',
        ' You fell on floor {}.'.format(game.floor),
        ' Reached level {}.'.format(p.level),
        ' Collected {} gold.'.format(p.gold),
        '',
        ' [r] play again   [q] quit',
    ]
    sy = (h - len(lines))//2
    for i, line in enumerate(lines):
        sx = max(0, (w - len(line))//2)
        safe_addstr(stdscr, sy+i, sx, line, cp(C_DMGRED, True))
    stdscr.refresh()


def render_win(stdscr, game):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    p = game.player
    lines = [
        '',
        ' ██╗   ██╗██╗ ██████╗████████╗ ██████╗ ██████╗ ██╗   ██╗██╗',
        ' ██║   ██║██║██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗╚██╗ ██╔╝██║',
        ' ██║   ██║██║██║        ██║   ██║   ██║██████╔╝ ╚████╔╝ ██║',
        ' ╚██╗ ██╔╝██║██║        ██║   ██║   ██║██╔══██╗  ╚██╔╝  ╚═╝',
        '  ╚████╔╝ ██║╚██████╗   ██║   ╚██████╔╝██║  ██║   ██║   ██╗',
        '   ╚═══╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝',
        '',
        ' You conquered all 10 floors!',
        ' Final level: {}   Gold: {}'.format(p.level, p.gold),
        '',
        ' [r] play again   [q] quit',
    ]
    sy = (h - len(lines))//2
    for i, line in enumerate(lines):
        sx = max(0, (w - len(line))//2)
        safe_addstr(stdscr, sy+i, sx, line, cp(C_HEALGRN, True))
    stdscr.refresh()


def render_title(stdscr):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    lines = [
        '',
        '    ██████╗ ███████╗██╗    ██╗   ██╗███████╗',
        '    ██╔══██╗██╔════╝██║    ██║   ██║██╔════╝',
        '    ██║  ██║█████╗  ██║    ██║   ██║█████╗  ',
        '    ██║  ██║██╔══╝  ██║    ╚██╗ ██╔╝██╔══╝  ',
        '    ██████╔╝███████╗███████╗╚████╔╝ ███████╗',
        '    ╚═════╝ ╚══════╝╚══════╝ ╚═══╝  ╚══════╝',
        '',
        '         a roguelike for BlackBerry Q10',
        '',
        '    Move:  arrow keys  (metamode + i/k/j/l on Q10)',
        '    Also:  wasd  or  hjkl',
        '    [g] grab item   [i] inventory   [>] descend stairs',
        '    [.] wait a turn   [q] quit',
        '',
        '              Press any key to begin',
    ]
    sy = max(0, (h - len(lines))//2)
    for i, line in enumerate(lines):
        sx = max(0, (w - len(line))//2)
        color = C_PLAYER if i < 8 else C_DIM if i > 10 else C_NORMAL
        bold  = i < 8
        safe_addstr(stdscr, sy+i, sx, line, cp(color, bold))
    stdscr.refresh()


# ═══════════════════════════════ MAIN LOOP ═══════════════════════════════

def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(100)
    init_colors()

    # title screen
    render_title(stdscr)
    while True:
        k = stdscr.getch()
        if k != -1:
            break

    game = Game()
    game.new_floor(1)

    DIR_KEYS = {
        curses.KEY_UP:    (0, -1),
        curses.KEY_DOWN:  (0,  1),
        curses.KEY_LEFT:  (-1, 0),
        curses.KEY_RIGHT: (1,  0),
        ord('k'): (0, -1), ord('j'): (0,  1),
        ord('h'): (-1, 0), ord('l'): (1,  0),
        ord('w'): (0, -1), ord('s'): (0,  1),
        ord('a'): (-1, 0), ord('d'): (1,  0),
    }

    while True:
        # ── draw ──
        if game.state == 'playing':
            render(stdscr, game)
        elif game.state == 'inventory':
            render_inventory(stdscr, game)
        elif game.state == 'dead':
            render_dead(stdscr, game)
        elif game.state == 'win':
            render_win(stdscr, game)

        k = stdscr.getch()
        if k == -1:
            continue

        # ── dead / win ──
        if game.state in ('dead', 'win'):
            if k == ord('r'):
                game = Game()
                game.new_floor(1)
            elif k == ord('q'):
                break
            continue

        # ── inventory ──
        if game.state == 'inventory':
            inv = game.player.inventory
            if k in (ord('i'), ord('q'), 27):   # esc
                game.state = 'playing'
            elif k in (curses.KEY_UP, ord('k'), ord('w')):
                game.inv_sel = max(0, game.inv_sel - 1)
            elif k in (curses.KEY_DOWN, ord('j'), ord('s')):
                game.inv_sel = min(len(inv)-1, game.inv_sel + 1)
            elif k == ord('u') and inv:
                game.use_item(game.inv_sel)
                game.state = 'playing'
            continue

        # ── playing ──
        if k == ord('q'):
            break
        elif k in DIR_KEYS:
            dx, dy = DIR_KEYS[k]
            game.move_player(dx, dy)
        elif k == ord('.'):
            game.tick_enemies()
        elif k == ord('g'):
            game.grab()
            game.tick_enemies()
        elif k == ord('i'):
            game.state = 'inventory'
            game.inv_sel = 0
        elif k == ord('>'):
            game.descend()


if __name__ == '__main__':
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    print('Thanks for playing DELVE!')
