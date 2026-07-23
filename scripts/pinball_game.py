"""Pinball task with direct LSL markers and local event logging.

The game publishes a single-channel string stream using the Sheeg contract:
name=Markers, type=Markers, nominal rate=0.0, format=string.
"""

from __future__ import annotations

__version__ = "3.1.0-windows-pymunk7"

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import pygame
import pymunk
import pymunk.pygame_util
from pymunk import Vec2d

try:
    from pylsl import StreamInfo, StreamOutlet, local_clock

    HAVE_LSL = True
except ImportError:
    HAVE_LSL = False


def parse_args() -> argparse.Namespace:
    session_stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    parser = argparse.ArgumentParser(description="Sheeg pinball EEG task")
    parser.add_argument(
        "--session_dir",
        default=str(Path("sessions") / f"pinball_{session_stamp}"),
    )
    parser.add_argument("--subject", default="P001")
    parser.add_argument("--session", default=session_stamp)
    parser.add_argument("--protocol", default="Pinball")
    parser.add_argument("--run", default="01")
    parser.add_argument("--marker_stream", default="Markers")
    parser.add_argument(
        "--no_lsl",
        action="store_true",
        help="Run without an LSL outlet while still writing CSV/JSON logs.",
    )
    parser.add_argument(
        "--sound",
        default="",
        help="Optional path to a sound effect file.",
    )
    return parser.parse_args()


args = parse_args()
session_dir = Path(args.session_dir).resolve()
session_dir.mkdir(parents=True, exist_ok=True)
csv_path = session_dir / "event.csv"
json_path = session_dir / "lsl_stream.json"

csv_file = csv_path.open("w", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(
    ["unix_time", "lsl_time", "event", "value", "ball", "score"]
)

lsl_enabled = HAVE_LSL and not args.no_lsl
outlet = None
if lsl_enabled:
    source_id = f"pinball_{args.subject}_{args.session}_{os.getpid()}"
    stream_info = StreamInfo(
        name=args.marker_stream,
        type="Markers",
        channel_count=1,
        nominal_srate=0.0,
        channel_format="string",
        source_id=source_id,
    )
    outlet = StreamOutlet(stream_info)
elif not args.no_lsl:
    print(
        "WARNING: pylsl is not installed. The game will run and save local logs, "
        "but it will not publish LSL markers.",
        file=sys.stderr,
    )

event_log: list[dict[str, object]] = []
last_marker = ""
event_count = 0
json_warning_shown = False
score = 0
rounds = 3
current_ball = 0
session_end_sent = False


def save_json_log() -> None:
    """Keep a readable log available without interrupting gameplay on I/O errors."""
    global json_warning_shown

    try:
        # Write directly because Windows sync/antivirus tools can temporarily lock
        # a destination and reject an otherwise-safe atomic os.replace operation.
        with json_path.open("w", encoding="utf-8") as json_file:
            json.dump(event_log, json_file, indent=2)
    except OSError as exc:
        if not json_warning_shown:
            print(
                f"WARNING: JSON log could not be updated ({exc}). "
                "CSV and LSL logging will continue.",
                file=sys.stderr,
            )
            json_warning_shown = True


def push_marker(event: str, value: object = "") -> None:
    """Publish one LSL string sample and mirror it to CSV and JSON."""
    global event_count, last_marker

    value_text = str(value) if value != "" else ""
    payload = f"{event}:{value_text}" if value_text else event
    unix_time = time.time()
    lsl_time: float | str = local_clock() if lsl_enabled else ""

    if outlet is not None:
        outlet.push_sample([payload], timestamp=lsl_time)

    csv_writer.writerow(
        [unix_time, lsl_time, event, value_text, current_ball, score]
    )
    csv_file.flush()
    event_log.append(
        {
            "unix_time": unix_time,
            "lsl_time": lsl_time,
            "event": event,
            "value": value_text,
            "payload": payload,
            "ball": current_ball,
            "score": score,
        }
    )
    save_json_log()
    event_count += 1
    last_marker = payload
    print(f"MARKER {lsl_time}: {payload}")


pygame.init()
screen = pygame.display.set_mode((600, 620))
pygame.display.set_caption("PINBALL EEG TASK")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 26)
small_font = pygame.font.SysFont("Arial", 17)

sound_effect = None
if args.sound:
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        sound_effect = pygame.mixer.Sound(args.sound)
    except (FileNotFoundError, pygame.error) as exc:
        print(f"WARNING: sound disabled: {exc}", file=sys.stderr)


def play_sound() -> None:
    if sound_effect is not None:
        sound_effect.play()


space = pymunk.Space()
space.gravity = (0.0, 900.0)
draw_options = pymunk.pygame_util.DrawOptions(screen)
balls: list[pymunk.Shape] = []

# Playfield walls
static_lines = [
    pymunk.Segment(space.static_body, (120, 480), (50, 50), 2.0),
    pymunk.Segment(space.static_body, (480, 480), (545, 110), 2.0),
    pymunk.Segment(space.static_body, (50, 50), (300, 0), 2.0),
    pymunk.Segment(space.static_body, (300, 0), (550, 50), 2.0),
    pymunk.Segment(space.static_body, (510, 480), (580, 90), 2.0),
    pymunk.Segment(space.static_body, (580, 90), (550, 50), 2.0),
    pymunk.Segment(space.static_body, (480, 480), (510, 480), 2.0),
    pymunk.Segment(space.static_body, (120, 480), (140, 500), 4.0),
    pymunk.Segment(space.static_body, (480, 480), (462, 495), 2.0),
]
for line in static_lines:
    line.elasticity = 0.7
    line.filter = pymunk.ShapeFilter(group=1)
space.add(*static_lines)

# Flippers
flipper_vertices = [(20, -20), (-132, 0), (20, 20)]
flipper_mass = 100
flipper_moment = pymunk.moment_for_poly(flipper_mass, flipper_vertices)

r_flipper_body = pymunk.Body(flipper_mass, flipper_moment)
r_flipper_body.position = 450, 500
r_flipper_shape = pymunk.Segment(r_flipper_body, (0, 0), (-116, 0), 14)
space.add(r_flipper_body, r_flipper_shape)
r_joint_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
r_joint_body.position = r_flipper_body.position
space.add(
    pymunk.PinJoint(r_flipper_body, r_joint_body, (0, 0), (0, 0)),
    pymunk.DampedRotarySpring(
        r_flipper_body, r_joint_body, 0.0, 20_000_000, 900_000
    ),
)

l_flipper_body = pymunk.Body(flipper_mass, flipper_moment)
l_flipper_body.position = 150, 500
l_flipper_shape = pymunk.Segment(l_flipper_body, (0, 0), (116, 0), 14)
space.add(l_flipper_body, l_flipper_shape)
l_joint_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
l_joint_body.position = l_flipper_body.position
space.add(
    pymunk.PinJoint(l_flipper_body, l_joint_body, (0, 0), (0, 0)),
    pymunk.DampedRotarySpring(
        l_flipper_body, l_joint_body, 0.0, 20_000_000, 900_000
    ),
)

r_flipper_shape.filter = pymunk.ShapeFilter(group=1)
l_flipper_shape.filter = pymunk.ShapeFilter(group=1)
r_flipper_shape.elasticity = l_flipper_shape.elasticity = 0.4

# Round bumpers
round_bumper_positions = [(230, 100), (370, 100), (300, 140)]
round_bumpers = []
for collision_type, position in enumerate(round_bumper_positions, start=3):
    bumper_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    bumper_body.position = position
    bumper_shape = pymunk.Circle(bumper_body, 20)
    bumper_shape.elasticity = 1.5
    bumper_shape.collision_type = collision_type
    bumper_shape.color = (31, 163, 5, 255)
    space.add(bumper_body, bumper_shape)
    round_bumpers.append(bumper_shape)

# Triangular bumpers
left_triangle_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
left_triangle_body.position = (100, 240)
left_triangle = pymunk.Poly(
    left_triangle_body, [(10, -20), (90, 120), (0, 90)]
)
left_triangle.elasticity = 1.3
left_triangle.collision_type = 6
left_triangle.color = (191, 48, 48, 255)
space.add(left_triangle_body, left_triangle)

right_triangle_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
right_triangle_body.position = (500, 240)
right_triangle = pymunk.Poly(
    right_triangle_body, [(-10, -20), (-90, 120), (0, 90)]
)
right_triangle.elasticity = 1.3
right_triangle.collision_type = 7
right_triangle.color = (191, 48, 48, 255)
space.add(right_triangle_body, right_triangle)

bumper_shapes = round_bumpers + [left_triangle, right_triangle]
default_bumper_colors = [
    (31, 163, 5, 255),
    (31, 163, 5, 255),
    (31, 163, 5, 255),
    (191, 48, 48, 255),
    (191, 48, 48, 255),
]

ballbody: pymunk.Body | None = None


def add_ball() -> None:
    global ballbody, current_ball

    current_ball += 1
    mass = 1
    radius = 14
    inertia = pymunk.moment_for_circle(mass, 0, radius, (0, 0))
    ballbody = pymunk.Body(mass, inertia)
    ballbody.position = 500, 460
    ball_shape = pymunk.Circle(ballbody, radius, (0, 0))
    ball_shape.elasticity = 0.90
    ball_shape.collision_type = 0
    space.add(ballbody, ball_shape)
    balls.append(ball_shape)
    push_marker("BALL_SPAWN", current_ball)


def handle_bumper_hit(bumper_number: int, shape: pymunk.Shape) -> bool:
    global score

    score += 10
    shape.color = (0, 255, 0, 255) if bumper_number <= 3 else (255, 0, 0, 255)
    play_sound()
    push_marker("BUMPER_HIT", bumper_number)
    push_marker("SCORE", score)
    return True


def make_hit_handler(bumper_number: int, shape: pymunk.Shape):
    def handler(_arbiter, _space, _data):
        return handle_bumper_hit(bumper_number, shape)

    return handler


def make_separate_handler(shape: pymunk.Shape, default_color):
    def handler(_arbiter, _space, _data):
        shape.color = default_color

    return handler


for bumper_number, (collision_type, bumper_shape, default_color) in enumerate(
    zip(range(3, 8), bumper_shapes, default_bumper_colors), start=1
):
    begin_callback = make_hit_handler(bumper_number, bumper_shape)
    separate_callback = make_separate_handler(bumper_shape, default_color)
    space.on_collision(
        0,
        collision_type,
        begin=begin_callback,
        separate=separate_callback,
    )


def ask_restart() -> bool:
    """Display a keyboard-controlled restart prompt without pyautogui."""
    while True:
        screen.fill((10, 20, 28))
        game_over_text = font.render("GAME OVER", True, (255, 90, 90))
        restart_text = small_font.render(
            "Press Y to restart or N/Esc to finish", True, (255, 255, 255)
        )
        screen.blit(game_over_text, game_over_text.get_rect(center=(300, 275)))
        screen.blit(restart_text, restart_text.get_rect(center=(300, 325)))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    return True
                if event.key in (pygame.K_n, pygame.K_ESCAPE):
                    return False
        clock.tick(30)


def reset_game() -> None:
    global score, rounds, current_ball

    for ball in list(balls):
        space.remove(ball.body, ball)
        balls.remove(ball)
    score = 0
    rounds = 3
    current_ball = 0
    push_marker("GAME_RESTART")
    add_ball()


push_marker("SESSION_START", f"subject={args.subject};run={args.run}")
add_ball()
running = True

try:
    while running:
        screen.fill(pygame.Color("white"))
        pygame.draw.rect(screen, (11, 156, 136), (0, 550, 600, 70))

        score_surface = font.render(f"Score: {score}", True, (240, 255, 240))
        balls_surface = font.render(
            f"Balls: {rounds}", True, (240, 255, 240)
        )
        lsl_status = "LSL: connected" if lsl_enabled else "LSL: local log only"
        status_color = (210, 255, 210) if lsl_enabled else (255, 225, 160)
        status_surface = small_font.render(
            f"{lsl_status} | Events: {event_count}", True, status_color
        )
        marker_surface = small_font.render(
            f"Last: {last_marker[:58]}", True, (240, 255, 240)
        )
        screen.blit(score_surface, (18, 552))
        screen.blit(balls_surface, (430, 552))
        screen.blit(status_surface, (18, 583))
        screen.blit(marker_surface, (250, 583))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                screenshot_path = session_dir / f"pinball_{timestamp}.png"
                pygame.image.save(screen, str(screenshot_path))
                push_marker("SCREENSHOT", screenshot_path.name)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RIGHT:
                r_flipper_body.apply_impulse_at_local_point(
                    Vec2d.unit() * -40_000, (-100, 0)
                )
                play_sound()
                push_marker("FLIPPER_PRESS", "RIGHT")
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_LEFT:
                l_flipper_body.apply_impulse_at_local_point(
                    Vec2d.unit() * 40_000, (-100, 0)
                )
                play_sound()
                push_marker("FLIPPER_PRESS", "LEFT")
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if (
                    ballbody is not None
                    and ballbody.position.x > 494
                    and ballbody.position.y < 465
                ):
                    ballbody.apply_impulse_at_local_point(
                        Vec2d.unit() * -1150, (0, 0)
                    )
                    play_sound()
                    push_marker("BALL_LAUNCH", current_ball)

        space.debug_draw(draw_options)

        r_flipper_body.position = 450, 500
        l_flipper_body.position = 150, 500
        r_flipper_body.velocity = l_flipper_body.velocity = (0, 0)

        to_remove = []
        for ball in balls:
            if ball.body.position.get_distance((300, 300)) > 1000:
                to_remove.append(ball)

        for ball in to_remove:
            push_marker("BALL_LOST", current_ball)
            space.remove(ball.body, ball)
            balls.remove(ball)
            rounds -= 1

            if rounds <= 0:
                rounds = 0
                push_marker("GAME_OVER", score)
                if ask_restart():
                    reset_game()
                else:
                    running = False
            else:
                add_ball()

        timestep = 1.0 / 60.0 / 5.0
        for _ in range(5):
            space.step(timestep)

        pygame.display.flip()
        clock.tick(50)
        pygame.display.set_caption(
            f"PINBALL EEG TASK | FPS: {clock.get_fps():.1f}"
        )
finally:
    if not session_end_sent:
        push_marker("SESSION_END", score)
        session_end_sent = True
    csv_file.close()
    pygame.quit()

    print(f"Session files saved in: {session_dir}")
    print(f"CSV events: {csv_path}")
    print(f"JSON events: {json_path}")
