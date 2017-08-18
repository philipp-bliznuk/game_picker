#!/usr/bin/env python3
import os
import sys
import json
import random
import asyncio
import aiohttp
import urllib.parse
import urllib.request


STEAM_API_KEY = '8E4ADBD9A8BB2F63A57DF91B24260A12'
MULTIPLAYER_CATEGORY_IDS = [1, 9]
DATA_DIR = os.path.join(os.getcwd(), 'data')


if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


class TooManyRequests(Exception):
    pass


def error(message):
    print('\033[91m{}\033[0m'.format(message))


def warning(message):
    print('\033[93m{}\033[0m'.format(message))


class GamePicker(object):
    def setup(self):
        warning('http://steamcommunity.com/id/<steam_name>')
        libraries = []
        loop = asyncio.get_event_loop()

        for player_steam_id, player_data in self.get_players().items():
            player_mention = player_data['mention']
            print('{} Steam ID is: {}'.format(player_mention, player_steam_id))
            print('Fetching {} Steam library...'.format(player_mention))
            libraries.append(self.collect_library(player_steam_id, loop))

        loop.close()
        if libraries:
            intersection_keys = set.intersection(*[set(library.keys()) for library in libraries])
            self.intersection = [v for k, v in libraries[0].items() if k in intersection_keys]

    def get_players(self):
        players_filename = os.path.join(DATA_DIR, 'players.json')
        answers = {
            'positive': ('', 'Y', 'y', 'Yes', 'yes'),
            'negative': ('N', 'n', 'No', 'no')
        }
        if os.path.isfile(players_filename):
            with open(players_filename) as f:
                players = json.load(f)

            while True:
                answer = input('Do you want to use previous player setup ({}), or enter new players? [Y/n]: '.format(
                    ', '.join(player_data['name'] for _, player_data in players.items())
                ))
                if answer in answers['positive'] or answer in answers['negative']:
                    break

            if answer in answers['positive']:
                return players

        players = {}
        for mention in ['1st player', '2nd player']:
            player_steam_id, player_steam_name = self.get_steam_id(mention)
            players[player_steam_id] = {'mention': mention, 'name': player_steam_name}

        with open(players_filename, 'w') as f:
            json.dump(players, f)

        return players

    def get_steam_api_url(self, category, method, **params):
        base_url = 'http://api.steampowered.com/{}/{}/v0001/?key={}&{}'
        encoded_params = urllib.parse.urlencode(params)
        return base_url.format(category, method, STEAM_API_KEY, encoded_params)

    def get_steam_id(self, mention):
        steam_name = input('Please enter {} Steam name: '.format(mention))
        resolve_name_url = self.get_steam_api_url('ISteamUser', 'ResolveVanityURL', **{'vanityurl': steam_name})
        response = json.load(urllib.request.urlopen(resolve_name_url)).get('response', {})
        if response.get('success') != 1:
            error('Sorry, no matches for this name, lets try again :)')
            return self.get_steam_id(mention)
        return response.get('steamid'), steam_name

    def collect_library(self, steam_id, loop):
        library_filename = os.path.join(DATA_DIR, '{}.json'.format(steam_id))
        if os.path.isfile(library_filename):
            with open(library_filename) as f:
                multiplayer_games = json.load(f)
            return multiplayer_games

        library_url_params = {'include_played_free_games': 1, 'include_appinfo': 1, 'steamid': steam_id, 'format': 'json'}
        library_url = self.get_steam_api_url('IPlayerService', 'GetOwnedGames', **library_url_params)
        response = json.load(urllib.request.urlopen(library_url)).get('response')
        games = {game['appid']: game['name'] for game in response.get('games', [])}
        multiplayer_games = {}

        loop.run_until_complete(self.app_details_coroutine(games, multiplayer_games))

        with open('{}.json'.format(steam_id), 'w') as f:
            json.dump(multiplayer_games, f)

        return multiplayer_games

    async def app_details_coroutine(self, games, multiplayer_games):
        semaphore = asyncio.Semaphore(5)
        async with semaphore:
            async with aiohttp.ClientSession(loop=loop) as session:
                futures = [self.download_app_details(session, app_id, app_name) for app_id, app_name in games.items()]
                for future in asyncio.as_completed(futures):
                    try:
                        result = await future
                    except TooManyRequests:
                        error('Sorry, it\'s too many requests, try again later.')
                        sys.exit()
                    if result is not None:
                        multiplayer_games.update(result)

    async def download_app_details(self, session, app_id, app_name):
        app_detail_url = 'http://store.steampowered.com/api/appdetails?appids={}'.format(app_id)
        async with session.get(app_detail_url) as response:
            if response.status != 429:
                raise TooManyRequests

            json_response = await response.json()
            app_details = json_response.get(str(app_id))
            categories = app_details.get('data', {}).get('categories')
            if categories is None:
                return

            category_ids = [category['id'] for category in categories]
            if any([multiplayer_category_id in category_ids for multiplayer_category_id in MULTIPLAYER_CATEGORY_IDS]):
                return {app_id: app_name}

    def pick_game(self):
        warning('Press `Ctrl+C` to exit')
        game_iterator = self.intersection[:]
        while True:
            games_left_in_pool = len(game_iterator)
            if games_left_in_pool == 0:
                game_iterator = self.intersection[:]
                games_left_in_pool = len(game_iterator)

            input('{} games left in pool: '.format(games_left_in_pool))
            index = random.choice(range(games_left_in_pool))
            warning(game_iterator[int(index)])
            game_iterator.pop(index)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    picker = GamePicker()
    picker.setup()
    print()
    try:
        picker.pick_game()
    except KeyboardInterrupt:
        sys.exit()
