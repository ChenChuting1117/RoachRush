import pygame
import sys
import random
import os

# 初始化显示与字体
pygame.display.init()
pygame.font.init()

# 游戏窗口设置
SCREEN_WIDTH = 1067
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
# Set both window title and iconified title (helps consistency on macOS/Dock)
pygame.display.set_caption("Roach Rush", "Roach Rush")

# 颜色
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# 工具函数：为图像添加描边
def create_outline(image, color=(255, 255, 255, 255), thickness=1):
    """Return a new Surface with a colored outline around the given image.

    - image: source Surface (with alpha)
    - color: RGBA outline color
    - thickness: outline radius in pixels
    """
    # Create a mask from the source alpha
    mask = pygame.mask.from_surface(image)
    # Render the mask as a solid-colored silhouette with alpha
    silhouette = mask.to_surface(setcolor=color, unsetcolor=(0, 0, 0, 0))
    silhouette = silhouette.convert_alpha()

    w, h = image.get_size()
    result = pygame.Surface((w + 2 * thickness, h + 2 * thickness), pygame.SRCALPHA)

    # Blit the silhouette in a filled circle of offsets to approximate a smooth outline
    for dx in range(-thickness, thickness + 1):
        for dy in range(-thickness, thickness + 1):
            if dx * dx + dy * dy <= thickness * thickness:
                result.blit(silhouette, (dx + thickness, dy + thickness))

    # Draw original image on top, centered
    result.blit(image, (thickness, thickness))
    return result

# 状态
INTRO = -1
PLAYING = 0
WIN = 1
LOSE = 2


class Animation:
    def __init__(self, frames, frame_duration, loop=True):
        self.frames = frames
        self.frame_duration = frame_duration
        self.loop = loop
        self.current_frame = 0
        self.animation_timer = 0
        self.finished = False

    def reset(self):
        self.current_frame = 0
        self.animation_timer = 0
        self.finished = False

    def update(self, dt):
        if self.finished and not self.loop:
            return
        self.animation_timer += dt
        if self.animation_timer >= self.frame_duration:
            self.animation_timer = 0
            if self.loop:
                self.current_frame = (self.current_frame + 1) % len(self.frames)
            else:
                if self.current_frame < len(self.frames) - 1:
                    self.current_frame += 1
                else:
                    self.finished = True

    def get_current_frame(self):
        return self.frames[self.current_frame]


class Cockroach:
    def __init__(self, game):
        self._game = game
        # 走路帧
        walk_frames = []
        for i in range(1, 9):
            img = pygame.image.load(f"images/cockroach/walk/cockroach_walk_{i}.png").convert_alpha()
            # 规范 alpha
            pixels = pygame.surfarray.pixels_alpha(img)
            pixels[pixels > 0] = 255
            del pixels
            walk_frames.append(img)
        self.walk_anim = Animation(walk_frames, 100)

        # 震动两帧
        self.shake_frame1 = pygame.image.load("images/cockroach/shake/cockroach_shake_1.png").convert_alpha()
        self.shake_frame2 = pygame.image.load("images/cockroach/shake/cockroach_shake_2.png").convert_alpha()
        self.shake_frame_index = 0
        self.shake_timer = 0
        self.shake_frame_duration = 25

        # 其他图片
        self.win_image = pygame.image.load("images/cockroach/cockroach_win.png").convert_alpha()
        self.idle_image = pygame.image.load("images/cockroach/cockroach_idle.png").convert_alpha()
        # 胜利描边版本（2px白色）
        try:
            # 不透明白色描边，1px 厚度
            self.win_image_outlined = create_outline(self.win_image, (255, 255, 255, 255), 1)
        except Exception:
            # 兜底：若描边生成失败则回退原图
            self.win_image_outlined = self.win_image

        # 尺寸与位置（逻辑尺寸+居中绘制）
        self.width = 155
        self.height = 195
        self.x = 50
        self.y = SCREEN_HEIGHT - self.height - 50
        self.speed = 3  # slower walking speed (was 5)

        # 状态
        self.is_moving = False
        self.is_hiding = False
        self.game_started = False
        self._last_state = None

    def move(self, keys):
        old_x = self.x
        self.is_hiding = keys[pygame.K_SPACE]
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.game_started = True
        if not self.is_hiding:
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.x += self.speed
        self.x = max(0, min(self.x, SCREEN_WIDTH - self.width))
        self.is_moving = (old_x != self.x) and not self.is_hiding

    def update(self, dt, game_state):
        if game_state == LOSE and self._last_state != LOSE:
            self.shake_timer = 0
            self.shake_frame_index = 0

        if game_state == LOSE:
            self.shake_timer += dt
            if self.shake_timer >= self.shake_frame_duration:
                self.shake_timer = 0
                self.shake_frame_index = 1 - self.shake_frame_index
        elif game_state == PLAYING:
            if self.is_moving and not self.is_hiding:
                self.walk_anim.update(dt)
        self._last_state = game_state

    def draw(self, surface, game_state):
        if game_state == WIN:
            image = self.win_image_outlined
        elif game_state == LOSE:
            image = self.shake_frame1 if self.shake_frame_index == 0 else self.shake_frame2
        else:
            # 游戏最开头未开始操作时显示静止图片；开始走路后才显示走路动图
            if self.is_hiding or not self.game_started:
                image = self.idle_image
            else:
                image = self.walk_anim.get_current_frame()

        iw, ih = image.get_width(), image.get_height()
        cx = self.x + (self.width - iw) // 2
        cy = self.y + (self.height - ih) // 2
        surface.blit(image, (cx, cy))

    def get_rect(self):
        shrink = 20
        return pygame.Rect(self.x + shrink, self.y + shrink, self.width - 2 * shrink, self.height - 2 * shrink)


class Cake:
    def __init__(self):
        # 帧
        cake_frame_paths = sorted(
            [os.path.join("images/cake", f) for f in os.listdir("images/cake") if f.startswith("cake_") and f.endswith(".png") and f != "cake_eaten.png"]
        )
        cake_frames = [pygame.image.load(p).convert_alpha() for p in cake_frame_paths]
        self.idle_anim = Animation(cake_frames, 250)
        self.eaten_image = pygame.image.load("images/cake/cake_eaten.png").convert_alpha()

        # 位置（逻辑尺寸用于碰撞）
        self.width = 197
        self.height = 237
        self.x = SCREEN_WIDTH - 300
        self.y = SCREEN_HEIGHT - self.height - 50

    def update(self, dt):
        self.idle_anim.update(dt)

    def draw(self, surface, game_state):
        image = self.eaten_image if game_state == WIN else self.idle_anim.get_current_frame()
        surface.blit(image, (self.x, self.y))

    def get_rect(self):
        shrink = 20
        return pygame.Rect(self.x + shrink, self.y + shrink, self.width - 2 * shrink, self.height - 2 * shrink)


class Guard:
    def __init__(self):
        self.sleep_image = pygame.image.load("images/guard/guard_sleep.png").convert_alpha()
        self.watch_image = pygame.image.load("images/guard/guard_watch.png").convert_alpha()
        self.angry_image = pygame.image.load("images/guard/guard_angry.png").convert_alpha()
        self.surprised_image = pygame.image.load("images/guard/guard_surprised.png").convert_alpha()
        self.slap_frames = [pygame.image.load(f"images/slap/slap_{i}.png").convert_alpha() for i in range(1, 4)]
        self.slap_anim = Animation(self.slap_frames, 500, loop=False)
        self.reset()

    def reset(self):
        self.width = 450
        self.height = 308
        self.x = SCREEN_WIDTH - self.width - 93
        self.y = SCREEN_HEIGHT - self.height - 140
        self.is_watching = False
        self.watch_timer = 0
        self.watch_duration = random.randint(90, 180)
        self.slap_anim.reset()
        self._last_state = None

    def update(self, dt, game_state):
        if game_state == PLAYING:
            self.watch_timer += 1
            if self.watch_timer >= self.watch_duration:
                self.is_watching = not self.is_watching
                self.watch_timer = 0
                self.watch_duration = random.randint(30, 60) if self.is_watching else random.randint(90, 180)
        elif game_state == LOSE:
            if self._last_state != LOSE:
                self.slap_anim.reset()
            self.slap_anim.update(dt)
        self._last_state = game_state

    def draw(self, surface, game_state):
        if game_state == LOSE:
            surface.blit(self.surprised_image, (self.x, self.y))
        elif game_state == WIN:
            surface.blit(self.angry_image, (self.x, self.y))
        else:
            surface.blit(self.watch_image if self.is_watching else self.sleep_image, (self.x, self.y))


class Game:
    def __init__(self):
        # 背景（桌子）
        try:
            self.background = pygame.image.load("images/table.png").convert_alpha()
            self.background_width, self.background_height = self.background.get_size()
            self.table_x = 0
            self.table_y = SCREEN_HEIGHT - self.background_height
        except Exception:
            self.background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            self.background.fill(WHITE)
            self.table_x = 0
            self.table_y = 0

        # 对象
        self.guard = Guard()
        self.cockroach = Cockroach(self)
        self.cake = Cake()

        # 字体：优先使用项目中的自定义字体文件（fonts/ 目录），否则回退到 Arial Bold
        def _find_project_font_path():
            exts = (".ttf", ".otf", ".ttc", ".otc")
            search_dirs = ["fonts", "font", ".", os.path.join("assets", "fonts")]
            preferred_basenames = ["custom_font", "CustomFont", "game_font", "GameFont"]
            # 优先尝试命名约定
            for d in search_dirs:
                if not os.path.isdir(d):
                    continue
                for base in preferred_basenames:
                    for ext in exts:
                        p = os.path.join(d, base + ext)
                        if os.path.exists(p):
                            return p
            # 否则取目录下第一个字体文件
            for d in search_dirs:
                if not os.path.isdir(d):
                    continue
                try:
                    files = [f for f in os.listdir(d) if f.lower().endswith(exts)]
                    files.sort()
                    for f in files:
                        p = os.path.join(d, f)
                        return p
                except Exception:
                    pass
            return None

        def _load_arial_bold(size=36):
            try:
                path = pygame.font.match_font("arial", True)
                if path:
                    return pygame.font.Font(path, size)
            except Exception:
                pass
            try:
                return pygame.font.SysFont("Arial", size, bold=True)
            except Exception:
                return pygame.font.Font(None, size)

        # 优先使用指定字体 fonts/Bungee-Regular.ttf
        bungee_path = os.path.join("fonts", "Bungee-Regular.ttf")
        try:
            if os.path.exists(bungee_path):
                # 调小字号
                self.font = pygame.font.Font(bungee_path, 28)
                self.small_font = pygame.font.Font(bungee_path, 20)
            else:
                # 自动查找项目字体
                project_font_path = _find_project_font_path()
                if project_font_path and os.path.exists(project_font_path):
                    self.font = pygame.font.Font(project_font_path, 28)
                    self.small_font = pygame.font.Font(project_font_path, 20)
                else:
                    # 回退 Arial Bold
                    self.font = _load_arial_bold(28)
                    self.small_font = _load_arial_bold(20)
        except Exception:
            # 任一加载失败时的兜底
            self.font = _load_arial_bold(28)
            self.small_font = _load_arial_bold(20)

        # 其他配置
        self.clock = pygame.time.Clock()
        self.cockroach_last_pos = (self.cockroach.x, self.cockroach.y)
        self.prev_r_pressed = False
        self.move_tolerance = 5
        self.slap_offset_x = 0
        self.slap_right_offset = 35

        # 开场图片
        def _load_image_by_stem(stem: str):
            cand_exts = [".png", ".jpg", ".jpeg", ""]
            for ext in cand_exts:
                path = os.path.join("images", stem + ext)
                if os.path.exists(path):
                    try:
                        return pygame.image.load(path).convert_alpha()
                    except Exception:
                        pass
            try:
                for f in os.listdir("images"):
                    fl = f.lower()
                    if fl.startswith(stem.lower() + ".") and (fl.endswith(".png") or fl.endswith(".jpg") or fl.endswith(".jpeg")):
                        return pygame.image.load(os.path.join("images", f)).convert_alpha()
            except Exception:
                pass
            s = pygame.Surface((10, 10), pygame.SRCALPHA)
            s.fill((0, 0, 0, 0))
            return s

        self.title_image = _load_image_by_stem("title")
        self.rule_image = _load_image_by_stem("rule")

        # 初始状态：INTRO
        self.game_state = INTRO
        self.intro_stage = 0  # 0=title, 1=rule

    def draw_text(self, text, x, y, color=BLACK):
        surface = self.font.render(text, True, color)
        screen.blit(surface, (x, y))

    def draw_text_wrapped(self, text, x, y, color=BLACK, font=None, max_width=520, line_spacing=4):
        """在给定宽度内按单词换行绘制文本。若单词过长，会按字符拆分。"""
        if font is None:
            font = self.font
        if not text:
            return y
        words = text.split(' ')
        lines = []
        current_line = ''
        for word in words:
            test_line = word if current_line == '' else current_line + ' ' + word
            w, _ = font.size(test_line)
            if w <= max_width:
                current_line = test_line
            else:
                # 如果单词本身就超过宽度，按字符拆分
                if current_line:
                    lines.append(current_line)
                long_word = word
                buffer = ''
                for ch in long_word:
                    cw, _ = font.size(buffer + ch)
                    if cw <= max_width:
                        buffer += ch
                    else:
                        if buffer:
                            lines.append(buffer)
                        buffer = ch
                current_line = buffer
        if current_line:
            lines.append(current_line)

        line_y = y
        for ln in lines:
            surf = font.render(ln, True, color)
            screen.blit(surf, (x, line_y))
            line_y += font.get_linesize() + line_spacing
        return line_y

    def check_movement(self):
        # 开始后：守卫睁眼 且 玩家未按空格躲藏 => 直接判定失败
        if self.guard.is_watching and self.cockroach.game_started:
            if not self.cockroach.is_hiding:
                self.game_state = LOSE
                self.guard.slap_anim.reset()
        self.cockroach_last_pos = (self.cockroach.x, self.cockroach.y)

    def draw(self):
        screen.fill(WHITE)

        if self.game_state == INTRO:
            # 场景（桌子打底 → 守卫 → 蛋糕 → 蟑螂）
            screen.blit(self.background, (self.table_x, self.table_y))
            self.guard.draw(screen, PLAYING)
            self.cake.draw(screen, PLAYING)
            self.cockroach.draw(screen, PLAYING)
            # 覆盖开场图片（不再显示提示文字）
            current_img = self.title_image if self.intro_stage == 0 else self.rule_image
            iw, ih = current_img.get_width(), current_img.get_height()
            ix = SCREEN_WIDTH // 2 - iw // 2
            iy = SCREEN_HEIGHT // 2 - ih // 2
            screen.blit(current_img, (ix, iy))
            pygame.display.flip()
            return

        # 正常场景：桌子打底
        screen.blit(self.background, (self.table_x, self.table_y))
        # 守卫
        self.guard.draw(screen, self.game_state)
        # 拍打（仅在失败时）并按蟑螂右缘+偏移对齐
        if self.game_state == LOSE:
            slap_frame = self.guard.slap_anim.get_current_frame()
            slap_y = 195
            walk_img = self.cockroach.walk_anim.get_current_frame()
            walk_left = self.cockroach.x + (self.cockroach.width - walk_img.get_width()) // 2
            walk_right = walk_left + walk_img.get_width()
            slap_right = walk_right + self.slap_right_offset
            slap_x = int(slap_right - slap_frame.get_width() + self.slap_offset_x)
            screen.blit(slap_frame, (slap_x, slap_y))
        # 蛋糕
        self.cake.draw(screen, self.game_state)
        # 蟑螂（拍打第3帧时隐藏）
        if self.game_state == LOSE:
            if not self.guard.slap_anim.finished and self.guard.slap_anim.current_frame < 2:
                self.cockroach.draw(screen, self.game_state)
        else:
            self.cockroach.draw(screen, self.game_state)

        # 状态与结局提示
        status_text = "Watch out! She is watching!" if self.guard.is_watching else "Go!"
        left_x = 20
        base_y = int(SCREEN_HEIGHT * 0.35)
        next_y = self.draw_text_wrapped(status_text, left_x, base_y, BLACK, self.font, max_width=520)
        if self.game_state == WIN:
            self.draw_text_wrapped("Great! Press R to restart", left_x, next_y + 10, BLACK, self.font, max_width=520)
        elif self.game_state == LOSE:
            self.draw_text_wrapped("Caught! Press R to restart", left_x, next_y + 10, BLACK, self.font, max_width=520)

        pygame.display.flip()

    def reset(self):
        self.game_state = PLAYING
        self.guard.reset()
        self.cockroach = Cockroach(self)
        self.cake = Cake()
        self.cockroach_last_pos = (self.cockroach.x, self.cockroach.y)

    def run(self):
        running = True
        last_frame_time = pygame.time.get_ticks()
        frame_count = 0
        last_fps_check = last_frame_time
        while running:
            current_time = pygame.time.get_ticks()
            dt = current_time - last_frame_time
            last_frame_time = current_time

            frame_count += 1
            if current_time - last_fps_check >= 1000:
                frame_count = 0
                last_fps_check = current_time

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if self.game_state == INTRO and event.key == pygame.K_SPACE:
                        if self.intro_stage == 0:
                            self.intro_stage = 1
                        else:
                            self.game_state = PLAYING
                    elif event.key == pygame.K_r and self.game_state != INTRO:
                        self.reset()

            keys = pygame.key.get_pressed()
            if self.game_state != INTRO:
                r_pressed = keys[pygame.K_r]
                if r_pressed and not self.prev_r_pressed:
                    self.reset()
                self.prev_r_pressed = r_pressed

            if self.game_state != INTRO:
                self.guard.update(dt, self.game_state)
                self.cockroach.update(dt, self.game_state)

            if self.game_state == PLAYING:
                self.cake.update(dt)
                self.cockroach.move(keys)
                self.check_movement()
                # 胜利：以蟑螂逻辑中心与蛋糕图片中心比较
                cake_img = self.cake.idle_anim.get_current_frame()
                cake_center_x = self.cake.x + cake_img.get_width() // 2
                roach_center_x = self.cockroach.x + self.cockroach.width // 2
                if roach_center_x >= cake_center_x:
                    self.game_state = WIN

            self.draw()
            self.clock.tick(60)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()