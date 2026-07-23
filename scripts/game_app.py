import pygame
import argparse
import os
import csv
import json
import time
import random
import sys

# -----------------------------
# Optional LSL
# -----------------------------
try:
    from pylsl import StreamInfo, StreamOutlet, local_clock
    HAVE_LSL = True
except Exception:
    HAVE_LSL = False

# -----------------------------
# Argument parsing
# -----------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--session_dir", required=True)
parser.add_argument("--subject", required=True)
parser.add_argument("--session", required=True)
parser.add_argument("--protocol", required=True)
parser.add_argument("--run", default="01")
parser.add_argument("--marker_stream", default="GameMarkers")
parser.add_argument("--duration", type=int, default=5)
args = parser.parse_args()

# -----------------------------
# Output paths
# -----------------------------
os.makedirs(args.session_dir, exist_ok=True)
csv_path = os.path.join(args.session_dir, "event.csv")
json_path = os.path.join(args.session_dir, "lsl_stream.json")

# -----------------------------
# Initialize CSV
# -----------------------------
csv_file = open(csv_path, "w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["unix_time", "lsl_time", "event", "value", "trial"])

# -----------------------------
# LSL Marker outlet
# -----------------------------
if HAVE_LSL:
    info = StreamInfo(
        args.marker_stream,
        "Markers",
        1,
        0,
        "string",
        f"{args.subject}_{args.session}"
    )
    outlet = StreamOutlet(info)
else:
    outlet = None

lsl_metadata = []

def push_marker(event, value="", trial=0):
    unix_t = time.time()
    lsl_t = local_clock() if HAVE_LSL else ""
    if HAVE_LSL:
        outlet.push_sample([f"{event}:{value}"])
    csv_writer.writerow([unix_t, lsl_t, event, value, trial])
    csv_file.flush()
    lsl_metadata.append({
        "unix_time": unix_t,
        "lsl_time": lsl_t,
        "event": event,
        "value": value,
        "trial": trial
    })

# -----------------------------
# Pygame setup
# -----------------------------
pygame.init()
SCREEN_W, SCREEN_H = 800, 600
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Session Game")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 40)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)

CHAR_SIZE = 40
SPEED = 5

char_x = SCREEN_W // 2
char_y = SCREEN_H // 2

# -----------------------------
# Helper screens
# -----------------------------
def wait_for_space():
    screen.fill(BLACK)
    text = font.render("Press SPACE to start", True, WHITE)
    screen.blit(text, text.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))
    pygame.display.flip()

    while True:
        for e in pygame.event.get():
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                push_marker("START_BUTTON")
                return
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

def blank_screen(duration):
    screen.fill(BLACK)
    pygame.display.flip()
    time.sleep(duration)

def plus_screen(duration):
    screen.fill(BLACK)
    pygame.draw.line(screen, WHITE, (SCREEN_W//2, 0), (SCREEN_W//2, SCREEN_H), 3)
    pygame.draw.line(screen, WHITE, (0, SCREEN_H//2), (SCREEN_W, SCREEN_H//2), 3)
    pygame.draw.rect(
        screen, RED,
        (char_x-CHAR_SIZE//2, char_y-CHAR_SIZE//2, CHAR_SIZE, CHAR_SIZE)
    )
    pygame.display.flip()
    time.sleep(duration)

# -----------------------------
# Smooth deterministic movement
# -----------------------------
def move_character(direction, duration):
    global char_x, char_y
    start = time.time()

    while time.time() - start < duration:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        if direction == "LEFT":
            char_x -= SPEED
        elif direction == "RIGHT":
            char_x += SPEED
        elif direction == "UP":
            char_y -= SPEED
        elif direction == "DOWN":
            char_y += SPEED

        screen.fill(BLACK)
        pygame.draw.rect(
            screen, RED,
            (char_x-CHAR_SIZE//2, char_y-CHAR_SIZE//2, CHAR_SIZE, CHAR_SIZE)
        )
        pygame.display.flip()
        clock.tick(60)

# -----------------------------
# Response screen
# -----------------------------
def wait_for_arrow():
    screen.fill(BLACK)
    text = font.render("Press arrow key", True, WHITE)
    screen.blit(text, text.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))
    pygame.display.flip()

    while True:
        for e in pygame.event.get():
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_LEFT:
                    return "LEFT"
                if e.key == pygame.K_RIGHT:
                    return "RIGHT"
                if e.key == pygame.K_UP:
                    return "UP"
                if e.key == pygame.K_DOWN:
                    return "DOWN"
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

# -----------------------------
# MAIN SESSION
# -----------------------------
wait_for_space()
push_marker("SESSION_START", trial=0)

# Deterministic direction
seed = int(time.time())
random.seed(seed)
direction = random.choice(["LEFT", "RIGHT", "UP", "DOWN"])

push_marker("TRIAL_START", trial=1)
push_marker("STIM_DIR", direction, trial=1)

blank_screen(5)
plus_screen(5)
move_character(direction, 5)

push_marker("RESPONSE_WINDOW", trial=1)
response = wait_for_arrow()
push_marker("RESPONSE_KEY", response, trial=1)

push_marker("SESSION_END", trial=1)

# -----------------------------
# Save LSL JSON
# -----------------------------
with open(json_path, "w") as f:
    json.dump(lsl_metadata, f, indent=2)

csv_file.close()
pygame.quit()
