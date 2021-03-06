__author__ = 'anish'
from entity import *
from sprite import Sprite
from pyglet import image
from random import randint, choice
from copy import copy
from common import *


class Ghost(Entity):

    def __init__(self, game, x, y):

        super().__init__(game, x, y)

        # setpoint coordinates
        self.want_x = self.x
        self.want_y = self.y

        self.count = 0

        self.state = "idle"
        self.pre_state = None

        self.target_player = choice(self.game.players)

        # The wanderpoint variable is specific to this each ghost
        self.wanderpoint = []
        self.escaped = False
        #TODO Hardcoding an escape tile isnt map-agnostic, do figure this out
        self.escape_tile = [15.5, 19.5]

        self.speeds = {"wander": self.speed, "escape": self.speed, "chase": self.speed,
                       "scared": Fraction(1, 2) * self.speed, "flashing": Fraction(1, 2) * self.speed,
                       "idle": Fraction(0, 1), "retreat": Fraction(2, 1) * self.speed}

        self.dot_threshold = 0

        self.normal_sprites = None

        # Get the scared spritesheet. This variable *could* be static, but isn't because of concerns that will never
        # apply, probably. Christian would be proud

        scared_spritesheet = Entity.spritesheet.get_region(4 * 32, 6 * 32, 4 * 32, 32)

        self.scared_sprites = image.ImageGrid(scared_spritesheet, 1, 4, item_width=32, item_height=32)
        for i in range(len(self.scared_sprites)):
            self.scared_sprites[i].anchor_x = self.scared_sprites[i].width // 2
            self.scared_sprites[i].anchor_y = self.scared_sprites[i].width // 2

        self.scared_sprites = [Sprite(i, self.game.graphics_group) for i in self.scared_sprites]

    def load_resources(self, row):

        # Slice out the needed region of the sprite sheet (32 x 32 Pac-Man normal_sprites)
        spritesheet = Entity.spritesheet.get_region(0, row * 32, 8 * 32, 32)

        # Convert the image into an array of images, and center their anchor points
        self.normal_sprites = image.ImageGrid(spritesheet, 1, 8, item_width=32, item_height=32)
        for i in range(len(self.normal_sprites)):
            self.normal_sprites[i].anchor_x = self.normal_sprites[i].width // 2
            self.normal_sprites[i].anchor_y = self.normal_sprites[i].width // 2

        # Convert the images in the array to normal_sprites
        self.normal_sprites = [Sprite(i, self.game.graphics_group) for i in self.normal_sprites]

        temp = copy(self.normal_sprites)
        self.normal_sprites = {}
        angles = {90: temp[0], 270: temp[2], 180: temp[4], 0: temp[6]}
        self.normal_sprites[0] = angles
        angles = {0: temp[7], 90: temp[1], 270: temp[3], 180: temp[5]}
        self.normal_sprites[1] = angles

    def update(self):

        super().update()

        if not self.escaped and self.game.dots_eaten >= self.dot_threshold:
            self.state = "escape"

        if self.state == "idle":
            return None

        if self.state == "escape":
            self.set_setpoint(*self.escape_tile)

            if not self.escaped and [self.x, self.y] == self.escape_tile:
                self.state = "wander"
                self.escaped = True

        if self.state == "retreat":
            self.set_setpoint(*self.escape_tile)
            if [self.x, self.y] == self.escape_tile:
                self.state = "wander"

        if self.state == "chase":
            self.set_setpoint(*self.target())

        if self.state == "wander":
            self.set_setpoint(*self.wanderpoint)

        if self.state == "scared":
            self.set_setpoint(*self.panic())

        if self.state == "flashing":
            self.set_setpoint(*self.panic())

        if self.pre_state == "flashing" or self.pre_state == "scared" or self.pre_state == "retreat" and \
            self.state != self.pre_state:

            self.target_player = choice(self.game.players)

        self.speed = self.speeds[self.state]
        self.x -= self.x % self.speed
        self.y -= self.y % self.speed

        self.update_pos()

        self.pre_state = self.state

    def update_pos(self):

        self.update_movement_possibilities()

        # The AI attempts to take the shortest path to target. The squares of the distances are actually used to avoid
        # having to call math.sqrt
        up_distance = pow(float(self.x) - float(self.want_x), 2) + pow(float(self.y) + float(self.speed) - float(self.want_y), 2)
        left_distance = pow(float(self.x) - float(self.speed) - float(self.want_x), 2) + pow(float(self.y) - float(self.want_y), 2)
        down_distance = pow(float(self.x) - float(self.want_x), 2) + pow(float(self.y) - float(self.speed) - float(self.want_y), 2)
        right_distance = pow(float(self.x) + float(self.speed) - float(self.want_x), 2) + pow(float(self.y) - float(self.want_y), 2)

        distances = [right_distance, left_distance, down_distance, up_distance]

        # This loop is needed to ensure that a valid theta is always set. If this is not included then sometimes an
        # appropriate theta will not be set because it is not the shortest path, allowing invalid paths to be taken

        theta_set = False

        while not theta_set:

            min_distance = min(distances)

            if self.can_up and up_distance == min_distance and self.theta != 270:
                self.theta = 90
                theta_set = True

            elif self.can_left and left_distance == min_distance and self.theta != 0:
                self.theta = 180
                theta_set = True

            elif self.can_down and down_distance == min_distance and self.theta != 90:
                self.theta = 270
                theta_set = True

            elif self.can_right and right_distance == min_distance and self.theta != 180:
                self.theta = 0
                theta_set = True

            #if none of the minimum distances are in valid directions, remove them from consideration and reloop
            if not theta_set:
                distances = [d for d in distances if d != min_distance]

                if not distances:
                    up_distance = 1
                    left_distance = 2
                    down_distance = 3
                    right_distance = 4
                    distances = [1, 2, 3, 4]

        self.x += self.speed * cos(self.theta).__int__()
        self.y += self.speed * sin(self.theta).__int__()

    def update_movement_possibilities(self):
        '''
        Method meant to calculate possible directions the entity can go in. This does not account for the no-reversal
        rule- that is taken care of in the update method. This simply tests for a block in the desired position
        :return: None
        '''
        #The .000001 is included to make sure that the method correctly detects the presence of a block on the game
        # The constant's value does not matter, but it should be smaller than 1 / self.speed
        self.can_up = self.x % 1 == 0.5 and self.game.grid[int(self.y + 0.5)][int(self.x)] != "b"
        self.can_left = self.y % 1 == 0.5 and self.game.grid[int(self.y)][int(self.x - 0.5 - .00000001)] != "b"
        self.can_down = self.x % 1 == 0.5 and self.game.grid[int(self.y - 0.5 - .000000001)][int(self.x)] != "b" and \
            self.game.grid[int(self.y - 0.5 - .000000001)][int(self.x)] != "g"
        self.can_right = self.y % 1 == 0.5 and self.game.grid[int(self.y)][int(self.x + 0.5)] != "b"

    def draw(self):
        '''
        Draw the appropriate sprite to the game
        :return: None
        '''
        self.count += .08

        #Based on the count and the current theta, draw a frame rotated at the appropriate angle

        if self.state == "idle":
            self.normal_sprites[int(self.count % 2)][0].set_position(int(self.x * GRID_DIM), int(self.y * GRID_DIM))
            self.normal_sprites[int(self.count % 2)][0].draw()

        elif self.state == "chase" or self.state == "wander" or self.state == "escape" or self.state == "retreat":
            self.normal_sprites[int(self.count % 2)][self.theta].set_position(int(self.x * GRID_DIM),
                                                                              int(self.y * GRID_DIM))
            self.normal_sprites[int(self.count % 2)][self.theta].draw()

        elif self.state == "scared":
            self.scared_sprites[int(self.count % 2)].set_position(int(self.x * GRID_DIM), int(self.y * GRID_DIM))
            self.scared_sprites[int(self.count % 2)].draw()

        elif self.state == 'flashing':
            self.scared_sprites[int(self.count % 4)].set_position(int(self.x * GRID_DIM), int(self.y * GRID_DIM))
            self.scared_sprites[int(self.count % 4)].draw()

    def set_setpoint(self, x, y):

        self.want_x = x
        self.want_y = y

    def panic(self):

        #TODO THis isnt map-agnostic, fix later?
        return [randint(0, 32), randint(0, 31)]

    def target(self):

        raise NotImplementedError
