"""Example of automatic vehicle control from client side."""

import hydra
import logging
import pygame
import carla
import random

from hud import HUD
from world import World
from agent import (
    BasicAgent,
    ConstantVelocityAgent,
    BehaviorAgent
)
from utils import KeyboardControl


def game_loop(config):
    """
    Main loop of the simulation. It handles updating all the HUD information,
    ticking the agent and, if needed, the world.
    """

    pygame.init()
    pygame.font.init()
    world = None

    try:
        if config['seed']:
            random.seed(config['seed'])

        client = carla.Client(config['host'], config['port'])
        client.set_timeout(60.0)

        traffic_manager = client.get_trafficmanager()
        sim_world = client.get_world()

        if config['sync']:
            settings = sim_world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = 0.05
            sim_world.apply_settings(settings)

            traffic_manager.set_synchronous_mode(True)

        display = pygame.display.set_mode(
            (config['resolution']['width'], config['resolution']['height']),
            pygame.HWSURFACE | pygame.DOUBLEBUF)

        hud = HUD(config['resolution']['width'], config['resolution']['height'])
        world = World(client.get_world(), hud, config)
        controller = KeyboardControl(world)
        if config['agent'] == "Basic":
            agent = BasicAgent(world.player, 30)
            agent.follow_speed_limits(True)
        elif config['agent'] == "Constant":
            agent = ConstantVelocityAgent(world.player, 30)
            ground_loc = world.world.ground_projection(world.player.get_location(), 5)
            if ground_loc:
                world.player.set_location(ground_loc.location + carla.Location(z=0.01))
            agent.follow_speed_limits(True)
        elif config['agent'] == "Behavior":
            agent = BehaviorAgent(world.player, behavior=config['behavior'])

        # Set the agent destination
        spawn_points = world.map.get_spawn_points()
        destination = random.choice(spawn_points).location
        agent.set_destination(destination)

        clock = pygame.time.Clock()

        while True:
            clock.tick()
            if config['sync']:
                world.world.tick()
            else:
                world.world.wait_for_tick()
            if controller.parse_events():
                return

            world.tick(clock)
            world.render(display)
            pygame.display.flip()

            if agent.done():
                if config['loop']:
                    agent.set_destination(random.choice(spawn_points).location)
                    world.hud.notification("Target reached", seconds=4.0)
                    print("The target has been reached, searching for another target")
                else:
                    print("The target has been reached, stopping the simulation")
                    break

            control = agent.run_step()
            control.manual_gear_shift = False
            world.player.apply_control(control)

    finally:

        if world is not None:
            settings = world.world.get_settings()
            settings.synchronous_mode = False
            settings.fixed_delta_seconds = None
            world.world.apply_settings(settings)
            traffic_manager.set_synchronous_mode(True)

            world.destroy()

        pygame.quit()

@hydra.main(config_path="config/config.yaml")
def main(config):
    """Main method"""

    log_level = logging.DEBUG if config['verbose'] else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', config['host'], config['port'])

    print(__doc__)

    try:
        game_loop(config)

    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':
    main()